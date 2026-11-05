"""认证依赖。业务路由通过登录会话确定当前用户。"""

from collections.abc import Generator

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from app.database import get_session
from app.models.user import User
from app.services import auth_service

_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def require_mutation_csrf(request: Request) -> None:
    """修改类请求必须同时带上 CSRF Cookie 和 X-CSRF-Token。GET 不检查。"""
    if request.method.upper() in _UNSAFE:
        auth_service.verify_csrf(request)


def require_csrf(request: Request) -> None:
    auth_service.verify_csrf(request)


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> Generator[User, None, None]:
    user = auth_service.current_user(session, request)
    if user.id is None:
        raise HTTPException(status_code=401, detail="登录已失效")
    # 放在本次请求的 Session 上。同步接口可能跑在另一个线程，不能只靠 ContextVar。
    session.info["actor_id"] = user.id
    yield user
