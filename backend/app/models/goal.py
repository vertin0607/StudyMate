"""学习目标表。状态只允许 active、paused、completed。"""

from datetime import date, datetime

from sqlmodel import Field, SQLModel

from app.models.user import utc_now


class LearningGoal(SQLModel, table=True):
    __tablename__ = "learning_goals"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=2000)
    target_date: date
    daily_minutes: int = Field(ge=1, le=720)
    status: str = Field(default="active", max_length=20)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
