"""导入数据表，确保 SQLModel 在建表前已经注册它们。"""

from app.models.goal import LearningGoal
from app.models.judge import ProblemJudgeCaseResult, ProblemJudgeResult
from app.models.knowledge import KnowledgePoint
from app.models.plan import PlanRevision, StudyPlan, StudyTask
from app.models.practice import ProblemLearningStatus, ProblemPracticeRecord, ProblemWrongRecord
from app.models.problem import Problem, ProblemNote, ProblemTestCase, ProblemTopic, ProblemTopicLink
from app.models.quiz import KnowledgeMasteryEvent, Quiz, QuizAnswer, QuizQuestion
from app.models.recommendation import TrainingRecommendation
from app.models.review import ReviewRecord, ReviewSchedule
from app.models.submission import ProblemCodeDraft, ProblemSubmission
from app.models.topic_link import TopicKnowledgeLink
from app.models.tutor import TutorMessage, TutorSession
from app.models.user import User, UserSession

__all__ = [
    "KnowledgeMasteryEvent",
    "KnowledgePoint",
    "LearningGoal",
    "PlanRevision",
    "Problem",
    "ProblemJudgeCaseResult",
    "ProblemJudgeResult",
    "ProblemCodeDraft",
    "ProblemLearningStatus",
    "ProblemPracticeRecord",
    "ProblemWrongRecord",
    "ProblemNote",
    "ProblemSubmission",
    "ProblemTestCase",
    "ProblemTopic",
    "ProblemTopicLink",
    "Quiz",
    "QuizAnswer",
    "QuizQuestion",
    "ReviewRecord",
    "ReviewSchedule",
    "StudyPlan",
    "StudyTask",
    "TrainingRecommendation",
    "TopicKnowledgeLink",
    "TutorMessage",
    "TutorSession",
    "User",
    "UserSession",
]
