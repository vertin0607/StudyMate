"""教学会话。读取已有学习记录，只有发送消息时才调用模型。"""

import json
import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, delete, select

from app.models.goal import LearningGoal
from app.models.knowledge import KnowledgePoint
from app.models.quiz import KnowledgeMasteryEvent, QuizAnswer, QuizQuestion
from app.models.tutor import TutorMessage, TutorSession
from app.services import goal_service
from app.services.ai.deepseek_client import complete_json
from app.services.ai.errors import AIError
from app.services.ai.prompt_builder import MAX_ATTEMPTS, build_repair_messages
from app.services.mastery import status_label
from app.services.tutor_evidence import analyze_message, public_diagnosis
from app.services.tutor_math import normalize_tutor_math

logger = logging.getLogger(__name__)
PROMPT_PATH_FALLBACK = None
DEFAULT_TITLE = "新的对话"


def teaching_strategy(mastery: int | None, assessed: bool) -> tuple[str, str]:
    """按已有掌握度选择讲解深度。未评估按基础讲解。"""
    if not assessed or mastery is None or mastery < 60:
        return "basic", "从基本概念讲起，使用生活化类比，不要直接堆砌公式"
    if mastery < 85:
        return "intermediate", "解释内部原理，提供一个简单例子，并逐个解释重要公式里的符号"
    return "advanced", "深入分析，提供综合应用，并联系实际问题"


def select_focus(points: list[dict], question: str) -> list[dict]:
    """问题里点到的知识点优先。多个命中时先讲掌握度更低的。"""
    text = question.casefold()
    matched = [point for point in points if point["name"] and point["name"].casefold() in text]
    matched.sort(key=lambda item: item["mastery_level"] if item["mastery_assessed"] and item["mastery_level"] is not None else -1)
    return matched[:2]


def parse_tutor_reply(raw: str) -> str:
    """只接受带正文的 JSON。不合规则不能入库。"""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("回复不是 JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("回复不是 JSON 对象")
    reply = data.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        raise ValueError("回复缺少正文")
    reply = reply.strip()
    if len(reply) > 8000:
        raise ValueError("回复过长")
    reply = normalize_tutor_math(reply)
    if not reply.strip():
        raise ValueError("回复缺少正文")
    return reply


def create_session(session: Session, goal_id: int | None, title: str | None) -> dict:
    user = goal_service.ensure_local_user(session)
    goal = None if goal_id is None else goal_service.get_goal(session, goal_id)
    now = datetime.now(timezone.utc)
    row = TutorSession(
        user_id=user.id,
        goal_id=None if goal is None else goal.id,
        title=(title or DEFAULT_TITLE).strip() or DEFAULT_TITLE,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    goal_service.commit_or_raise(session)
    session.refresh(row)
    return _session_payload(session, row, include_messages=True)


def list_sessions(session: Session) -> dict:
    user = goal_service.ensure_local_user(session)
    rows = session.exec(
        select(TutorSession).where(TutorSession.user_id == user.id).order_by(TutorSession.updated_at.desc())
    ).all()
    return {"sessions": [_session_summary(session, row) for row in rows]}


def get_session_detail(session: Session, session_id: int) -> dict:
    row = _owned_session(session, session_id)
    return _session_payload(session, row, include_messages=True)


def delete_session(session: Session, session_id: int) -> None:
    row = _owned_session(session, session_id)
    session.exec(delete(TutorMessage).where(TutorMessage.session_id == row.id))
    session.delete(row)
    goal_service.commit_or_raise(session)


def send_message(session: Session, session_id: int, content: str) -> dict:
    row = _owned_session(session, session_id)
    text = content.strip()
    if not text:
        raise HTTPException(status_code=422, detail="请输入要问的问题")
    context, analysis = _context(session, row, text)
    reply = _request_reply(context)
    now = datetime.now(timezone.utc)
    user_message = TutorMessage(session_id=row.id, role="user", content=text, created_at=now)
    assistant_message = TutorMessage(
        session_id=row.id,
        role="assistant",
        content=reply,
        knowledge_point_ids_json=json.dumps(context["focus_ids"], ensure_ascii=False),
        created_at=now,
    )
    if row.title == DEFAULT_TITLE:
        row.title = text[:24]
    row.updated_at = now
    session.add(user_message)
    session.add(assistant_message)
    session.add(row)
    goal_service.commit_or_raise(session)
    session.refresh(user_message)
    session.refresh(assistant_message)
    payload = {
        "user_message": _message_payload(user_message),
        "assistant_message": _message_payload(assistant_message),
    }
    diagnosis = public_diagnosis(analysis)
    if diagnosis is not None:
        payload["diagnosis"] = diagnosis
    return payload


def _request_reply(context: dict) -> str:
    from pathlib import Path

    prompt = Path(__file__).resolve().parents[1].joinpath("prompts", "tutor.txt").read_text(encoding="utf-8")
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "请回复这次提问：\n" + json.dumps(context, ensure_ascii=False)},
    ]
    last_error = "回复缺少正文"
    raw = ""
    for _attempt in range(MAX_ATTEMPTS):
        raw = complete_json(messages, max_tokens=1600)
        try:
            return parse_tutor_reply(raw)
        except ValueError as exc:
            last_error = str(exc)
            messages = build_repair_messages(messages, raw, last_error)
    raise AIError(last_error, status_code=502)


def _context(session: Session, row: TutorSession, question: str) -> tuple[dict, dict]:
    goal = None if row.goal_id is None else session.get(LearningGoal, row.goal_id)
    analysis = analyze_message(session, user_id=row.user_id, goal_id=row.goal_id, question=question)
    strategy = analysis["teaching_strategy"]
    guidance = _strategy_guidance(strategy)
    history = session.exec(
        select(TutorMessage).where(TutorMessage.session_id == row.id).order_by(TutorMessage.id)
    ).all()
    focus_ids = [point_id for point_id in [analysis["knowledge_point_id"]] if point_id is not None]
    context = {
        "goal": None
        if goal is None
        else {"id": goal.id, "title": goal.title, "description": goal.description},
        "focus_ids": focus_ids,
        "focus_names": [] if analysis["knowledge_point_name"] is None else [analysis["knowledge_point_name"]],
        "strategy": strategy,
        "strategy_guidance": guidance,
        "evidence_status": analysis["evidence_status"],
        "teaching_context": analysis["model_context"],
        "history": [{"role": item.role, "content": item.content[:500]} for item in history[-8:]],
        "question": question,
    }
    return context, analysis


def _strategy_guidance(strategy: str) -> str:
    """沿用原来的掌握度讲解要求，并限制追问次数。"""
    limit = "用户明确说不会时先解释，不要连续追问。最后最多提出一个检查问题。"
    if strategy == "intermediate":
        return teaching_strategy(74, True)[1] + limit
    if strategy == "advanced":
        return teaching_strategy(95, True)[1] + limit
    if strategy == "code_debugging":
        return "先看当前这道题的最新代码，指出最小的错误位置，说明原因，并给出局部修改。保留用户原来的结构，不要重写整份代码。" + limit
    if strategy == "forgetting_recovery":
        return "先接上这个知识点里已经掌握过的部分，只补现在对不上的环节。不要因为距离上次学习较远就认定已经遗忘。" + limit
    return teaching_strategy(40, True)[1] + limit


def _points(session: Session, goal: LearningGoal) -> list[dict]:
    rows = session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id == goal.id).order_by(KnowledgePoint.id)).all()
    payload = []
    for point in rows:
        events = session.exec(
            select(KnowledgeMasteryEvent)
            .where(KnowledgeMasteryEvent.knowledge_point_id == point.id)
            .order_by(KnowledgeMasteryEvent.created_at)
        ).all()
        assessed = bool(events) or point.status == "mastered"
        scores = [event.quiz_score for event in events]
        payload.append(
            {
                "id": point.id,
                "name": point.name,
                "mastery_level": None if not assessed else point.mastery_level,
                "mastery_assessed": assessed,
                "status_label": status_label(point.status, assessed),
                "latest_score": None if not scores else scores[-1],
                "weak_points": _weak_reasons(session, point.id),
            }
        )
    return payload


def _weak_reasons(session: Session, point_id: int | None) -> list[str]:
    if point_id is None:
        return []
    answers = session.exec(
        select(QuizAnswer)
        .join(QuizQuestion, QuizAnswer.question_id == QuizQuestion.id)
        .where(QuizQuestion.knowledge_point_id == point_id, QuizAnswer.is_correct == False)  # noqa: E712
    ).all()
    reasons: list[str] = []
    for answer in answers:
        text = answer.error_reason.strip()
        if text and text not in reasons:
            reasons.append(text)
        if len(reasons) == 3:
            break
    return reasons


def _owned_session(session: Session, session_id: int) -> TutorSession:
    row = session.get(TutorSession, session_id)
    user = goal_service.ensure_local_user(session)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="教学会话不存在")
    if row.goal_id is not None:
        goal_service.get_goal(session, row.goal_id)
    return row


def _session_summary(session: Session, row: TutorSession) -> dict:
    count = len(session.exec(select(TutorMessage).where(TutorMessage.session_id == row.id)).all())
    goal = None if row.goal_id is None else session.get(LearningGoal, row.goal_id)
    return {
        "id": row.id,
        "title": row.title,
        "goal_id": row.goal_id,
        "goal_title": None if goal is None else goal.title,
        "message_count": count,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _session_payload(session: Session, row: TutorSession, include_messages: bool) -> dict:
    payload = _session_summary(session, row)
    goal = None if row.goal_id is None else session.get(LearningGoal, row.goal_id)
    payload["points"] = [] if goal is None else _points(session, goal)
    if include_messages:
        messages = session.exec(select(TutorMessage).where(TutorMessage.session_id == row.id).order_by(TutorMessage.id)).all()
        payload["messages"] = [_message_payload(item) for item in messages]
    return payload


def _message_payload(row: TutorMessage) -> dict:
    try:
        point_ids = json.loads(row.knowledge_point_ids_json)
    except json.JSONDecodeError:
        point_ids = []
    if not isinstance(point_ids, list):
        point_ids = []
    return {
        "id": row.id,
        "session_id": row.session_id,
        "role": row.role,
        "content": row.content,
        "knowledge_point_ids": point_ids,
        "created_at": row.created_at,
    }

