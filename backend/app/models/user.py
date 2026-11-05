"""用户和登录会话。业务接口仍可使用 local，认证接口使用会话。"""

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, min_length=1, max_length=50)
    email: str | None = Field(default=None, max_length=255, unique=True, index=True)
    # 尚未设置密码的历史账号保持为空。登录时拒绝空哈希，不写入明文。
    password_hash: str | None = Field(default=None, max_length=255)
    nickname: str = Field(default="", max_length=50)
    avatar: str | None = Field(default=None, max_length=500)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class UserSession(SQLModel, table=True):
    """服务端会话。数据库只保存令牌哈希。"""

    __tablename__ = "user_sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    session_token_hash: str = Field(unique=True, index=True, max_length=64)
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime = Field(index=True)
    revoked_at: datetime | None = Field(default=None)
    last_used_at: datetime | None = Field(default=None)
