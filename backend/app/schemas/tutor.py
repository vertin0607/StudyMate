"""教学会话的请求校验。"""

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    goal_id: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, max_length=40)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
