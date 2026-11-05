"""题目讲解和知识点讲解。讲解记录与掌握度分开保存。"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.user import utc_now


class QuestionExplanation(SQLModel, table=True):
    __tablename__ = "question_explanations"

    id: int | None = Field(default=None, primary_key=True)
    quiz_id: int = Field(foreign_key="quizzes.id", index=True)
    question_id: int = Field(foreign_key="quiz_questions.id", unique=True, index=True)
    content: str = Field(min_length=1, max_length=8000)
    created_at: datetime = Field(default_factory=utc_now)


class KnowledgeExplainSession(SQLModel, table=True):
    __tablename__ = "knowledge_explain_sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    goal_id: int = Field(foreign_key="learning_goals.id", index=True)
    schedule_id: int = Field(foreign_key="review_schedules.id", unique=True, index=True)
    knowledge_point_id: int = Field(foreign_key="knowledge_points.id", index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class KnowledgeExplainMessage(SQLModel, table=True):
    __tablename__ = "knowledge_explain_messages"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="knowledge_explain_sessions.id", index=True)
    role: str = Field(max_length=20)
    content: str = Field(min_length=1, max_length=8000)
    created_at: datetime = Field(default_factory=utc_now)
