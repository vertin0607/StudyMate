"""知识点掌握度。未检测的知识点不会被标成已掌握。"""

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.database import get_session
from app.services import quiz_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("")
def list_knowledge(goal_id: int | None = Query(default=None, ge=1), session: Session = Depends(get_session)) -> dict:
    return quiz_service.list_knowledge(session, goal_id)


@router.get("/{knowledge_id}/history")
def knowledge_history(knowledge_id: int, session: Session = Depends(get_session)) -> dict:
    return quiz_service.knowledge_history(session, knowledge_id)


@router.get("/{knowledge_id}")
def knowledge_detail(knowledge_id: int, session: Session = Depends(get_session)) -> dict:
    return quiz_service.get_knowledge(session, knowledge_id)
