"""学习计划、每日任务和修改历史。同一天只保留一份当前有效计划。"""

from datetime import date, datetime

from sqlmodel import Field, SQLModel

from app.models.user import utc_now


class StudyPlan(SQLModel, table=True):
    __tablename__ = "study_plans"

    id: int | None = Field(default=None, primary_key=True)
    goal_id: int = Field(foreign_key="learning_goals.id", index=True)
    plan_date: date = Field(index=True)
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    total_minutes: int = Field(ge=1, le=720)
    status: str = Field(default="active", max_length=20, index=True)
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class StudyTask(SQLModel, table=True):
    __tablename__ = "study_tasks"

    id: int | None = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="study_plans.id", index=True)
    knowledge_point_id: int | None = Field(default=None, foreign_key="knowledge_points.id")
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    task_type: str = Field(max_length=20)
    estimated_minutes: int = Field(ge=1, le=720)
    sort_order: int = Field(default=0, ge=0)
    status: str = Field(default="pending", max_length=20)
    completed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PlanRevision(SQLModel, table=True):
    __tablename__ = "plan_revisions"

    id: int | None = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="study_plans.id", index=True)
    old_content: str
    new_content: str
    reason: str = Field(max_length=500)
    created_at: datetime = Field(default_factory=utc_now)
