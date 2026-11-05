"""复习接口的请求校验。"""

from pydantic import BaseModel, Field, field_validator


class PostponeRequest(BaseModel):
    days: int = Field(default=1, ge=1, le=14)


class KnowledgeFollowupRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("请先写下要追问的内容")
        return text
