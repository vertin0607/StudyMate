"""复习队列。查询不会调用 DeepSeek，开始复习才会出题。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.schemas.review import KnowledgeFollowupRequest, PostponeRequest
from app.services import explain_service, review_service
from app.services.ai.errors import AIError

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _call(action):
    try:
        return action()
    except AIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None


@router.get("/today")
def reviews_today(session: Session = Depends(get_session)) -> dict:
    return review_service.today_queue(session)


@router.get("/upcoming")
def reviews_upcoming(session: Session = Depends(get_session)) -> dict:
    return review_service.list_by_queue(session, "upcoming")


@router.get("/overdue")
def reviews_overdue(session: Session = Depends(get_session)) -> dict:
    return review_service.list_by_queue(session, "overdue")


@router.get("/history")
def reviews_history(session: Session = Depends(get_session)) -> dict:
    return review_service.history(session)


@router.post("/generate")
def generate_queue(session: Session = Depends(get_session)) -> dict:
    """根据已有检测记录整理复习队列，不调用模型。"""
    return review_service.today_queue(session)


@router.get("/{schedule_id}")
def review_detail(schedule_id: int, session: Session = Depends(get_session)) -> dict:
    return review_service.get_review(session, schedule_id)


@router.patch("/{schedule_id}/postpone")
def postpone_review(schedule_id: int, payload: PostponeRequest, session: Session = Depends(get_session)) -> dict:
    return review_service.postpone(session, schedule_id, payload.days)


@router.post("/{schedule_id}/start")
def start_review(schedule_id: int, session: Session = Depends(get_session)) -> dict:
    return _call(lambda: review_service.start_review(session, schedule_id))


@router.get("/{schedule_id}/explain")
def get_knowledge_explain(schedule_id: int, session: Session = Depends(get_session)) -> dict:
    return explain_service.get_knowledge_explain(session, schedule_id)


@router.post("/{schedule_id}/explain")
def start_knowledge_explain(schedule_id: int, session: Session = Depends(get_session)) -> dict:
    return _call(lambda: explain_service.start_knowledge_explain(session, schedule_id))


@router.post("/{schedule_id}/explain/messages")
def followup_knowledge_explain(
    schedule_id: int, payload: KnowledgeFollowupRequest, session: Session = Depends(get_session)
) -> dict:
    return _call(lambda: explain_service.followup_knowledge_explain(session, schedule_id, payload.content))
