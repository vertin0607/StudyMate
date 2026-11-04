"""按提交编号读取或删除自己的代码记录。"""

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from sqlmodel import Session

from app.database import get_session
from app.services import submission_service
from app.services.judge import judge_service

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.get("/{submission_id}")
def submission_detail(submission_id: int, session: Session = Depends(get_session)) -> dict:
    return submission_service.get_submission(session, submission_id)


@router.post("/{submission_id}/judge")
def judge_submission(
    submission_id: int, background: BackgroundTasks, session: Session = Depends(get_session)
) -> dict:
    return judge_service.request_judge(session, submission_id, background)


@router.get("/{submission_id}/judge-result")
def judge_result(submission_id: int, session: Session = Depends(get_session)) -> dict:
    return judge_service.get_result(session, submission_id)


@router.post("/{submission_id}/ai-analysis")
def analyze_submission(submission_id: int, session: Session = Depends(get_session)) -> dict:
    return judge_service.analyze_failure(session, submission_id)


@router.delete("/{submission_id}", status_code=204)
def remove_submission(submission_id: int, session: Session = Depends(get_session)) -> Response:
    submission_service.delete_submission(session, submission_id)
    return Response(status_code=204)
