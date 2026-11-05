"""记录练习过程和错题。不判题，不调用模型，不修改掌握度。"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.knowledge import KnowledgePoint
from app.models.practice import ProblemLearningStatus, ProblemPracticeRecord, ProblemWrongRecord
from app.models.problem import Problem, ProblemTopic, ProblemTopicLink
from app.models.quiz import KnowledgeMasteryEvent
from app.models.review import ReviewRecord, ReviewSchedule
from app.models.submission import ProblemSubmission
from app.schemas.practice import LearningStatusUpdate, PracticeComplete, WrongWrite
from app.services import goal_service, problem_service
from app.services.actor import acting_user

MANUAL_STATUSES = {"todo", "attempting", "self_completed"}
JUDGED_STATUSES = {"accepted", "wrong_answer", "compile_error", "time_limit_exceeded", "runtime_error"}
COMPLETION_FLAGS = {
    "independent": (False, False),
    "with_hint": (True, False),
    "with_solution": (False, True),
    "unfinished": (False, False),
}


def get_learning_status(session: Session, problem_id: int) -> dict:
    problem = problem_service._owned_problem(session, problem_id)
    user = acting_user(session)
    row = _status_row(session, user.id, problem.id)
    return _status_payload(problem.id, row)


def update_learning_status(session: Session, problem_id: int, payload: LearningStatusUpdate) -> dict:
    if payload.status not in MANUAL_STATUSES:
        raise HTTPException(status_code=422, detail="不能手动设置系统判题结果")
    problem = problem_service._owned_problem(session, problem_id)
    user = acting_user(session)
    row = _status_row(session, user.id, problem.id)
    if row is not None and row.status in JUDGED_STATUSES:
        raise HTTPException(status_code=409, detail="已有系统判题结果，不能用手动状态覆盖")
    now = datetime.now(timezone.utc)
    if row is None:
        row = ProblemLearningStatus(user_id=user.id, problem_id=problem.id, status=payload.status, created_at=now, updated_at=now)
    else:
        row.status = payload.status
        row.updated_at = now
    session.add(row)
    goal_service.commit_or_raise(session)
    session.refresh(row)
    return _status_payload(problem.id, row)


def start_practice(session: Session, problem_id: int) -> dict:
    problem = problem_service._owned_problem(session, problem_id)
    user = acting_user(session)
    open_row = _open_practice(session, user.id, problem.id)
    if open_row is not None:
        return {"created": False, "record": _practice_payload(open_row)}
    now = datetime.now(timezone.utc)
    row = ProblemPracticeRecord(user_id=user.id, problem_id=problem.id, started_at=now, created_at=now)
    session.add(row)
    status = _status_row(session, user.id, problem.id)
    if status is None or status.status not in JUDGED_STATUSES:
        if status is None:
            status = ProblemLearningStatus(user_id=user.id, problem_id=problem.id, status="attempting", created_at=now, updated_at=now)
        else:
            status.status = "attempting"
            status.updated_at = now
        session.add(status)
    goal_service.commit_or_raise(session)
    session.refresh(row)
    return {"created": True, "record": _practice_payload(row)}


def complete_practice(session: Session, problem_id: int, record_id: int, payload: PracticeComplete) -> dict:
    problem = problem_service._owned_problem(session, problem_id)
    user = acting_user(session)
    row = session.get(ProblemPracticeRecord, record_id)
    if row is None or row.user_id != user.id or row.problem_id != problem.id:
        raise HTTPException(status_code=404, detail="练习记录不存在")
    if row.completed_at is not None:
        raise HTTPException(status_code=409, detail="这次练习已经结束")
    used_hint, viewed_solution = COMPLETION_FLAGS[payload.completion_type]
    row.completed_at = datetime.now(timezone.utc)
    row.completion_type = payload.completion_type
    row.used_hint = used_hint
    row.viewed_solution = viewed_solution
    row.note = payload.note
    session.add(row)
    goal_service.commit_or_raise(session)
    session.refresh(row)
    return _practice_payload(row)


def practice_history(session: Session, problem_id: int) -> dict:
    problem = problem_service._owned_problem(session, problem_id)
    user = acting_user(session)
    rows = session.exec(
        select(ProblemPracticeRecord)
        .where(ProblemPracticeRecord.user_id == user.id, ProblemPracticeRecord.problem_id == problem.id)
        .order_by(ProblemPracticeRecord.id.desc())
    ).all()
    return {"records": [_practice_payload(row) for row in rows]}


def all_practice_history(session: Session) -> dict:
    user = acting_user(session)
    rows = session.exec(
        select(ProblemPracticeRecord).where(ProblemPracticeRecord.user_id == user.id).order_by(ProblemPracticeRecord.id.desc())
    ).all()
    items = []
    for row in rows[:50]:
        problem = session.get(Problem, row.problem_id)
        payload = _practice_payload(row)
        payload["problem_title"] = problem.title if problem is not None else ""
        items.append(payload)
    return {"records": items}


def list_wrong(session: Session, *, topic_id: int | None = None, difficulty: str = "") -> dict:
    user = acting_user(session)
    rows = session.exec(select(ProblemWrongRecord).where(ProblemWrongRecord.user_id == user.id).order_by(ProblemWrongRecord.updated_at.desc())).all()
    items = []
    for row in rows:
        problem = session.get(Problem, row.problem_id)
        if problem is None or problem.user_id != user.id:
            continue
        if difficulty and problem.difficulty != difficulty:
            continue
        topics = _topic_names(session, problem.id)
        if topic_id is not None and topic_id not in {item["topic_id"] for item in topics}:
            continue
        items.append({**_wrong_payload(row), "title": problem.title, "difficulty": problem.difficulty, "topics": topics})
    return {"problems": items}


def add_wrong(session: Session, problem_id: int, payload: WrongWrite) -> dict:
    problem = problem_service._owned_problem(session, problem_id)
    user = acting_user(session)
    exists = _wrong_row(session, user.id, problem.id)
    if exists is not None:
        raise HTTPException(status_code=409, detail="这道题已经在错题里")
    _owned_submission(session, user.id, problem.id, payload.related_submission_id)
    now = datetime.now(timezone.utc)
    row = ProblemWrongRecord(
        user_id=user.id,
        problem_id=problem.id,
        reason_type=payload.reason_type,
        reason_detail=payload.reason_detail,
        related_submission_id=payload.related_submission_id,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    goal_service.commit_or_raise(session)
    session.refresh(row)
    return _wrong_payload(row)


def update_wrong(session: Session, problem_id: int, payload: WrongWrite) -> dict:
    problem = problem_service._owned_problem(session, problem_id)
    user = acting_user(session)
    row = _wrong_row(session, user.id, problem.id)
    if row is None:
        raise HTTPException(status_code=404, detail="错题记录不存在")
    _owned_submission(session, user.id, problem.id, payload.related_submission_id)
    row.reason_type = payload.reason_type
    row.reason_detail = payload.reason_detail
    row.related_submission_id = payload.related_submission_id
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    goal_service.commit_or_raise(session)
    session.refresh(row)
    return _wrong_payload(row)


def delete_wrong(session: Session, problem_id: int) -> None:
    problem = problem_service._owned_problem(session, problem_id)
    user = acting_user(session)
    row = _wrong_row(session, user.id, problem.id)
    if row is None:
        raise HTTPException(status_code=404, detail="错题记录不存在")
    session.delete(row)
    goal_service.commit_or_raise(session)


def practice_statistics(session: Session) -> dict:
    user = acting_user(session)
    problems = session.exec(select(Problem).where(Problem.user_id == user.id)).all()
    statuses = {
        row.problem_id: row.status
        for row in session.exec(select(ProblemLearningStatus).where(ProblemLearningStatus.user_id == user.id)).all()
    }
    counts = {name: 0 for name in ("todo", "attempting", "self_completed", "accepted", "wrong_answer", "compile_error", "time_limit_exceeded", "runtime_error")}
    for problem in problems:
        counts[statuses.get(problem.id, "todo")] = counts.get(statuses.get(problem.id, "todo"), 0) + 1
    practices = session.exec(select(ProblemPracticeRecord).where(ProblemPracticeRecord.user_id == user.id)).all()
    submissions = session.exec(select(ProblemSubmission).where(ProblemSubmission.user_id == user.id)).all()
    wrongs = session.exec(select(ProblemWrongRecord).where(ProblemWrongRecord.user_id == user.id)).all()
    today = datetime.now().astimezone().date()
    return {
        "total": len(problems),
        "todo": counts["todo"],
        "attempting": counts["attempting"],
        "self_completed": counts["self_completed"],
        "accepted": counts["accepted"],
        "wrong_answer": counts["wrong_answer"],
        "compile_error": counts["compile_error"],
        "time_limit_exceeded": counts["time_limit_exceeded"],
        "runtime_error": counts["runtime_error"],
        "wrong_count": len(wrongs),
        "submission_count": len(submissions),
        "practice_total": len(practices),
        "practice_today": sum(1 for row in practices if row.started_at.astimezone().date() == today),
        "started_problems": len({row.problem_id for row in practices}),
    }


def practice_trends(session: Session) -> dict:
    user = acting_user(session)
    today = datetime.now().astimezone().date()
    days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    practices = session.exec(select(ProblemPracticeRecord).where(ProblemPracticeRecord.user_id == user.id)).all()
    submissions = session.exec(select(ProblemSubmission).where(ProblemSubmission.user_id == user.id)).all()
    items = []
    for day in days:
        items.append(
            {
                "date": day.isoformat(),
                "practice_count": sum(1 for row in practices if row.started_at.astimezone().date() == day),
                "submission_count": sum(1 for row in submissions if row.submitted_at.astimezone().date() == day),
            }
        )
    return {"days": items}


def mastery_and_review_counts(session: Session) -> dict:
    """读取掌握度和知识点复习的行数，练习操作不应改变它们。"""
    return {
        "mastery_events": len(session.exec(select(KnowledgeMasteryEvent)).all()),
        "review_schedules": len(session.exec(select(ReviewSchedule)).all()),
        "review_records": len(session.exec(select(ReviewRecord)).all()),
        "knowledge_points": len(session.exec(select(KnowledgePoint)).all()),
    }


def _status_row(session: Session, user_id: int | None, problem_id: int | None) -> ProblemLearningStatus | None:
    return session.exec(
        select(ProblemLearningStatus).where(ProblemLearningStatus.user_id == user_id, ProblemLearningStatus.problem_id == problem_id)
    ).first()


def _open_practice(session: Session, user_id: int | None, problem_id: int | None) -> ProblemPracticeRecord | None:
    return session.exec(
        select(ProblemPracticeRecord).where(
            ProblemPracticeRecord.user_id == user_id,
            ProblemPracticeRecord.problem_id == problem_id,
            ProblemPracticeRecord.completed_at.is_(None),
        )
    ).first()


def _wrong_row(session: Session, user_id: int | None, problem_id: int | None) -> ProblemWrongRecord | None:
    return session.exec(
        select(ProblemWrongRecord).where(ProblemWrongRecord.user_id == user_id, ProblemWrongRecord.problem_id == problem_id)
    ).first()


def _owned_submission(session: Session, user_id: int | None, problem_id: int | None, submission_id: int | None) -> None:
    if submission_id is None:
        return
    row = session.get(ProblemSubmission, submission_id)
    if row is None or row.user_id != user_id or row.problem_id != problem_id:
        raise HTTPException(status_code=404, detail="提交记录不存在")


def _topic_names(session: Session, problem_id: int | None) -> list[dict]:
    links = session.exec(select(ProblemTopicLink).where(ProblemTopicLink.problem_id == problem_id)).all()
    items = []
    for link in links:
        topic = session.get(ProblemTopic, link.topic_id)
        if topic is not None:
            items.append({"topic_id": topic.id, "name": topic.name})
    return items


def _status_payload(problem_id: int | None, row: ProblemLearningStatus | None) -> dict:
    if row is None:
        return {"problem_id": problem_id, "status": "todo", "saved": False, "locked": False, "updated_at": None}
    return {
        "problem_id": problem_id,
        "status": row.status,
        "saved": True,
        "locked": row.status in JUDGED_STATUSES,
        "updated_at": row.updated_at,
    }


def _practice_payload(row: ProblemPracticeRecord) -> dict:
    return {
        "id": row.id,
        "problem_id": row.problem_id,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "completion_type": row.completion_type,
        "used_hint": row.used_hint,
        "viewed_solution": row.viewed_solution,
        "note": row.note,
        "open": row.completed_at is None,
    }


def _wrong_payload(row: ProblemWrongRecord) -> dict:
    return {
        "id": row.id,
        "problem_id": row.problem_id,
        "reason_type": row.reason_type,
        "reason_detail": row.reason_detail,
        "related_submission_id": row.related_submission_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
