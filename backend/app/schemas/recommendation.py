"""训练建议只允许把待做标记为完成或忽略。"""

from typing import Literal

from pydantic import BaseModel


class RecommendationStatusUpdate(BaseModel):
    status: Literal["completed", "ignored"]
