"""用户确认题库知识点和学习知识点的关联。打开页面不会自动建立关联。"""

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session

from app.database import get_session
from app.schemas.topic_link import TopicKnowledgeLinkCreate
from app.services import topic_link_service

router = APIRouter(prefix="/learning/topic-links", tags=["topic-links"])


@router.get("")
def list_links(session: Session = Depends(get_session)) -> dict:
    return topic_link_service.list_links(session)


@router.post("", status_code=201)
def create_link(payload: TopicKnowledgeLinkCreate, session: Session = Depends(get_session)) -> dict:
    return topic_link_service.create_link(session, payload)


@router.delete("/{link_id}", status_code=204)
def delete_link(link_id: int, session: Session = Depends(get_session)) -> Response:
    topic_link_service.delete_link(session, link_id)
    return Response(status_code=204)
