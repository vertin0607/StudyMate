"""复习接口的请求校验。"""

from pydantic import BaseModel, Field


class PostponeRequest(BaseModel):
    days: int = Field(default=1, ge=1, le=14)
