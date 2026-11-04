"""保存代码草稿和提交记录。不调用模型，也不运行代码。"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, delete, select

from app.models.judge import ProblemJudgeCaseResult, ProblemJudgeResult
from app.models.submission import ProblemCodeDraft, ProblemSubmission
from app.schemas.submission import DraftWrite, SubmissionWrite
from app.services import goal_service, problem_service

UNJUDGED = "unjudged"
UNJUDGED_MESSAGE = "代码已提交，尚未判题"


def get_draft(session: Session, problem_id: int) -> dict:
    problem = problem_service._owned_problem(session, problem_id)
    user = goal_service.ensure_local_user(session)
    row = _find_draft(session, user.id, problem.id)
    if row is None:
        return {"problem_id": problem.id, "language": "cpp", "source_code": "", "updated_at": None, "saved": False}
    return _draft_payload(row, saved=True)


def save_draft(session: Session, problem_id: int, payload: DraftWrite) -> dict:
    problem = problem_service._owned_problem(session, problem_id)
    user = goal_service.ensure_local_user(session)
    row = _find_draft(session, user.id, problem.id)
    now = datetime.now(timezone.utc)
    if row is None:
        row = ProblemCodeDraft(
            user_id=user.id,
            problem_id=problem.id,
            language=payload.language,
            source_code=payload.source_code,
            created_at=now,
            updated_at=now,
        )
    else:
        row.language = payload.language
        row.source_code = payload.source_code
        row.updated_at = now
    session.add(row)
    goal_service.commit_or_raise(session)
    session.refresh(row)
    return _draft_payload(row, saved=True)


def create_submission(session: Session, problem_id: int, payload: SubmissionWrite) -> dict:
    if not payload.source_code.strip():
        raise HTTPException(status_code=422, detail="代码不能为空")
    problem = problem_service._owned_problem(session, problem_id)
    user = goal_service.ensure_local_user(session)
    row = ProblemSubmission(
        user_id=user.id,
        problem_id=problem.id,
        language=payload.language,
        source_code=payload.source_code,
        status=UNJUDGED,
        submitted_at=datetime.now(timezone.utc),
    )
    session.add(row)
    goal_service.commit_or_raise(session)
    session.refresh(row)
    return _submission_payload(row, include_code=True)


def list_submissions(session: Session, problem_id: int) -> dict:
    problem = problem_service._owned_problem(session, problem_id)
    user = goal_service.ensure_local_user(session)
    rows = session.exec(
        select(ProblemSubmission)
        .where(ProblemSubmission.problem_id == problem.id, ProblemSubmission.user_id == user.id)
        .order_by(ProblemSubmission.submitted_at.desc(), ProblemSubmission.id.desc())
    ).all()
    return {"submissions": [_submission_payload(row, include_code=False) for row in rows]}


def get_submission(session: Session, submission_id: int) -> dict:
    return _submission_payload(_owned_submission(session, submission_id), include_code=True)


def delete_submission(session: Session, submission_id: int) -> None:
    row = _owned_submission(session, submission_id)
    result = session.exec(select(ProblemJudgeResult).where(ProblemJudgeResult.submission_id == row.id)).first()
    if result is not None:
        session.exec(delete(ProblemJudgeCaseResult).where(ProblemJudgeCaseResult.judge_result_id == result.id))
        session.delete(result)
    session.delete(row)
    goal_service.commit_or_raise(session)


def _find_draft(session: Session, user_id: int | None, problem_id: int | None) -> ProblemCodeDraft | None:
    return session.exec(
        select(ProblemCodeDraft).where(ProblemCodeDraft.user_id == user_id, ProblemCodeDraft.problem_id == problem_id)
    ).first()


def _owned_submission(session: Session, submission_id: int) -> ProblemSubmission:
    user = goal_service.ensure_local_user(session)
    row = session.get(ProblemSubmission, submission_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    problem_service._owned_problem(session, row.problem_id)
    return row


def _draft_payload(row: ProblemCodeDraft, *, saved: bool) -> dict:
    return {
        "problem_id": row.problem_id,
        "language": row.language,
        "source_code": row.source_code,
        "updated_at": row.updated_at,
        "saved": saved,
    }


def _submission_payload(row: ProblemSubmission, *, include_code: bool) -> dict:
    payload = {
        "id": row.id,
        "problem_id": row.problem_id,
        "language": row.language,
        "status": row.status,
        "code_length": len(row.source_code),
        "submitted_at": row.submitted_at,
        "judged": False,
        "message": UNJUDGED_MESSAGE,
    }
    if include_code:
        payload["source_code"] = row.source_code
    return payload
