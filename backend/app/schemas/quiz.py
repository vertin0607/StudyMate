"""知识检测的请求校验。"""

from pydantic import BaseModel, Field, field_validator


class QuizGenerateRequest(BaseModel):
    task_id: int = Field(ge=1)


class AnswerInput(BaseModel):
    question_id: int = Field(ge=1)
    answer: str = ""

    @field_validator("answer")
    @classmethod
    def clean_answer(cls, value: str) -> str:
        text = value.strip()
        if len(text) > 4000:
            raise ValueError("答案不能超过 4000 个字符")
        return text


class QuizSubmitRequest(BaseModel):
    answers: list[AnswerInput] = Field(min_length=1)
