"""个人题库。题目、测试数据和分类与学习目标的掌握度分开保存。"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.user import utc_now


class ProblemTopic(SQLModel, table=True):
    """题库使用的算法和数据结构分类，不进入掌握度或复习。"""

    __tablename__ = "problem_topics"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    category: str = Field(max_length=40)
    name: str = Field(max_length=40, index=True)
    created_at: datetime = Field(default_factory=utc_now)


class Problem(SQLModel, table=True):
    __tablename__ = "problems"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    title: str = Field(max_length=200)
    source_platform: str = Field(default="南开大学校内 OJ", max_length=80)
    source_problem_id: str = Field(default="", max_length=40)
    source_url: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=20000)
    input_description: str = Field(default="", max_length=8000)
    output_description: str = Field(default="", max_length=8000)
    sample_input: str = Field(default="", max_length=20000)
    sample_output: str = Field(default="", max_length=20000)
    constraints: str = Field(default="", max_length=4000)
    note: str = Field(default="", max_length=4000)
    difficulty: str = Field(default="unknown", max_length=20)
    course: str = Field(default="", max_length=80)
    status: str = Field(default="ready", max_length=20)
    analysis_status: str = Field(default="pending", max_length=20, index=True)
    analysis_error: str = Field(default="", max_length=500)
    ai_analysis_json: str = Field(default="")
    classification_locked: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProblemTestCase(SQLModel, table=True):
    __tablename__ = "problem_test_cases"

    id: int | None = Field(default=None, primary_key=True)
    problem_id: int = Field(foreign_key="problems.id", index=True)
    name: str = Field(max_length=80)
    input_data: str = Field(default="")
    expected_output: str = Field(default="")
    case_type: str = Field(default="custom", max_length=20)
    is_public: bool = Field(default=False)
    note: str = Field(default="", max_length=500)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProblemTopicLink(SQLModel, table=True):
    __tablename__ = "problem_topic_links"

    id: int | None = Field(default=None, primary_key=True)
    problem_id: int = Field(foreign_key="problems.id", index=True)
    topic_id: int = Field(foreign_key="problem_topics.id", index=True)
    relevance: str = Field(max_length=20)
    reason: str = Field(default="", max_length=500)


class ProblemNote(SQLModel, table=True):
    __tablename__ = "problem_notes"

    id: int | None = Field(default=None, primary_key=True)
    problem_id: int = Field(foreign_key="problems.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    content: str = Field(default="", max_length=8000)
    solution_idea: str = Field(default="", max_length=8000)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
