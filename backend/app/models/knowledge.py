"""知识点。掌握程度和任务是否完成分开记录。"""

from sqlmodel import Field, SQLModel

from app.models.user import utc_now
from datetime import datetime


class KnowledgePoint(SQLModel, table=True):
    __tablename__ = "knowledge_points"

    id: int | None = Field(default=None, primary_key=True)
    goal_id: int = Field(foreign_key="learning_goals.id", index=True)
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=2000)
    difficulty: str = Field(default="unknown", max_length=20)
    status: str = Field(default="not_started", max_length=20)
    # 0 表示还没有测试成绩，不代表已经掌握。
    mastery_level: int = Field(default=0, ge=0, le=100)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
