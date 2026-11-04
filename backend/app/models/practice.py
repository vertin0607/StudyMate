"""题目练习状态、练习记录和错题。与知识点掌握度、知识点复习分开保存。"""

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.user import utc_now


class ProblemLearningStatus(SQLModel, table=True):
    """每道题每个用户一份练习状态。系统判题结果由后续阶段写入。"""

    __tablename__ = "problem_learning_status"
    __table_args__ = (UniqueConstraint("user_id", "problem_id", name="uq_problem_learning_status"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    problem_id: int = Field(foreign_key="problems.id", index=True)
    status: str = Field(default="todo", max_length=30)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProblemPracticeRecord(SQLModel, table=True):
    """一次练习过程。完成记录不会覆盖更早的练习。"""

    __tablename__ = "problem_practice_records"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    problem_id: int = Field(foreign_key="problems.id", index=True)
    started_at: datetime = Field(default_factory=utc_now, index=True)
    completed_at: datetime | None = Field(default=None)
    completion_type: str = Field(default="", max_length=30)
    used_hint: bool = Field(default=False)
    viewed_solution: bool = Field(default=False)
    note: str = Field(default="", max_length=2000)
    created_at: datetime = Field(default_factory=utc_now)


class ProblemWrongRecord(SQLModel, table=True):
    """用户主动标记的错题。本阶段不根据未判题的提交自动创建。"""

    __tablename__ = "problem_wrong_records"
    __table_args__ = (UniqueConstraint("user_id", "problem_id", name="uq_problem_wrong_record"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    problem_id: int = Field(foreign_key="problems.id", index=True)
    reason_type: str = Field(max_length=30)
    reason_detail: str = Field(default="", max_length=1000)
    related_submission_id: int | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
