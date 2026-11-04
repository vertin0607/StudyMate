"""教学会话。对话记录和掌握度分开保存，本阶段不因聊天改写掌握度。"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.user import utc_now


class TutorSession(SQLModel, table=True):
    __tablename__ = "tutor_sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    goal_id: int | None = Field(default=None, foreign_key="learning_goals.id", index=True)
    title: str = Field(default="新的对话", max_length=40)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TutorMessage(SQLModel, table=True):
    __tablename__ = "tutor_messages"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="tutor_sessions.id", index=True)
    role: str = Field(max_length=20)
    content: str = Field(min_length=1, max_length=8000)
    knowledge_point_ids_json: str = Field(default="[]")
    created_at: datetime = Field(default_factory=utc_now)
