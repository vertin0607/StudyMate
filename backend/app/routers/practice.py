"""跨题目的练习历史。读取时不调用模型。"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.services import practice_service

router = APIRouter(prefix="/practice", tags=["practice"])


@router.get("/history")
def practice_history(session: Session = Depends(get_session)) -> dict:
    return practice_service.all_practice_history(session)
