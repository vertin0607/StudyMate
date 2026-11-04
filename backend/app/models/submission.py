"""题目代码草稿和提交记录。草稿和历史提交分开保存，本阶段不判题。"""

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.user import utc_now


class ProblemCodeDraft(SQLModel, table=True):
    """每道题每个用户一份当前草稿。"""

    __tablename__ = "problem_code_drafts"
    __table_args__ = (UniqueConstraint("user_id", "problem_id", name="uq_problem_code_draft"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    problem_id: int = Field(foreign_key="problems.id", index=True)
    language: str = Field(default="cpp", max_length=20)
    source_code: str = Field(default="", max_length=100000)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProblemSubmission(SQLModel, table=True):
    """一次代码提交。第八阶段只记录代码，状态固定为尚未判题。"""

    __tablename__ = "problem_submissions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    problem_id: int = Field(foreign_key="problems.id", index=True)
    language: str = Field(default="cpp", max_length=20)
    source_code: str = Field(max_length=100000)
    status: str = Field(default="unjudged", max_length=30)
    submitted_at: datetime = Field(default_factory=utc_now, index=True)
