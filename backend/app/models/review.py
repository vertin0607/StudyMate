"""知识点的复习计划和每次复习记录。"""

from datetime import date, datetime

from sqlmodel import Field, SQLModel

from app.models.user import utc_now


class ReviewSchedule(SQLModel, table=True):
    __tablename__ = "review_schedules"

    id: int | None = Field(default=None, primary_key=True)
    goal_id: int = Field(foreign_key="learning_goals.id", index=True)
    knowledge_point_id: int = Field(foreign_key="knowledge_points.id", unique=True, index=True)
    successful_passes: int = Field(default=0, ge=0)
    consecutive_high: int = Field(default=0, ge=0)
    review_count: int = Field(default=0, ge=0)
    interval_days: int = Field(default=1, ge=1)
    last_reviewed_at: datetime | None = Field(default=None)
    last_score: int | None = Field(default=None)
    next_review_date: date = Field(index=True)
    postpone_count: int = Field(default=0, ge=0)
    reason: str = Field(default="", max_length=500)
    open_quiz_id: int | None = Field(default=None, index=True)
    updated_at: datetime = Field(default_factory=utc_now)


class ReviewRecord(SQLModel, table=True):
    __tablename__ = "review_records"

    id: int | None = Field(default=None, primary_key=True)
    schedule_id: int = Field(foreign_key="review_schedules.id", index=True)
    knowledge_point_id: int = Field(foreign_key="knowledge_points.id", index=True)
    quiz_id: int | None = Field(default=None, foreign_key="quizzes.id", index=True)
    reviewed_at: datetime = Field(default_factory=utc_now)
    due_date: date | None = Field(default=None)
    score: int | None = Field(default=None)
    result: str = Field(max_length=20)
    error_summary: str = Field(default="", max_length=500)
    previous_mastery: int | None = Field(default=None)
    new_mastery: int | None = Field(default=None)
    next_interval: int = Field(ge=1)
    next_review_date: date
    reason: str = Field(default="", max_length=500)
