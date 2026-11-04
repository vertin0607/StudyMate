"""学习目标接口。数据只通过这里读写，不在页面里访问数据库。"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.schemas.goal import GoalCreate, GoalRead, GoalStatusUpdate, GoalUpdate
from app.services import goal_service

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[GoalRead])
def list_goals(session: Session = Depends(get_session)) -> list:
    return goal_service.list_goals(session)


@router.post("", response_model=GoalRead, status_code=201)
def create_goal(payload: GoalCreate, session: Session = Depends(get_session)) -> object:
    return goal_service.create_goal(session, payload)


@router.get("/{goal_id}", response_model=GoalRead)
def get_goal(goal_id: int, session: Session = Depends(get_session)) -> object:
    return goal_service.get_goal(session, goal_id)


@router.put("/{goal_id}", response_model=GoalRead)
def update_goal(
    goal_id: int,
    payload: GoalUpdate,
    session: Session = Depends(get_session),
) -> object:
    return goal_service.update_goal(session, goal_id, payload)


@router.patch("/{goal_id}/status", response_model=GoalRead)
def update_goal_status(
    goal_id: int,
    payload: GoalStatusUpdate,
    session: Session = Depends(get_session),
) -> object:
    return goal_service.update_goal_status(session, goal_id, payload.status)


@router.delete("/{goal_id}", status_code=204)
def delete_goal(goal_id: int, session: Session = Depends(get_session)) -> None:
    goal_service.delete_goal(session, goal_id)
