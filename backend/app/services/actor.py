"""当前请求对应的登录用户。只接受会话依赖写入的用户编号。"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

from fastapi import HTTPException
from sqlmodel import Session

from app.models.user import User

_actor_id: ContextVar[int | None] = ContextVar("studymate_actor_id", default=None)


def set_actor(user_id: int) -> Token[int | None]:
    return _actor_id.set(user_id)


def reset_actor(token: Token[int | None]) -> None:
    _actor_id.reset(token)


def acting_user(session: Session) -> User:
    """读取本请求已验证的登录用户。不会创建 local，也不读取客户端传来的 user_id。"""
    user_id = _actor_id.get()
    if user_id is None:
        stored = session.info.get("actor_id")
        user_id = stored if isinstance(stored, int) else None
    if user_id is None:
        raise HTTPException(status_code=401, detail="尚未登录")
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="登录已失效")
    return user


@contextmanager
def acting_as(user_id: int) -> Iterator[None]:
    token = set_actor(user_id)
    try:
        yield
    finally:
        reset_actor(token)
