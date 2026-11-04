"""用户确认后，题库知识点才和学习目标知识点关联。"""

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.user import utc_now


class TopicKnowledgeLink(SQLModel, table=True):
    __tablename__ = "topic_knowledge_links"
    __table_args__ = (UniqueConstraint("user_id", "problem_topic_id", "knowledge_point_id"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    problem_topic_id: int = Field(foreign_key="problem_topics.id", index=True)
    knowledge_point_id: int = Field(foreign_key="knowledge_points.id", index=True)
    created_at: datetime = Field(default_factory=utc_now)
