"""知识检测接口。正确答案在提交前不会返回。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.database import get_session
from app.schemas.quiz import QuizGenerateRequest, QuizSubmitRequest
from app.services import quiz_service
from app.services.ai.errors import AIError

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


def _call(action):
    try:
        return action()
    except AIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None


@router.get("/history")
def quiz_history(goal_id: int = Query(ge=1), session: Session = Depends(get_session)) -> dict:
    return quiz_service.history(session, goal_id)


@router.post("/generate")
def generate_quiz(payload: QuizGenerateRequest, session: Session = Depends(get_session)) -> dict:
    return _call(lambda: quiz_service.generate_for_task(session, payload.task_id))


@router.get("/{quiz_id}/result")
def quiz_result(quiz_id: int, session: Session = Depends(get_session)) -> dict:
    return quiz_service.get_result(session, quiz_id)


@router.get("/{quiz_id}")
def quiz_detail(quiz_id: int, session: Session = Depends(get_session)) -> dict:
    return quiz_service.get_quiz(session, quiz_id)


@router.post("/{quiz_id}/submit")
def submit_quiz(quiz_id: int, payload: QuizSubmitRequest, session: Session = Depends(get_session)) -> dict:
    answers = [item.model_dump() for item in payload.answers]
    return _call(lambda: quiz_service.submit_quiz(session, quiz_id, answers))
