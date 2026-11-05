"""用户注册、会话 Cookie 和 CSRF。使用测试库，不读取正式学习记录。"""

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import settings
from app.database import engine
from app.main import app
from app.models.goal import LearningGoal
from app.models.user import User, UserSession
from app.models.user import utc_now
from app.services.auth_service import CSRF_COOKIE, SESSION_COOKIE, hash_token

client = TestClient(app)


def setup_function() -> None:
    client.cookies.clear()


def _csrf_headers() -> dict[str, str]:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    token = response.json()["csrf_token"]
    assert token
    assert token == client.cookies.get(CSRF_COOKIE)
    return {"X-CSRF-Token": token}


def _register(username: str, password: str = "study1234", email: str | None = None) -> dict:
    payload: dict[str, str] = {"username": username, "password": password}
    if email is not None:
        payload["email"] = email
    response = client.post("/api/auth/register", json=payload, headers=_csrf_headers())
    assert response.status_code == 201, response.text
    return response.json()


def _login(username: str, password: str = "study1234") -> object:
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password, "user_id": 1},
        headers=_csrf_headers(),
    )


def test_local_user_remains() -> None:
    with Session(engine) as session:
        local = session.exec(select(User).where(User.username == "local")).one()

    assert local.id is not None
    assert local.username == "local"
    assert local.password_hash is not None
    assert local.password_hash.startswith("$argon2")
    assert "local1234" not in local.password_hash


def test_register_creates_independent_user() -> None:
    created_goal = client.post(
        "/api/goals",
        json={
            "title": "只属于 local 的目标",
            "description": "新注册用户不能看到这条历史记录。",
            "target_date": "2026-12-31",
            "daily_minutes": 25,
        },
    )
    assert created_goal.status_code == 201
    local_user_id = created_goal.json()["user_id"]

    username = f"user_{uuid.uuid4().hex[:12]}"
    body = _register(username)
    assert body["username"] == username
    assert body["id"] != local_user_id
    assert body["id"] != 1 or local_user_id != body["id"]
    assert "password_hash" not in body
    assert "session_token" not in body
    assert SESSION_COOKIE not in response_text(body)

    with Session(engine) as session:
        created = session.exec(select(User).where(User.username == username)).one()
        owned = session.exec(select(LearningGoal).where(LearningGoal.user_id == created.id)).all()
        local_goals = session.exec(select(LearningGoal).where(LearningGoal.user_id == local_user_id)).all()

    assert owned == []
    assert local_goals
    assert created.password_hash is not None
    assert created.password_hash != "study1234"
    assert created.password_hash.startswith("$argon2")
    assert "study1234" not in created.password_hash


def test_duplicate_username_and_email_are_rejected() -> None:
    username = f"user_{uuid.uuid4().hex[:12]}"
    email = f"{uuid.uuid4().hex[:12]}@example.com"
    _register(username, email=email)

    duplicate_name = client.post(
        "/api/auth/register",
        json={"username": username, "password": "study1234"},
        headers=_csrf_headers(),
    )
    assert duplicate_name.status_code == 409

    duplicate_email = client.post(
        "/api/auth/register",
        json={"username": f"user_{uuid.uuid4().hex[:12]}", "password": "study1234", "email": email.upper()},
        headers=_csrf_headers(),
    )
    assert duplicate_email.status_code == 409


def test_login_sets_httponly_cookie_and_me_returns_current_user() -> None:
    username = f"user_{uuid.uuid4().hex[:12]}"
    _register(username)
    client.cookies.clear()

    anonymous = client.get("/api/auth/me", headers={"X-User-Id": "1"}, params={"user_id": 1})
    assert anonymous.status_code == 401

    logged_in = _login(username)
    assert logged_in.status_code == 200
    body = logged_in.json()
    assert body["username"] == username
    assert "password_hash" not in body
    assert "password" not in body
    session_header = _cookie_header(logged_in, SESSION_COOKIE)
    assert "HttpOnly" in session_header
    assert "samesite=lax" in session_header.lower()
    assert "Secure" not in session_header
    csrf_header = _cookie_header(logged_in, CSRF_COOKIE)
    assert "HttpOnly" not in csrf_header
    assert logged_in.json()["id"]
    assert SESSION_COOKIE not in logged_in.text
    assert client.cookies.get(SESSION_COOKIE) not in logged_in.text

    me = client.get("/api/auth/me", headers={"X-User-Id": "1"}, params={"user_id": 1})
    assert me.status_code == 200
    assert me.json()["username"] == username
    assert me.json()["id"] == body["id"]
    assert "password_hash" not in me.json()
    assert "session_token" not in me.json()


def test_wrong_password_is_rejected() -> None:
    username = f"user_{uuid.uuid4().hex[:12]}"
    _register(username)
    response = _login(username, "wrong1234")

    assert response.status_code == 401
    assert SESSION_COOKIE not in response.headers.get("set-cookie", "")


def test_logout_and_expired_or_disabled_session_are_rejected() -> None:
    username = f"user_{uuid.uuid4().hex[:12]}"
    created = _register(username)
    logged_in = _login(username)
    assert logged_in.status_code == 200
    token = client.cookies.get(SESSION_COOKIE)
    assert token

    logout = client.post("/api/auth/logout", headers={"X-CSRF-Token": client.cookies.get(CSRF_COOKIE)})
    assert logout.status_code == 204
    client.cookies.set(SESSION_COOKIE, token)
    again = client.get("/api/auth/me")
    assert again.status_code == 401
    with Session(engine) as session:
        stored = session.exec(select(UserSession).where(UserSession.session_token_hash == hash_token(token))).one()
        assert stored.revoked_at is not None
        assert stored.user_id == created["id"]

    client.cookies.clear()
    assert _login(username).status_code == 200
    with Session(engine) as session:
        row = session.exec(
            select(UserSession)
            .where(UserSession.user_id == created["id"], UserSession.revoked_at.is_(None))
            .order_by(UserSession.id.desc())
        ).first()
        assert row is not None
        row.expires_at = utc_now() - timedelta(seconds=1)
        session.add(row)
        session.commit()
    assert client.get("/api/auth/me").status_code == 401

    client.cookies.clear()
    assert _login(username).status_code == 200
    with Session(engine) as session:
        user = session.get(User, created["id"])
        assert user is not None
        user.is_active = False
        session.add(user)
        session.commit()
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    assert _login(username).status_code == 403


def test_production_cookie_is_secure(monkeypatch) -> None:
    monkeypatch.setattr(settings, "cookie_secure", True)
    response = client.get("/api/auth/csrf")

    assert response.status_code == 200
    header = _cookie_header(response, CSRF_COOKIE)
    assert "Secure" in header
    assert "samesite=lax" in header.lower()


def response_text(body: dict) -> str:
    return str(body)


def _cookie_header(response, name: str) -> str:
    matches = [value for value in response.headers.get_list("set-cookie") if value.startswith(f"{name}=")]
    assert matches, response.headers.get_list("set-cookie")
    return matches[0]
