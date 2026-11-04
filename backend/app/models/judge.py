"""一次提交对应一份判题结果。判题结果不覆盖提交时的代码。"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.user import utc_now


class ProblemJudgeResult(SQLModel, table=True):
    __tablename__ = "problem_judge_results"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    submission_id: int = Field(foreign_key="problem_submissions.id", unique=True, index=True)
    problem_id: int = Field(foreign_key="problems.id", index=True)
    status: str = Field(default="judging", max_length=30, index=True)
    total_cases: int = Field(default=0)
    passed_cases: int = Field(default=0)
    failed_cases: int = Field(default=0)
    compile_output: str = Field(default="")
    error_message: str = Field(default="", max_length=2000)
    execution_time_ms: int = Field(default=0)
    memory_used_kb: int = Field(default=0)
    ai_analysis: str = Field(default="")
    ai_analysis_error: str = Field(default="", max_length=500)
    judged_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)


class ProblemJudgeCaseResult(SQLModel, table=True):
    __tablename__ = "problem_judge_case_results"

    id: int | None = Field(default=None, primary_key=True)
    judge_result_id: int = Field(foreign_key="problem_judge_results.id", index=True)
    test_case_id: int = Field(foreign_key="problem_test_cases.id", index=True)
    status: str = Field(max_length=30)
    execution_time_ms: int = Field(default=0)
    actual_output: str = Field(default="")
    expected_output: str = Field(default="")
    error_message: str = Field(default="", max_length=1000)
