"""代码草稿和提交的请求校验。"""

from pydantic import BaseModel, Field


class DraftWrite(BaseModel):
    source_code: str = Field(default="", max_length=100000)
    language: str = Field(default="cpp", pattern="^cpp$")


class SubmissionWrite(BaseModel):
    source_code: str = Field(min_length=1, max_length=100000)
    language: str = Field(default="cpp", pattern="^cpp$")
