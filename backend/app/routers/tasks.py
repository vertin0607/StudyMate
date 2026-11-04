"""更新任务完成状态。不会因此修改知识点掌握分。"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.schemas.plan import TaskStatusUpdate
from app.services import planning_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.patch("/{task_id}/status")
def update_task_status(
    task_id: int,
    payload: TaskStatusUpdate,
    session: Session = Depends(get_session),
) -> dict:
    return planning_service.update_task_status(session, task_id, payload.status)
