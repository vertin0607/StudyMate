"""练习状态、练习记录和错题的请求校验。"""

from pydantic import BaseModel, Field


class LearningStatusUpdate(BaseModel):
    status: str = Field(pattern="^(todo|attempting|self_completed)$")


class PracticeComplete(BaseModel):
    completion_type: str = Field(pattern="^(independent|with_hint|with_solution|unfinished)$")
    note: str = Field(default="", max_length=2000)


class WrongWrite(BaseModel):
    reason_type: str = Field(pattern="^(algorithm|boundary|implementation|syntax|complexity|other)$")
    reason_detail: str = Field(default="", max_length=1000)
    related_submission_id: int | None = Field(default=None, ge=1)
