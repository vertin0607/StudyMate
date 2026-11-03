"""健康检查。用来确认后端进程已经启动。"""

from datetime import datetime

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    """返回服务状态和服务器本地时间。不访问数据库，也不调用 AI。"""
    # 日期由服务器时钟生成。后续每日计划也沿用这个原则，不交给模型决定。
    now = datetime.now().astimezone()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "phase": 1,
        "server_time": now.isoformat(timespec="seconds"),
    }
