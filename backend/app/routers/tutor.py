"""教学会话。查看历史不调用模型，发送消息才会请求 DeepSeek。"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session

from app.database import get_session
from app.schemas.tutor import MessageCreate, SessionCreate
from app.services import tutor_service
from app.services.ai.errors import AIError

router = APIRouter(prefix="/tutor", tags=["tutor"])


def _call(action):
    try:
        return action()
    except AIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None


@router.post("/sessions", status_code=201)
def create_session(payload: SessionCreate, session: Session = Depends(get_session)) -> dict:
    return tutor_service.create_session(session, payload.goal_id, payload.title)


@router.get("/sessions")
def list_sessions(session: Session = Depends(get_session)) -> dict:
    return tutor_service.list_sessions(session)


@router.get("/sessions/{session_id}")
def session_detail(session_id: int, session: Session = Depends(get_session)) -> dict:
    return tutor_service.get_session_detail(session, session_id)


@router.delete("/sessions/{session_id}", status_code=204)
def remove_session(session_id: int, session: Session = Depends(get_session)) -> Response:
    tutor_service.delete_session(session, session_id)
    return Response(status_code=204)


@router.post("/sessions/{session_id}/messages")
def send_message(session_id: int, payload: MessageCreate, session: Session = Depends(get_session)) -> dict:
    return _call(lambda: tutor_service.send_message(session, session_id, payload.content))
