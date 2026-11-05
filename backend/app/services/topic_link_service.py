"""保存用户确认过的题库知识点和学习知识点关联。不会按名称自动建立。"""

from fastapi import HTTPException
from sqlmodel import Session, delete, select

from app.models.goal import LearningGoal
from app.models.knowledge import KnowledgePoint
from app.models.problem import ProblemTopic
from app.models.topic_link import TopicKnowledgeLink
from app.schemas.topic_link import TopicKnowledgeLinkCreate
from app.services import goal_service
from app.services.actor import acting_user


def list_links(session: Session) -> dict:
    user = acting_user(session)
    rows = session.exec(
        select(TopicKnowledgeLink).where(TopicKnowledgeLink.user_id == user.id).order_by(TopicKnowledgeLink.id)
    ).all()
    return {"links": [_payload(session, row) for row in rows]}


def create_link(session: Session, payload: TopicKnowledgeLinkCreate) -> dict:
    user = acting_user(session)
    topic = _owned_topic(session, user.id, payload.problem_topic_id)
    point = _owned_point(session, payload.knowledge_point_id)
    existing = session.exec(
        select(TopicKnowledgeLink).where(
            TopicKnowledgeLink.user_id == user.id,
            TopicKnowledgeLink.problem_topic_id == topic.id,
            TopicKnowledgeLink.knowledge_point_id == point.id,
        )
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="这个关联已经确认过")
    row = TopicKnowledgeLink(user_id=user.id, problem_topic_id=topic.id, knowledge_point_id=point.id)
    session.add(row)
    goal_service.commit_or_raise(session)
    session.refresh(row)
    return _payload(session, row)


def delete_link(session: Session, link_id: int) -> None:
    user = acting_user(session)
    row = session.get(TopicKnowledgeLink, link_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="关联不存在")
    session.delete(row)
    goal_service.commit_or_raise(session)


def delete_for_knowledge_points(session: Session, point_ids: list[int], user_id: int | None) -> None:
    if point_ids and user_id is not None:
        session.exec(
            delete(TopicKnowledgeLink).where(
                TopicKnowledgeLink.knowledge_point_id.in_(point_ids),
                TopicKnowledgeLink.user_id == user_id,
            )
        )


def delete_for_topics(session: Session, topic_ids: list[int], user_id: int | None) -> None:
    if topic_ids and user_id is not None:
        session.exec(
            delete(TopicKnowledgeLink).where(
                TopicKnowledgeLink.problem_topic_id.in_(topic_ids),
                TopicKnowledgeLink.user_id == user_id,
            )
        )


def _owned_topic(session: Session, user_id: int | None, topic_id: int) -> ProblemTopic:
    topic = session.get(ProblemTopic, topic_id)
    if topic is None or topic.user_id != user_id:
        raise HTTPException(status_code=404, detail="题库知识点不存在")
    return topic


def _owned_point(session: Session, knowledge_id: int) -> KnowledgePoint:
    point = session.get(KnowledgePoint, knowledge_id)
    if point is None:
        raise HTTPException(status_code=404, detail="学习知识点不存在")
    goal = session.get(LearningGoal, point.goal_id)
    user = acting_user(session)
    if goal is None or goal.user_id != user.id:
        raise HTTPException(status_code=404, detail="学习知识点不存在")
    return point


def _payload(session: Session, row: TopicKnowledgeLink) -> dict:
    topic = session.get(ProblemTopic, row.problem_topic_id)
    point = session.get(KnowledgePoint, row.knowledge_point_id)
    return {
        "id": row.id,
        "problem_topic_id": row.problem_topic_id,
        "problem_topic_name": "" if topic is None else topic.name,
        "knowledge_point_id": row.knowledge_point_id,
        "knowledge_point_name": "" if point is None else point.name,
        "goal_id": None if point is None else point.goal_id,
        "created_at": row.created_at,
    }
