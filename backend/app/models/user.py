"""本地用户。当前只有一个用户，学习目标仍然通过 user_id 关联。"""

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, min_length=1, max_length=50)
    created_at: datetime = Field(default_factory=utc_now)
