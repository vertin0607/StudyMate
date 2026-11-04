"""学习计划接口。路由不直接调用模型，也不拼接 SQL。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.database import get_session
from app.schemas.plan import GeneratePlanRequest, RegeneratePlanRequest
from app.services.ai.errors import AIError
from app.services import planning_service

router = APIRouter(prefix="/plans", tags=["plans"])


def _call(action):
    try:
        return action()
    except AIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None


@router.get("/dashboard")
def plan_dashboard(session: Session = Depends(get_session)) -> dict:
    return planning_service.dashboard(session)


@router.get("/today")
def today_plan(
    goal_id: int = Query(ge=1),
    generate: bool = False,
    session: Session = Depends(get_session),
) -> dict:
    # 默认只读取。生成必须显式打开，避免刷新页面重复扣费。
    return _call(lambda: planning_service.get_today(session, goal_id, generate))


@router.post("/generate")
def generate_plan(payload: GeneratePlanRequest, session: Session = Depends(get_session)) -> dict:
    return _call(lambda: planning_service.create_for_goal(session, payload.goal_id))


@router.get("/{plan_id}/history")
def plan_history(plan_id: int, session: Session = Depends(get_session)) -> dict:
    return planning_service.get_history(session, plan_id)


@router.get("/{plan_id}")
def plan_detail(plan_id: int, session: Session = Depends(get_session)) -> dict:
    return planning_service.get_plan_detail(session, plan_id)


@router.post("/{plan_id}/regenerate")
def regenerate_plan(
    plan_id: int,
    payload: RegeneratePlanRequest,
    session: Session = Depends(get_session),
) -> dict:
    return _call(lambda: planning_service.regenerate(session, plan_id, payload.instruction))
