"""学习计划接口的请求和响应。"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

TaskStatus = Literal["pending", "in_progress", "completed", "skipped"]


class GeneratePlanRequest(BaseModel):
    goal_id: int = Field(ge=1)


class RegeneratePlanRequest(BaseModel):
    instruction: str = ""

    @field_validator("instruction")
    @classmethod
    def clean_instruction(cls, value: str) -> str:
        text = value.strip()
        if len(text) > 500:
            raise ValueError("修改要求不能超过 500 个字符")
        return text


class TaskStatusUpdate(BaseModel):
    status: TaskStatus
