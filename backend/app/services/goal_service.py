"""学习目标的数据库操作。路由只负责收发请求。"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, delete, select

from app.models.goal import LearningGoal
from app.models.knowledge import KnowledgePoint
from app.models.plan import PlanRevision, StudyPlan, StudyTask
from app.models.quiz import KnowledgeMasteryEvent, Quiz, QuizAnswer, QuizQuestion
from app.models.recommendation import TrainingRecommendation
from app.models.review import ReviewRecord, ReviewSchedule
from app.models.tutor import TutorMessage, TutorSession
from app.models.user import User
from app.schemas.goal import GoalCreate, GoalUpdate
from app.services.actor import acting_user

logger = logging.getLogger(__name__)
LOCAL_USERNAME = "local"


def commit_or_raise(session: Session) -> None:
    """提交失败时回滚，并向用户返回不含 SQL 的说明。"""
    try:
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("学习目标保存失败")
        raise HTTPException(status_code=500, detail="保存学习目标失败，请稍后重试") from None


def ensure_local_user(session: Session) -> User | None:
    """只在空库中创建历史账号 local。完成初始化后库里已有正式用户，不再补一个新的 local。"""
    user = session.exec(select(User).where(User.username == LOCAL_USERNAME)).first()
    if user is not None:
        return user
    if session.exec(select(User.id)).first() is not None:
        return None

    user = User(username=LOCAL_USERNAME)
    session.add(user)
    commit_or_raise(session)
    session.refresh(user)
    return user


def list_goals(session: Session) -> list[LearningGoal]:
    user = acting_user(session)
    statement = (
        select(LearningGoal)
        .where(LearningGoal.user_id == user.id)
        .order_by(LearningGoal.updated_at.desc())
    )
    return list(session.exec(statement).all())


def get_goal(session: Session, goal_id: int) -> LearningGoal:
    user = acting_user(session)
    goal = session.get(LearningGoal, goal_id)
    if goal is None or goal.user_id != user.id:
        raise HTTPException(status_code=404, detail="学习目标不存在")
    return goal


def _title_taken(session: Session, user_id: int, title: str, ignore_id: int | None) -> bool:
    statement = select(LearningGoal).where(
        LearningGoal.user_id == user_id,
        LearningGoal.title == title,
    )
    for goal in session.exec(statement).all():
        if goal.id != ignore_id:
            return True
    return False


def create_goal(session: Session, data: GoalCreate) -> LearningGoal:
    user = acting_user(session)
    if _title_taken(session, user.id, data.title, None):
        raise HTTPException(status_code=409, detail="已经有同名学习目标，请换一个名称")

    now = datetime.now(timezone.utc)
    goal = LearningGoal(
        user_id=user.id,
        title=data.title,
        description=data.description,
        target_date=data.target_date,
        daily_minutes=data.daily_minutes,
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(goal)
    commit_or_raise(session)
    session.refresh(goal)
    return goal


def update_goal(session: Session, goal_id: int, data: GoalUpdate) -> LearningGoal:
    goal = get_goal(session, goal_id)
    if _title_taken(session, goal.user_id, data.title, goal.id):
        raise HTTPException(status_code=409, detail="已经有同名学习目标，请换一个名称")

    goal.title = data.title
    goal.description = data.description
    goal.target_date = data.target_date
    goal.daily_minutes = data.daily_minutes
    goal.updated_at = datetime.now(timezone.utc)
    session.add(goal)
    commit_or_raise(session)
    session.refresh(goal)
    return goal


def update_goal_status(session: Session, goal_id: int, status: str) -> LearningGoal:
    goal = get_goal(session, goal_id)
    goal.status = status
    goal.updated_at = datetime.now(timezone.utc)
    session.add(goal)
    commit_or_raise(session)
    session.refresh(goal)
    return goal


def delete_goal(session: Session, goal_id: int) -> None:
    """删除目标时一并删除它的计划和知识点，避免外键拦住原有的删除操作。"""
    goal = get_goal(session, goal_id)
    plans = session.exec(select(StudyPlan).where(StudyPlan.goal_id == goal.id)).all()
    plan_ids = [plan.id for plan in plans if plan.id is not None]
    tutor_ids = [
        item.id
        for item in session.exec(
            select(TutorSession).where(TutorSession.goal_id == goal.id, TutorSession.user_id == goal.user_id)
        ).all()
        if item.id is not None
    ]
    if tutor_ids:
        session.exec(delete(TutorMessage).where(TutorMessage.session_id.in_(tutor_ids)))
    session.exec(delete(TutorSession).where(TutorSession.goal_id == goal.id, TutorSession.user_id == goal.user_id))
    point_ids = [
        point.id
        for point in session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id == goal.id)).all()
        if point.id is not None
    ]
    if point_ids:
        session.exec(delete(ReviewRecord).where(ReviewRecord.knowledge_point_id.in_(point_ids)))
    session.exec(delete(ReviewSchedule).where(ReviewSchedule.goal_id == goal.id))
    quizzes = session.exec(select(Quiz).where(Quiz.goal_id == goal.id)).all()
    quiz_ids = [quiz.id for quiz in quizzes if quiz.id is not None]
    if quiz_ids:
        question_ids = [
            question.id
            for question in session.exec(select(QuizQuestion).where(QuizQuestion.quiz_id.in_(quiz_ids))).all()
            if question.id is not None
        ]
        if question_ids:
            session.exec(delete(QuizAnswer).where(QuizAnswer.question_id.in_(question_ids)))
        session.exec(delete(QuizQuestion).where(QuizQuestion.quiz_id.in_(quiz_ids)))
        session.exec(delete(KnowledgeMasteryEvent).where(KnowledgeMasteryEvent.quiz_id.in_(quiz_ids)))
        session.exec(delete(Quiz).where(Quiz.id.in_(quiz_ids)))
    session.exec(
        delete(TrainingRecommendation).where(
            TrainingRecommendation.goal_id == goal.id,
            TrainingRecommendation.user_id == goal.user_id,
        )
    )
    if point_ids:
        session.exec(
            delete(TrainingRecommendation).where(
                TrainingRecommendation.knowledge_point_id.in_(point_ids),
                TrainingRecommendation.user_id == goal.user_id,
            )
        )
        session.exec(delete(KnowledgeMasteryEvent).where(KnowledgeMasteryEvent.knowledge_point_id.in_(point_ids)))
        from app.services.topic_link_service import delete_for_knowledge_points

        delete_for_knowledge_points(session, point_ids, goal.user_id)
    if plan_ids:
        session.exec(delete(StudyTask).where(StudyTask.plan_id.in_(plan_ids)))
        session.exec(delete(PlanRevision).where(PlanRevision.plan_id.in_(plan_ids)))
        session.exec(delete(StudyPlan).where(StudyPlan.id.in_(plan_ids)))
    session.exec(delete(KnowledgePoint).where(KnowledgePoint.goal_id == goal.id))
    session.delete(goal)
    commit_or_raise(session)
