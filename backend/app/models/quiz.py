"""知识检测、作答和掌握度变化。正确答案只存在服务端。"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.user import utc_now


class Quiz(SQLModel, table=True):
    __tablename__ = "quizzes"

    id: int | None = Field(default=None, primary_key=True)
    goal_id: int = Field(foreign_key="learning_goals.id", index=True)
    plan_id: int | None = Field(default=None, foreign_key="study_plans.id", index=True)
    task_id: int | None = Field(default=None, foreign_key="study_tasks.id", index=True)
    title: str = Field(min_length=1, max_length=120)
    status: str = Field(default="ready", max_length=20, index=True)
    score: int | None = Field(default=None)
    correct_count: int = Field(default=0, ge=0)
    wrong_count: int = Field(default=0, ge=0)
    suggestion: str = Field(default="", max_length=2000)
    created_at: datetime = Field(default_factory=utc_now)
    submitted_at: datetime | None = Field(default=None)


class QuizQuestion(SQLModel, table=True):
    __tablename__ = "quiz_questions"

    id: int | None = Field(default=None, primary_key=True)
    quiz_id: int = Field(foreign_key="quizzes.id", index=True)
    knowledge_point_id: int = Field(foreign_key="knowledge_points.id", index=True)
    sort_order: int = Field(default=0, ge=0)
    question_type: str = Field(max_length=20)
    difficulty: str = Field(max_length=20)
    stem: str = Field(min_length=1, max_length=2000)
    options_json: str = Field(default="[]")
    correct_answer: str = Field(min_length=1, max_length=2000)
    explanation: str = Field(min_length=1, max_length=2000)
    score: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)


class QuizAnswer(SQLModel, table=True):
    __tablename__ = "quiz_answers"

    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="quiz_questions.id", unique=True, index=True)
    user_answer: str = Field(default="", max_length=4000)
    is_correct: bool = Field(default=False)
    score: int = Field(default=0, ge=0, le=100)
    error_reason: str = Field(default="", max_length=2000)
    suggestion: str = Field(default="", max_length=2000)
    created_at: datetime = Field(default_factory=utc_now)


class KnowledgeMasteryEvent(SQLModel, table=True):
    __tablename__ = "knowledge_mastery_events"

    id: int | None = Field(default=None, primary_key=True)
    knowledge_point_id: int = Field(foreign_key="knowledge_points.id", index=True)
    quiz_id: int | None = Field(default=None, foreign_key="quizzes.id", index=True)
    previous_level: int | None = Field(default=None)
    new_level: int = Field(ge=0, le=100)
    quiz_score: int = Field(ge=0, le=100)
    reason: str = Field(max_length=500)
    created_at: datetime = Field(default_factory=utc_now)
