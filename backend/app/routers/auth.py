"""注册、登录、退出和当前用户。不接收客户端指定的 user_id。"""

from fastapi import APIRouter, Depends, Request, Response
from sqlmodel import Session

from app.database import get_session
from app.deps import get_current_user, require_csrf
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/csrf")
def csrf_token(response: Response) -> dict:
    """发放双提交 Cookie 使用的 CSRF 令牌。这个接口不登录用户。"""
    token = auth_service.issue_csrf(response)
    return {"csrf_token": token}


@router.post("/register", status_code=201)
def register(
    payload: RegisterRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> dict:
    user = auth_service.register_user(session, payload)
    return auth_service.public_user(user).model_dump()


@router.post("/login")
def login(
    payload: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
    _: None = Depends(require_csrf),
) -> dict:
    user = auth_service.authenticate(session, payload)
    auth_service.start_session(session, user, response)
    return auth_service.public_user(user).model_dump()


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_csrf),
    user: User = Depends(get_current_user),
) -> Response:
    del user
    response = Response(status_code=204)
    auth_service.revoke_current_session(session, request, response)
    return response


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return auth_service.public_user(user).model_dump()
