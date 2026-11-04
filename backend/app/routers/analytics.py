"""首页学习效果。只统计已经保存的任务和检测。"""

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.database import get_session
from app.services import diagnosis_rules, diagnosis_service, growth_service, quiz_service, review_service

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/diagnosis-sources")
def diagnosis_sources(session: Session = Depends(get_session)) -> dict:
    return diagnosis_service.snapshot(session)


@router.get("/diagnosis")
def diagnosis(goal_id: int | None = Query(default=None, ge=1), session: Session = Depends(get_session)) -> dict:
    return diagnosis_rules.diagnose(session, goal_id)


@router.get("/growth")
def learning_growth(
    goal_id: int | None = Query(default=None, ge=1),
    days: int = Query(default=30),
    session: Session = Depends(get_session),
) -> dict:
    return growth_service.growth(session, goal_id, days)


@router.get("/analytics")
def learning_analytics(session: Session = Depends(get_session)) -> dict:
    return quiz_service.analytics(session)


@router.get("/trends")
def learning_trends(knowledge_id: int | None = Query(default=None, ge=1), session: Session = Depends(get_session)) -> dict:
    return review_service.trends(session, knowledge_id)


@router.get("/forgetting-risk")
def forgetting_risk(session: Session = Depends(get_session)) -> dict:
    return review_service.risk_report(session)


@router.get("/review-statistics")
def review_statistics(session: Session = Depends(get_session)) -> dict:
    return review_service.review_statistics(session)
