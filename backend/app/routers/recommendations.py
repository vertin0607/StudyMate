"""训练建议。生成时只读取规则诊断，页面不会调用模型。"""

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.database import get_session
from app.schemas.recommendation import RecommendationStatusUpdate
from app.services import recommendation_service

router = APIRouter(prefix="/learning/recommendations", tags=["recommendations"])


@router.post("/generate")
def generate(goal_id: int | None = Query(default=None, ge=1), session: Session = Depends(get_session)) -> dict:
    return recommendation_service.generate(session, goal_id)


@router.get("")
def list_recommendations(
    goal_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict:
    return recommendation_service.list_recommendations(session, goal_id, status)


@router.get("/{recommendation_id}")
def get_recommendation(recommendation_id: int, session: Session = Depends(get_session)) -> dict:
    return recommendation_service.get_recommendation(session, recommendation_id)


@router.patch("/{recommendation_id}/status")
def update_status(
    recommendation_id: int,
    payload: RecommendationStatusUpdate,
    session: Session = Depends(get_session),
) -> dict:
    return recommendation_service.update_status(session, recommendation_id, payload)
