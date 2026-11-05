"""测试使用独立的 SQLite 文件，不写入 backend/data 里的正式学习记录。"""

import os
from pathlib import Path

TEST_DB_PATH = Path(__file__).resolve().parent / "_test_studymate.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

# 必须在导入 app 之前设置。load_dotenv 不会覆盖已经存在的环境变量。
os.environ["DATABASE_PATH"] = str(TEST_DB_PATH)


def _clean_goals() -> None:
    from sqlmodel import Session, delete

    from app.database import engine, init_db
    from app.models.goal import LearningGoal
    from app.models.knowledge import KnowledgePoint
    from app.models.plan import PlanRevision, StudyPlan, StudyTask
    from app.models.judge import ProblemJudgeCaseResult, ProblemJudgeResult
    from app.models.practice import ProblemLearningStatus, ProblemPracticeRecord, ProblemWrongRecord
    from app.models.problem import Problem, ProblemNote, ProblemTestCase, ProblemTopic, ProblemTopicLink
    from app.models.submission import ProblemCodeDraft, ProblemSubmission
    from app.models.explain import KnowledgeExplainMessage, KnowledgeExplainSession, QuestionExplanation
    from app.models.quiz import KnowledgeMasteryEvent, Quiz, QuizAnswer, QuizQuestion
    from app.models.recommendation import TrainingRecommendation
    from app.models.review import ReviewRecord, ReviewSchedule
    from app.models.topic_link import TopicKnowledgeLink
    from app.models.tutor import TutorMessage, TutorSession

    init_db()
    with Session(engine) as session:
        session.exec(delete(ProblemJudgeCaseResult))
        session.exec(delete(ProblemJudgeResult))
        session.exec(delete(ProblemWrongRecord))
        session.exec(delete(ProblemPracticeRecord))
        session.exec(delete(ProblemLearningStatus))
        session.exec(delete(ProblemCodeDraft))
        session.exec(delete(ProblemSubmission))
        session.exec(delete(TrainingRecommendation))
        session.exec(delete(TopicKnowledgeLink))
        session.exec(delete(ProblemTopicLink))
        session.exec(delete(ProblemNote))
        session.exec(delete(ProblemTestCase))
        session.exec(delete(Problem))
        session.exec(delete(ProblemTopic))
        session.exec(delete(TutorMessage))
        session.exec(delete(TutorSession))
        session.exec(delete(KnowledgeExplainMessage))
        session.exec(delete(KnowledgeExplainSession))
        session.exec(delete(QuestionExplanation))
        session.exec(delete(ReviewRecord))
        session.exec(delete(ReviewSchedule))
        session.exec(delete(QuizAnswer))
        session.exec(delete(QuizQuestion))
        session.exec(delete(KnowledgeMasteryEvent))
        session.exec(delete(Quiz))
        session.exec(delete(StudyTask))
        session.exec(delete(PlanRevision))
        session.exec(delete(StudyPlan))
        session.exec(delete(KnowledgePoint))
        session.exec(delete(LearningGoal))
        session.commit()


def _allow_test_login() -> None:
    """只给测试库里的 local 设置口令，便于原有用例继续访问自己的数据。"""
    from sqlmodel import Session, select

    from app.database import engine
    from app.models.user import User
    from app.services.auth_service import hash_password
    from tests.client import LOCAL_PASSWORD

    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == "local")).one()
        if user.password_hash:
            return
        user.password_hash = hash_password(LOCAL_PASSWORD)
        session.add(user)
        session.commit()


def pytest_runtest_setup() -> None:
    """每个测试前清掉学习目标，避免用例互相影响。"""
    _clean_goals()
    _allow_test_login()


import fastapi.testclient
from tests.client import BusinessTestClient

fastapi.testclient.TestClient = BusinessTestClient
