"""学习目标的请求和响应结构。客户端不能指定 user_id。"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

GoalStatus = Literal["active", "paused", "completed"]


def _required_text(value: str, label: str, limit: int) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{label}不能为空")
    if len(text) > limit:
        raise ValueError(f"{label}不能超过 {limit} 个字符")
    return text


class GoalWrite(BaseModel):
    """创建和编辑共用的字段。"""

    title: str
    description: str
    target_date: date
    daily_minutes: int = Field(ge=1, le=720)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return _required_text(value, "学习目标名称", 80)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        return _required_text(value, "目标描述", 2000)

    @field_validator("daily_minutes")
    @classmethod
    def check_minutes(cls, value: int) -> int:
        if value < 1 or value > 720:
            raise ValueError("每日学习时间需要在 1 到 720 分钟之间")
        return value


class GoalCreate(GoalWrite):
    pass


class GoalUpdate(GoalWrite):
    pass


class GoalStatusUpdate(BaseModel):
    status: GoalStatus


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    description: str
    target_date: date
    daily_minutes: int
    status: str
    created_at: datetime
    updated_at: datetime
