"""题目讲解和复习知识点讲解。调用模型前校验所有权，讲解本身不改掌握度。"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.explain import KnowledgeExplainMessage, KnowledgeExplainSession, QuestionExplanation
from app.models.knowledge import KnowledgePoint
from app.models.quiz import Quiz, QuizAnswer, QuizQuestion
from app.services import goal_service
from app.services.actor import acting_user
from app.services.ai.deepseek_client import complete_json
from app.services.ai.errors import AIError
from app.services.ai.explain_parser import parse_followup, parse_knowledge_explain, parse_question_explain
from app.services.ai.prompt_builder import MAX_ATTEMPTS, build_repair_messages
from app.services.tutor_service import teaching_strategy

logger = logging.getLogger(__name__)
PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
QUESTION_PROMPT = PROMPT_DIR / "question_explain.txt"
KNOWLEDGE_PROMPT = PROMPT_DIR / "knowledge_explain.txt"
FOLLOWUP_PROMPT = PROMPT_DIR / "knowledge_followup.txt"


def explain_question(session: Session, quiz_id: int, question_id: int) -> dict:
    quiz, question, answer, point = _owned_graded_question(session, quiz_id, question_id)
    cached = session.exec(select(QuestionExplanation).where(QuestionExplanation.question_id == question.id)).first()
    if cached is not None:
        return _question_payload(cached)
    content = _generate_question_explain(quiz, question, answer, point)
    now = datetime.now(timezone.utc)
    row = QuestionExplanation(quiz_id=quiz.id, question_id=question.id, content=content, created_at=now)
    session.add(row)
    goal_service.commit_or_raise(session)
    session.refresh(row)
    logger.info("已保存题目讲解 quiz=%s question=%s", quiz.id, question.id)
    return _question_payload(row)


def get_question_explain(session: Session, quiz_id: int, question_id: int) -> dict:
    _owned_graded_question(session, quiz_id, question_id)
    cached = session.exec(select(QuestionExplanation).where(QuestionExplanation.question_id == question_id)).first()
    if cached is None:
        raise HTTPException(status_code=404, detail="还没有生成这道题的讲解")
    return _question_payload(cached)


def get_knowledge_explain(session: Session, schedule_id: int) -> dict:
    schedule, point, goal = _owned_review_point(session, schedule_id)
    row = session.exec(select(KnowledgeExplainSession).where(KnowledgeExplainSession.schedule_id == schedule.id)).first()
    if row is None:
        return {"session_id": None, "knowledge_point_id": point.id, "name": point.name, "messages": []}
    return _session_payload(session, row, point)


def start_knowledge_explain(session: Session, schedule_id: int) -> dict:
    schedule, point, goal = _owned_review_point(session, schedule_id)
    row = _get_or_create_session(session, schedule, point, goal)
    messages = _messages(session, row.id)
    if any(item.role == "assistant" for item in messages):
        return _session_payload(session, row, point)
    content = _generate_knowledge_explain(session, point, goal)
    now = datetime.now(timezone.utc)
    session.add(KnowledgeExplainMessage(session_id=row.id, role="assistant", content=content, created_at=now))
    row.updated_at = now
    session.add(row)
    goal_service.commit_or_raise(session)
    logger.info("已保存知识点讲解 schedule=%s", schedule.id)
    return _session_payload(session, row, point)


def followup_knowledge_explain(session: Session, schedule_id: int, question: str) -> dict:
    text = question.strip()
    if not text:
        raise HTTPException(status_code=422, detail="请先写下要追问的内容")
    schedule, point, goal = _owned_review_point(session, schedule_id)
    row = session.exec(select(KnowledgeExplainSession).where(KnowledgeExplainSession.schedule_id == schedule.id)).first()
    if row is None:
        raise HTTPException(status_code=409, detail="请先生成知识点讲解，再继续追问")
    history = _messages(session, row.id)
    if not any(item.role == "assistant" for item in history):
        raise HTTPException(status_code=409, detail="请先生成知识点讲解，再继续追问")
    now = datetime.now(timezone.utc)
    session.add(KnowledgeExplainMessage(session_id=row.id, role="user", content=text[:2000], created_at=now))
    reply = _generate_followup(session, point, goal, [*history, KnowledgeExplainMessage(role="user", content=text)])
    session.add(KnowledgeExplainMessage(session_id=row.id, role="assistant", content=reply, created_at=now))
    row.updated_at = now
    session.add(row)
    goal_service.commit_or_raise(session)
    return _session_payload(session, row, point)


def _owned_graded_question(session: Session, quiz_id: int, question_id: int) -> tuple[Quiz, QuizQuestion, QuizAnswer, KnowledgePoint]:
    from app.services.quiz_service import _get_quiz

    quiz = _get_quiz(session, quiz_id)
    if quiz.status != "completed":
        raise HTTPException(status_code=409, detail="提交检测后才能查看题目讲解")
    question = session.get(QuizQuestion, question_id)
    if question is None or question.quiz_id != quiz.id:
        raise HTTPException(status_code=404, detail="题目不存在")
    answer = session.exec(select(QuizAnswer).where(QuizAnswer.question_id == question.id)).first()
    if answer is None:
        raise HTTPException(status_code=409, detail="这道题还没有作答记录")
    point = session.get(KnowledgePoint, question.knowledge_point_id)
    if point is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    goal_service.get_goal(session, point.goal_id)
    return quiz, question, answer, point


def _owned_review_point(session: Session, schedule_id: int):
    from app.services.review_service import _owned_schedule

    schedule = _owned_schedule(session, schedule_id)
    point = session.get(KnowledgePoint, schedule.knowledge_point_id)
    if point is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    goal = goal_service.get_goal(session, schedule.goal_id)
    return schedule, point, goal


def _get_or_create_session(session: Session, schedule, point: KnowledgePoint, goal) -> KnowledgeExplainSession:
    row = session.exec(select(KnowledgeExplainSession).where(KnowledgeExplainSession.schedule_id == schedule.id)).first()
    if row is not None:
        return row
    now = datetime.now(timezone.utc)
    row = KnowledgeExplainSession(
        user_id=acting_user(session).id,
        goal_id=goal.id,
        schedule_id=schedule.id,
        knowledge_point_id=point.id,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return row


def _generate_question_explain(quiz: Quiz, question: QuizQuestion, answer: QuizAnswer, point: KnowledgePoint) -> str:
    payload = {
        "knowledge_point": {
            "id": point.id,
            "name": point.name,
            "description": point.description,
            "mastery_level": point.mastery_level,
        },
        "question": {
            "type": question.question_type,
            "difficulty": question.difficulty,
            "stem": question.stem,
            "options": json.loads(question.options_json),
            "correct_answer": question.correct_answer,
            "scoring_guide": question.explanation,
        },
        "user": {
            "answer": answer.user_answer,
            "is_correct": answer.is_correct,
            "score": answer.score,
            "error_reason": answer.error_reason,
        },
        "quiz_title": quiz.title,
    }
    return _complete(
        QUESTION_PROMPT.read_text(encoding="utf-8"),
        "请讲解这道题：\n" + json.dumps(payload, ensure_ascii=False),
        parse_question_explain,
        "题目讲解未通过校验",
    )


def _generate_knowledge_explain(session: Session, point: KnowledgePoint, goal) -> str:
    from app.services.review_service import memory_profile

    memory = memory_profile(session, point)
    assessed = memory["mastery_assessed"]
    mastery = memory["mastery_level"]
    depth, strategy = teaching_strategy(mastery if assessed else None, assessed)
    payload = {
        "goal": {"title": goal.title, "description": goal.description},
        "knowledge_point": {
            "id": point.id,
            "name": point.name,
            "description": point.description,
            "difficulty": point.difficulty,
            "status": point.status,
            "mastery_level": mastery,
            "mastery_assessed": assessed,
        },
        "memory": {
            "study_count": memory["study_count"],
            "quiz_count": memory["quiz_count"],
            "latest_score": memory["latest_score"],
            "weak_points": memory["weak_points"][:5],
            "status_label": memory["status_label"],
        },
        "teaching_strategy": {"depth": depth, "instruction": strategy},
    }
    return _complete(
        KNOWLEDGE_PROMPT.read_text(encoding="utf-8"),
        "请讲解这个知识点：\n" + json.dumps(payload, ensure_ascii=False),
        parse_knowledge_explain,
        "知识点讲解未通过校验",
    )


def _generate_followup(session: Session, point: KnowledgePoint, goal, history: list[KnowledgeExplainMessage]) -> str:
    from app.services.review_service import memory_profile

    memory = memory_profile(session, point)
    assessed = memory["mastery_assessed"]
    mastery = memory["mastery_level"]
    depth, strategy = teaching_strategy(mastery if assessed else None, assessed)
    payload = {
        "goal": {"title": goal.title},
        "knowledge_point": {"id": point.id, "name": point.name, "description": point.description},
        "teaching_strategy": {"depth": depth, "instruction": strategy},
        "history": [{"role": item.role, "content": item.content[:2000]} for item in history[-12:]],
    }
    return _complete(
        FOLLOWUP_PROMPT.read_text(encoding="utf-8"),
        "请继续回答：\n" + json.dumps(payload, ensure_ascii=False),
        parse_followup,
        "追问回复未通过校验",
    )


def _complete(system: str, user: str, parser, fallback: str) -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    last_error = fallback
    raw = ""
    for attempt in range(MAX_ATTEMPTS):
        try:
            raw = complete_json(messages, max_tokens=2000)
            return parser(raw)
        except AIError as exc:
            last_error = exc.message
            logger.warning("讲解未通过：%s", last_error)
            if attempt + 1 >= MAX_ATTEMPTS:
                break
            if raw:
                messages = build_repair_messages(messages, raw, exc.message)
    raise AIError(last_error, status_code=502)


def _messages(session: Session, session_id: int | None) -> list[KnowledgeExplainMessage]:
    if session_id is None:
        return []
    return list(
        session.exec(
            select(KnowledgeExplainMessage)
            .where(KnowledgeExplainMessage.session_id == session_id)
            .order_by(KnowledgeExplainMessage.created_at, KnowledgeExplainMessage.id)
        ).all()
    )


def _question_payload(row: QuestionExplanation) -> dict:
    return {"question_id": row.question_id, "quiz_id": row.quiz_id, "content": row.content, "created_at": row.created_at}


def _session_payload(session: Session, row: KnowledgeExplainSession, point: KnowledgePoint) -> dict:
    return {
        "session_id": row.id,
        "knowledge_point_id": point.id,
        "name": point.name,
        "messages": [
            {"id": item.id, "role": item.role, "content": item.content, "created_at": item.created_at}
            for item in _messages(session, row.id)
        ],
    }
