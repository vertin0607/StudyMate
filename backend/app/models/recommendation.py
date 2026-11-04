"""个性化训练建议。诊断报告表留给后续 AI 报告，这里不提前创建。"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.user import utc_now


class TrainingRecommendation(SQLModel, table=True):
    __tablename__ = "training_recommendations"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    # 10.6 才会建立诊断报告。当前规则诊断没有报告行，所以这里保持为空，不设外键。
    diagnosis_report_id: int | None = Field(default=None, index=True)
    goal_id: int | None = Field(default=None, foreign_key="learning_goals.id", index=True)
    knowledge_point_id: int | None = Field(default=None, foreign_key="knowledge_points.id", index=True)
    problem_topic_id: int | None = Field(default=None, foreign_key="problem_topics.id", index=True)
    problem_id: int | None = Field(default=None, foreign_key="problems.id", index=True)
    category: str = Field(max_length=40, index=True)
    title: str = Field(max_length=120)
    description: str = Field(default="", max_length=2000)
    reason: str = Field(default="", max_length=2000)
    estimated_minutes: int = Field(ge=1, le=720)
    priority: int = Field(ge=1, le=4, index=True)
    completion_criteria: str = Field(max_length=500)
    status: str = Field(default="pending", max_length=20, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
