"""关联请求只接受两侧编号，不接受名称匹配。"""

from pydantic import BaseModel, Field


class TopicKnowledgeLinkCreate(BaseModel):
    problem_topic_id: int = Field(ge=1)
    knowledge_point_id: int = Field(ge=1)
