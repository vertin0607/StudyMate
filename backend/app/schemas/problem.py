"""题库请求校验。测试数据按原文保存。"""

from pydantic import BaseModel, Field


class TestCaseInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    input_data: str = Field(default="", max_length=20000)
    expected_output: str = Field(default="", max_length=20000)
    case_type: str = Field(default="custom", pattern="^(sample|custom)$")
    is_public: bool = False
    note: str = Field(default="", max_length=500)


class ProblemWrite(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)
    source_platform: str = Field(default="南开大学校内 OJ", max_length=80)
    source_problem_id: str = Field(default="", max_length=40)
    source_url: str = Field(default="", max_length=500)
    input_description: str = Field(default="", max_length=8000)
    output_description: str = Field(default="", max_length=8000)
    sample_input: str = Field(default="", max_length=20000)
    sample_output: str = Field(default="", max_length=20000)
    constraints: str = Field(default="", max_length=4000)
    note: str = Field(default="", max_length=4000)
    status: str = Field(default="ready", pattern="^(draft|ready)$")
    test_cases: list[TestCaseInput] = Field(default_factory=list)


class TopicLinkInput(BaseModel):
    topic_id: int = Field(ge=1)
    relevance: str = Field(pattern="^(primary|secondary)$")
    reason: str = Field(default="", max_length=500)


class ClassificationUpdate(BaseModel):
    course: str = Field(default="", max_length=80)
    difficulty: str = Field(default="unknown", pattern="^(unknown|easy|medium|hard)$")
    links: list[TopicLinkInput] = Field(default_factory=list)


class NoteWrite(BaseModel):
    content: str = Field(default="", max_length=8000)
    solution_idea: str = Field(default="", max_length=8000)


class TopicConfirm(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    relevance: str = Field(pattern="^(primary|secondary)$")
    reason: str = Field(default="", max_length=500)
