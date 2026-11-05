"""用户注册、会话和 CSRF。不改动 local 的历史学习数据。"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.config import settings
from app.models.user import User, UserSession, utc_now
from app.schemas.auth import LoginRequest, RegisterRequest, UserPublic

SESSION_COOKIE = "studymate_session"
CSRF_COOKIE = "studymate_csrf"
CSRF_HEADER = "X-CSRF-Token"

_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("studymate-unused-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str | None) -> bool:
    """没有哈希时也走一次校验，避免用响应时间判断用户是否存在。"""
    candidate = password_hash or _DUMMY_HASH
    try:
        matched = _hasher.verify(candidate, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    return bool(password_hash) and matched


def public_user(user: User) -> UserPublic:
    return UserPublic(
        id=user.id or 0,
        username=user.username,
        email=user.email,
        nickname=user.nickname,
        avatar=user.avatar,
        is_active=user.is_active,
        created_at=_iso(user.created_at),
        updated_at=_iso(user.updated_at),
    )


def issue_csrf(response: Response) -> str:
    token = secrets.token_urlsafe(32)
    _set_csrf_cookie(response, token)
    return token


def verify_csrf(request: Request) -> None:
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get(CSRF_HEADER, "")
    if not cookie or not header or len(cookie) != len(header) or not secrets.compare_digest(cookie, header):
        raise HTTPException(status_code=403, detail="缺少或无效的 CSRF 令牌")


def register_user(session: Session, payload: RegisterRequest) -> User:
    if session.exec(select(User).where(User.username == payload.username)).first() is not None:
        raise HTTPException(status_code=409, detail="用户名已被使用")
    if payload.email is not None and session.exec(select(User).where(User.email == payload.email)).first() is not None:
        raise HTTPException(status_code=409, detail="邮箱已被使用")
    now = utc_now()
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname or payload.username,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="用户名或邮箱已被使用") from None
    session.refresh(user)
    return user


def authenticate(session: Session, payload: LoginRequest) -> User:
    user = session.exec(select(User).where(User.username == payload.username)).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用")
    return user


def start_session(session: Session, user: User, response: Response) -> None:
    """签发新会话。调用方不能指定用户编号，用户来自注册或密码校验结果。"""
    if user.id is None:
        raise HTTPException(status_code=500, detail="创建会话失败")
    now = utc_now()
    expires_at = now + timedelta(days=max(1, settings.session_ttl_days))
    token = secrets.token_urlsafe(32)
    session.add(
        UserSession(
            user_id=user.id,
            session_token_hash=hash_token(token),
            created_at=now,
            expires_at=expires_at,
            last_used_at=now,
        )
    )
    session.commit()
    _set_session_cookie(response, token, expires_at)
    issue_csrf(response)


def current_user(session: Session, request: Request) -> User:
    """只信任 HttpOnly 会话 Cookie。忽略查询参数、请求体和自行指定用户的请求头。"""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="尚未登录")
    row = session.exec(select(UserSession).where(UserSession.session_token_hash == hash_token(token))).first()
    now = utc_now()
    if row is None or row.revoked_at is not None or _as_utc(row.expires_at) <= now:
        raise HTTPException(status_code=401, detail="登录已失效")
    user = session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="登录已失效")
    row.last_used_at = now
    session.add(row)
    session.commit()
    session.refresh(user)
    return user


def revoke_current_session(session: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        row = session.exec(select(UserSession).where(UserSession.session_token_hash == hash_token(token))).first()
        if row is not None and row.revoked_at is None:
            row.revoked_at = utc_now()
            session.add(row)
            session.commit()
    _clear_cookie(response, SESSION_COOKIE, httponly=True)
    _clear_cookie(response, CSRF_COOKIE, httponly=False)


def _set_session_cookie(response: Response, token: str, expires_at: datetime) -> None:
    secure, samesite = _cookie_flags()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
        max_age=max(1, int((_as_utc(expires_at) - utc_now()).total_seconds())),
    )


def _set_csrf_cookie(response: Response, token: str) -> None:
    secure, samesite = _cookie_flags()
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        httponly=False,
        secure=secure,
        samesite=samesite,
        path="/",
        max_age=max(1, settings.session_ttl_days) * 24 * 60 * 60,
    )


def _clear_cookie(response: Response, key: str, *, httponly: bool) -> None:
    secure, samesite = _cookie_flags()
    response.delete_cookie(key, path="/", secure=secure, httponly=httponly, samesite=samesite)


def _cookie_flags() -> tuple[bool, str]:
    samesite = settings.cookie_samesite if settings.cookie_samesite in {"lax", "strict", "none"} else "lax"
    secure = settings.cookie_secure or samesite == "none"
    return secure, samesite


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _as_utc(value).isoformat()
