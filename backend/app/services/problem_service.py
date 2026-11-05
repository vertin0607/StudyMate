"""题库保存、测试数据和个人笔记。只有分析接口会调用模型。"""

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlmodel import Session, delete, select

from app.models.judge import ProblemJudgeCaseResult, ProblemJudgeResult
from app.models.practice import ProblemLearningStatus, ProblemPracticeRecord, ProblemWrongRecord
from app.models.problem import Problem, ProblemNote, ProblemTestCase, ProblemTopic, ProblemTopicLink
from app.models.recommendation import TrainingRecommendation
from app.models.submission import ProblemCodeDraft, ProblemSubmission
from app.schemas.problem import ClassificationUpdate, NoteWrite, ProblemWrite, TestCaseInput, TopicConfirm
from app.services import goal_service
from app.services.actor import acting_user
from app.services.ai.deepseek_client import complete_json
from app.services.ai.errors import AIError
from app.services.ai.prompt_builder import MAX_ATTEMPTS, build_repair_messages
from app.services.problem_catalog import CATALOG_NAMES, TOPIC_CATALOG
from app.services.problem_parser import parse_problem_analysis

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "problem_analysis.txt"


def list_problems(
    session: Session,
    *,
    keyword: str = "",
    course: str = "",
    topic_id: int | None = None,
    difficulty: str = "",
    source_platform: str = "",
    analysis_status: str = "",
) -> dict:
    user = acting_user(session)
    _ensure_topics(session, user.id)
    rows = session.exec(select(Problem).where(Problem.user_id == user.id).order_by(Problem.created_at.desc())).all()
    if topic_id is not None:
        linked = {
            link.problem_id
            for link in session.exec(select(ProblemTopicLink).where(ProblemTopicLink.topic_id == topic_id)).all()
        }
        rows = [row for row in rows if row.id in linked]
    keyword = keyword.strip()
    items = []
    for row in rows:
        if course and row.course != course:
            continue
        if difficulty and row.difficulty != difficulty:
            continue
        if source_platform and row.source_platform != source_platform:
            continue
        if analysis_status and row.analysis_status != analysis_status:
            continue
        if keyword and keyword not in row.title and keyword not in row.source_problem_id:
            continue
        items.append(_summary(session, row))
    return {"problems": items}


def statistics(session: Session) -> dict:
    user = acting_user(session)
    rows = session.exec(select(Problem).where(Problem.user_id == user.id)).all()
    return {
        "total": len(rows),
        "analyzed": sum(1 for row in rows if row.analysis_status == "completed"),
        "pending": sum(1 for row in rows if row.analysis_status == "pending"),
        "failed": sum(1 for row in rows if row.analysis_status == "failed"),
        "passed": 0,
        "to_review": 0,
    }


def topics(session: Session) -> dict:
    user = acting_user(session)
    _ensure_topics(session, user.id)
    rows = session.exec(select(ProblemTopic).where(ProblemTopic.user_id == user.id).order_by(ProblemTopic.id)).all()
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row.category, []).append({"id": row.id, "name": row.name, "category": row.category})
    return {"categories": [{"name": name, "topics": items} for name, items in grouped.items()]}


def delete_topic(session: Session, topic_id: int) -> None:
    """删除题库知识点及其关联。不删除题目，也不删除学习目标里的知识点。"""
    user = acting_user(session)
    topic = session.get(ProblemTopic, topic_id)
    if topic is None or topic.user_id != user.id:
        raise HTTPException(status_code=404, detail="题库知识点不存在")
    from app.services.topic_link_service import delete_for_topics

    delete_for_topics(session, [topic.id], topic.user_id)
    session.exec(
        delete(TrainingRecommendation).where(
            TrainingRecommendation.problem_topic_id == topic.id,
            TrainingRecommendation.user_id == topic.user_id,
        )
    )
    owned_problem_ids = list(session.exec(select(Problem.id).where(Problem.user_id == user.id)).all())
    if owned_problem_ids:
        session.exec(
            delete(ProblemTopicLink).where(
                ProblemTopicLink.topic_id == topic.id,
                ProblemTopicLink.problem_id.in_(owned_problem_ids),
            )
        )
    session.delete(topic)
    goal_service.commit_or_raise(session)


def problems_for_topic(session: Session, topic_id: int) -> dict:
    user = acting_user(session)
    topic = session.get(ProblemTopic, topic_id)
    if topic is None or topic.user_id != user.id:
        raise HTTPException(status_code=404, detail="知识点不存在")
    return {"topic": {"id": topic.id, "name": topic.name, "category": topic.category}, **list_problems(session, topic_id=topic_id)}


def import_problem(session: Session, payload: ProblemWrite) -> dict:
    if payload.status == "ready" and not payload.description.strip():
        raise HTTPException(status_code=422, detail="正式导入时题目描述不能为空")
    _reject_exact_duplicate(session, payload.source_platform, payload.source_problem_id, None)
    problem = _insert_problem(session, payload)
    warning = _title_warning(session, problem)
    return {"problem": get_problem(session, problem.id), "duplicate_warning": warning}


def create_problem(session: Session, payload: ProblemWrite) -> dict:
    return import_problem(session, payload)


def get_problem(session: Session, problem_id: int) -> dict:
    problem = _owned_problem(session, problem_id)
    payload = _summary(session, problem)
    payload.update(
        {
            "description": problem.description,
            "input_description": problem.input_description,
            "output_description": problem.output_description,
            "sample_input": problem.sample_input,
            "sample_output": problem.sample_output,
            "constraints": problem.constraints,
            "note": problem.note,
            "status": problem.status,
            "analysis_error": problem.analysis_error,
            "classification_locked": problem.classification_locked,
            "analysis": _analysis(problem),
            "test_cases": [_case_payload(item) for item in _cases(session, problem.id)],
            "note_record": _note_payload(session, problem),
        }
    )
    return payload


def update_problem(session: Session, problem_id: int, payload: ProblemWrite) -> dict:
    problem = _owned_problem(session, problem_id)
    if payload.status == "ready" and not payload.description.strip():
        raise HTTPException(status_code=422, detail="正式导入时题目描述不能为空")
    _reject_exact_duplicate(session, payload.source_platform, payload.source_problem_id, problem.id)
    _apply_problem_fields(problem, payload)
    problem.updated_at = datetime.now(timezone.utc)
    session.add(problem)
    goal_service.commit_or_raise(session)
    return get_problem(session, problem.id)


def delete_problem(session: Session, problem_id: int) -> None:
    problem = _owned_problem(session, problem_id)
    owner_id = problem.user_id
    judge_ids = [
        row.id
        for row in session.exec(
            select(ProblemJudgeResult).where(ProblemJudgeResult.problem_id == problem.id, ProblemJudgeResult.user_id == owner_id)
        ).all()
    ]
    if judge_ids:
        session.exec(delete(ProblemJudgeCaseResult).where(ProblemJudgeCaseResult.judge_result_id.in_(judge_ids)))
    session.exec(delete(ProblemJudgeResult).where(ProblemJudgeResult.problem_id == problem.id, ProblemJudgeResult.user_id == owner_id))
    session.exec(delete(ProblemWrongRecord).where(ProblemWrongRecord.problem_id == problem.id, ProblemWrongRecord.user_id == owner_id))
    session.exec(delete(ProblemPracticeRecord).where(ProblemPracticeRecord.problem_id == problem.id, ProblemPracticeRecord.user_id == owner_id))
    session.exec(delete(ProblemLearningStatus).where(ProblemLearningStatus.problem_id == problem.id, ProblemLearningStatus.user_id == owner_id))
    session.exec(delete(ProblemCodeDraft).where(ProblemCodeDraft.problem_id == problem.id, ProblemCodeDraft.user_id == owner_id))
    session.exec(delete(ProblemSubmission).where(ProblemSubmission.problem_id == problem.id, ProblemSubmission.user_id == owner_id))
    session.exec(delete(ProblemTestCase).where(ProblemTestCase.problem_id == problem.id))
    session.exec(delete(ProblemTopicLink).where(ProblemTopicLink.problem_id == problem.id))
    session.exec(delete(ProblemNote).where(ProblemNote.problem_id == problem.id, ProblemNote.user_id == owner_id))
    session.exec(delete(TrainingRecommendation).where(TrainingRecommendation.problem_id == problem.id, TrainingRecommendation.user_id == owner_id))
    session.delete(problem)
    goal_service.commit_or_raise(session)


def add_case(session: Session, problem_id: int, payload: TestCaseInput) -> dict:
    problem = _owned_problem(session, problem_id)
    row = _new_case(problem.id, payload)
    session.add(row)
    goal_service.commit_or_raise(session)
    session.refresh(row)
    return _case_payload(row)


def update_case(session: Session, problem_id: int, case_id: int, payload: TestCaseInput) -> dict:
    _owned_problem(session, problem_id)
    row = _owned_case(session, problem_id, case_id)
    row.name = payload.name.strip()
    row.input_data = payload.input_data
    row.expected_output = payload.expected_output
    row.case_type = payload.case_type
    row.is_public = payload.is_public
    row.note = payload.note
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    goal_service.commit_or_raise(session)
    session.refresh(row)
    return _case_payload(row)


def delete_case(session: Session, problem_id: int, case_id: int) -> None:
    _owned_problem(session, problem_id)
    row = _owned_case(session, problem_id, case_id)
    session.delete(row)
    goal_service.commit_or_raise(session)


def list_cases(session: Session, problem_id: int) -> dict:
    _owned_problem(session, problem_id)
    return {"test_cases": [_case_payload(item) for item in _cases(session, problem_id)]}


def save_note(session: Session, problem_id: int, payload: NoteWrite) -> dict:
    problem = _owned_problem(session, problem_id)
    note = session.exec(select(ProblemNote).where(ProblemNote.problem_id == problem.id)).first()
    now = datetime.now(timezone.utc)
    if note is None:
        note = ProblemNote(problem_id=problem.id, user_id=problem.user_id, created_at=now)
    note.content = payload.content
    note.solution_idea = payload.solution_idea
    note.updated_at = now
    session.add(note)
    goal_service.commit_or_raise(session)
    session.refresh(note)
    return _note_payload(session, problem)


def get_note(session: Session, problem_id: int) -> dict:
    problem = _owned_problem(session, problem_id)
    return _note_payload(session, problem)


def update_classification(session: Session, problem_id: int, payload: ClassificationUpdate) -> dict:
    problem = _owned_problem(session, problem_id)
    user = acting_user(session)
    topic_ids = {topic.id for topic in session.exec(select(ProblemTopic).where(ProblemTopic.user_id == user.id)).all()}
    for link in payload.links:
        if link.topic_id not in topic_ids:
            raise HTTPException(status_code=404, detail="知识点不存在")
    session.exec(delete(ProblemTopicLink).where(ProblemTopicLink.problem_id == problem.id))
    for link in payload.links:
        session.add(ProblemTopicLink(problem_id=problem.id, topic_id=link.topic_id, relevance=link.relevance, reason=link.reason))
    problem.course = payload.course.strip()
    problem.difficulty = payload.difficulty
    problem.classification_locked = True
    problem.updated_at = datetime.now(timezone.utc)
    session.add(problem)
    goal_service.commit_or_raise(session)
    return get_problem(session, problem.id)


def confirm_topic(session: Session, problem_id: int, payload: TopicConfirm) -> dict:
    problem = _owned_problem(session, problem_id)
    user = acting_user(session)
    if payload.name in CATALOG_NAMES:
        topic = session.exec(
            select(ProblemTopic).where(ProblemTopic.user_id == user.id, ProblemTopic.name == payload.name)
        ).one()
    else:
        topic = session.exec(
            select(ProblemTopic).where(ProblemTopic.user_id == user.id, ProblemTopic.name == payload.name)
        ).first()
        if topic is None:
            topic = ProblemTopic(user_id=user.id, category="自定义", name=payload.name)
            session.add(topic)
            session.flush()
    exists = session.exec(
        select(ProblemTopicLink).where(ProblemTopicLink.problem_id == problem.id, ProblemTopicLink.topic_id == topic.id)
    ).first()
    if exists is None:
        session.add(
            ProblemTopicLink(problem_id=problem.id, topic_id=topic.id, relevance=payload.relevance, reason=payload.reason)
        )
    problem.classification_locked = True
    problem.updated_at = datetime.now(timezone.utc)
    session.add(problem)
    goal_service.commit_or_raise(session)
    return get_problem(session, problem.id)


def analyze_problem(session: Session, problem_id: int) -> dict:
    problem = _owned_problem(session, problem_id)
    if not problem.description.strip():
        raise HTTPException(status_code=400, detail="题目描述为空，不能分析")
    user = acting_user(session)
    _ensure_topics(session, user.id)
    original = {
        "description": problem.description,
        "sample_input": problem.sample_input,
        "sample_output": problem.sample_output,
    }
    notes_before = problem.note
    try:
        analysis = _request_analysis(problem)
    except (AIError, ValueError) as exc:
        message = exc.message if isinstance(exc, AIError) else str(exc)
        status_code = exc.status_code if isinstance(exc, AIError) else 502
        problem.analysis_status = "failed"
        problem.analysis_error = message[:500]
        problem.updated_at = datetime.now(timezone.utc)
        session.add(problem)
        goal_service.commit_or_raise(session)
        raise HTTPException(status_code=status_code, detail=message) from None
    if problem.description != original["description"] or problem.sample_input != original["sample_input"]:
        raise HTTPException(status_code=500, detail="分析不能改写原题")
    problem.ai_analysis_json = json.dumps(analysis, ensure_ascii=False)
    problem.analysis_status = "completed"
    problem.analysis_error = ""
    problem.note = notes_before
    if not problem.classification_locked:
        problem.course = analysis["course"]
        problem.difficulty = analysis["difficulty"]
        _replace_links(session, problem, analysis)
    problem.updated_at = datetime.now(timezone.utc)
    session.add(problem)
    goal_service.commit_or_raise(session)
    return get_problem(session, problem.id)


def _request_analysis(problem: Problem) -> dict:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    payload = {
        "title": problem.title,
        "description": problem.description,
        "input_description": problem.input_description,
        "output_description": problem.output_description,
        "constraints": problem.constraints,
        "catalog": sorted(CATALOG_NAMES),
    }
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "请分析这道题：\n" + json.dumps(payload, ensure_ascii=False)},
    ]
    last_error = "分析结果未通过校验"
    raw = ""
    for _attempt in range(MAX_ATTEMPTS):
        raw = complete_json(messages, max_tokens=1600)
        try:
            return parse_problem_analysis(raw)
        except ValueError as exc:
            last_error = str(exc)
            messages = build_repair_messages(messages, raw, last_error)
    raise AIError(last_error, status_code=502)


def _replace_links(session: Session, problem: Problem, analysis: dict) -> None:
    user_topics = {
        topic.name: topic
        for topic in session.exec(select(ProblemTopic).where(ProblemTopic.user_id == problem.user_id)).all()
    }
    session.exec(delete(ProblemTopicLink).where(ProblemTopicLink.problem_id == problem.id))
    for item in analysis["main_knowledge_points"] + analysis["secondary_knowledge_points"]:
        topic = user_topics.get(item["name"])
        if topic is None:
            continue
        session.add(
            ProblemTopicLink(
                problem_id=problem.id,
                topic_id=topic.id,
                relevance=item["relevance"],
                reason=item["reason"],
            )
        )


def _insert_problem(session: Session, payload: ProblemWrite) -> Problem:
    user = acting_user(session)
    _ensure_topics(session, user.id)
    now = datetime.now(timezone.utc)
    problem = Problem(user_id=user.id, created_at=now, updated_at=now)
    _apply_problem_fields(problem, payload)
    session.add(problem)
    session.flush()
    for case in payload.test_cases:
        session.add(_new_case(problem.id, case))
    has_sample_case = any(case.case_type == "sample" for case in payload.test_cases)
    if not has_sample_case and (payload.sample_input or payload.sample_output):
        session.add(
            _new_case(
                problem.id,
                TestCaseInput(
                    name="样例",
                    input_data=payload.sample_input,
                    expected_output=payload.sample_output,
                    case_type="sample",
                    is_public=True,
                ),
            )
        )
    goal_service.commit_or_raise(session)
    session.refresh(problem)
    return problem


def _apply_problem_fields(problem: Problem, payload: ProblemWrite) -> None:
    problem.title = payload.title.strip()
    problem.description = payload.description
    problem.source_platform = payload.source_platform.strip() or "南开大学校内 OJ"
    problem.source_problem_id = payload.source_problem_id.strip()
    problem.source_url = payload.source_url.strip()
    problem.input_description = payload.input_description
    problem.output_description = payload.output_description
    problem.sample_input = payload.sample_input
    problem.sample_output = payload.sample_output
    problem.constraints = payload.constraints
    problem.note = payload.note
    problem.status = payload.status


def _new_case(problem_id: int | None, payload: TestCaseInput) -> ProblemTestCase:
    now = datetime.now(timezone.utc)
    return ProblemTestCase(
        problem_id=problem_id,
        name=payload.name.strip(),
        input_data=payload.input_data,
        expected_output=payload.expected_output,
        case_type=payload.case_type,
        is_public=payload.is_public,
        note=payload.note,
        created_at=now,
        updated_at=now,
    )


def _reject_exact_duplicate(session: Session, platform: str, source_id: str, current_id: int | None) -> None:
    source_id = source_id.strip()
    if not source_id:
        return
    user = acting_user(session)
    rows = session.exec(
        select(Problem).where(
            Problem.user_id == user.id,
            Problem.source_platform == (platform.strip() or "南开大学校内 OJ"),
            Problem.source_problem_id == source_id,
        )
    ).all()
    if any(row.id != current_id for row in rows):
        raise HTTPException(status_code=409, detail="这个平台和题目编号已经导入过")


def _title_warning(session: Session, problem: Problem) -> bool:
    rows = session.exec(select(Problem).where(Problem.user_id == problem.user_id, Problem.title == problem.title)).all()
    return any(row.id != problem.id for row in rows)


def _ensure_topics(session: Session, user_id: int | None) -> None:
    existing = {topic.name for topic in session.exec(select(ProblemTopic).where(ProblemTopic.user_id == user_id)).all()}
    created = False
    for category, name in TOPIC_CATALOG:
        if name in existing:
            continue
        session.add(ProblemTopic(user_id=user_id, category=category, name=name))
        created = True
    if created:
        goal_service.commit_or_raise(session)


def _owned_problem(session: Session, problem_id: int) -> Problem:
    user = acting_user(session)
    problem = session.get(Problem, problem_id)
    if problem is None or problem.user_id != user.id:
        raise HTTPException(status_code=404, detail="题目不存在")
    return problem


def _owned_case(session: Session, problem_id: int, case_id: int) -> ProblemTestCase:
    row = session.get(ProblemTestCase, case_id)
    if row is None or row.problem_id != problem_id:
        raise HTTPException(status_code=404, detail="测试数据不存在")
    return row


def _cases(session: Session, problem_id: int | None) -> list[ProblemTestCase]:
    return list(session.exec(select(ProblemTestCase).where(ProblemTestCase.problem_id == problem_id).order_by(ProblemTestCase.id)).all())


def _summary(session: Session, problem: Problem) -> dict:
    links = session.exec(select(ProblemTopicLink).where(ProblemTopicLink.problem_id == problem.id)).all()
    topics = []
    for link in links:
        topic = session.get(ProblemTopic, link.topic_id)
        if topic is None or topic.user_id != problem.user_id:
            continue
        topics.append({"id": link.id, "topic_id": topic.id, "name": topic.name, "relevance": link.relevance, "reason": link.reason})
    return {
        "id": problem.id,
        "title": problem.title,
        "source_platform": problem.source_platform,
        "source_problem_id": problem.source_problem_id,
        "source_url": problem.source_url,
        "difficulty": problem.difficulty,
        "course": problem.course,
        "status": problem.status,
        "analysis_status": problem.analysis_status,
        "learning_status": _learning_status_name(session, problem),
        "created_at": problem.created_at,
        "updated_at": problem.updated_at,
        "topics": topics,
    }


def _learning_status_name(session: Session, problem: Problem) -> str:
    row = session.exec(
        select(ProblemLearningStatus).where(
            ProblemLearningStatus.user_id == problem.user_id,
            ProblemLearningStatus.problem_id == problem.id,
        )
    ).first()
    return row.status if row is not None else "todo"


def _analysis(problem: Problem) -> dict | None:
    if not problem.ai_analysis_json:
        return None
    try:
        data = json.loads(problem.ai_analysis_json)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _note_payload(session: Session, problem: Problem) -> dict:
    note = session.exec(select(ProblemNote).where(ProblemNote.problem_id == problem.id)).first()
    if note is None:
        return {"content": "", "solution_idea": "", "updated_at": None}
    return {"id": note.id, "content": note.content, "solution_idea": note.solution_idea, "updated_at": note.updated_at}


def _case_payload(row: ProblemTestCase) -> dict:
    return {
        "id": row.id,
        "problem_id": row.problem_id,
        "name": row.name,
        "input_data": row.input_data,
        "expected_output": row.expected_output,
        "case_type": row.case_type,
        "is_public": row.is_public,
        "note": row.note,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
