"""题库知识点和学习知识点只在用户确认后关联。"""

from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models.goal import LearningGoal
from app.models.knowledge import KnowledgePoint
from app.models.problem import Problem, ProblemTopic
from app.models.topic_link import TopicKnowledgeLink
from app.models.user import User

client = TestClient(app)


def _seed(username: str | None = None) -> dict[str, int]:
    username = username or f"other-link-{uuid4().hex}"
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        local = session.exec(select(User).where(User.username == "local")).one()
        other = User(username=username)
        session.add(other)
        session.commit()
        session.refresh(other)
        goal = LearningGoal(
            user_id=local.id,
            title="关联目标",
            description="确认后才关联",
            target_date=date.today(),
            daily_minutes=25,
            created_at=now,
            updated_at=now,
        )
        hidden_goal = LearningGoal(
            user_id=other.id,
            title="别人的目标",
            description="不可关联",
            target_date=date.today(),
            daily_minutes=25,
            created_at=now,
            updated_at=now,
        )
        session.add(goal)
        session.add(hidden_goal)
        session.commit()
        session.refresh(goal)
        session.refresh(hidden_goal)
        point = KnowledgePoint(goal_id=goal.id, name="字符串匹配算法", created_at=now, updated_at=now)
        same_name = KnowledgePoint(goal_id=goal.id, name="KMP", created_at=now, updated_at=now)
        hidden_point = KnowledgePoint(goal_id=hidden_goal.id, name="别人的知识点", created_at=now, updated_at=now)
        topic = ProblemTopic(user_id=local.id, category="自定义", name="前缀函数", created_at=now)
        same_topic = ProblemTopic(user_id=local.id, category="自定义", name="KMP", created_at=now)
        hidden_topic = ProblemTopic(user_id=other.id, category="自定义", name="别人的题库知识点", created_at=now)
        problem = Problem(user_id=local.id, title="关联题", description="题面", created_at=now, updated_at=now)
        session.add(point)
        session.add(same_name)
        session.add(hidden_point)
        session.add(topic)
        session.add(same_topic)
        session.add(hidden_topic)
        session.add(problem)
        session.commit()
        for row in (point, same_name, hidden_point, topic, same_topic, hidden_topic, problem, goal):
            session.refresh(row)
        return {
            "goal": goal.id,
            "point": point.id,
            "same_name": same_name.id,
            "hidden_point": hidden_point.id,
            "topic": topic.id,
            "same_topic": same_topic.id,
            "hidden_topic": hidden_topic.id,
            "problem": problem.id,
        }


def test_links_require_confirmation_and_stay_isolated() -> None:
    ids = _seed()
    assert client.get("/api/learning/topic-links").json()["links"] == []
    created = client.post(
        "/api/problems/import",
        json={"title": "同名题", "description": "描述", "source_platform": "南开大学校内 OJ", "source_problem_id": "kmp-link"},
    )
    assert created.status_code == 201
    assert client.get("/api/learning/topic-links").json()["links"] == []
    denied_topic = client.post("/api/learning/topic-links", json={"problem_topic_id": ids["hidden_topic"], "knowledge_point_id": ids["point"]})
    denied_point = client.post("/api/learning/topic-links", json={"problem_topic_id": ids["topic"], "knowledge_point_id": ids["hidden_point"]})
    assert denied_topic.status_code == 404
    assert denied_point.status_code == 404
    first = client.post("/api/learning/topic-links", json={"problem_topic_id": ids["topic"], "knowledge_point_id": ids["point"]})
    assert first.status_code == 201
    assert first.json()["problem_topic_name"] == "前缀函数"
    assert first.json()["knowledge_point_name"] == "字符串匹配算法"
    again = client.post("/api/learning/topic-links", json={"problem_topic_id": ids["topic"], "knowledge_point_id": ids["point"]})
    assert again.status_code == 409
    second = client.post("/api/learning/topic-links", json={"problem_topic_id": ids["same_topic"], "knowledge_point_id": ids["point"]})
    third = client.post("/api/learning/topic-links", json={"problem_topic_id": ids["topic"], "knowledge_point_id": ids["same_name"]})
    assert second.status_code == 201
    assert third.status_code == 201
    listed = client.get("/api/learning/topic-links").json()["links"]
    assert len(listed) == 3
    assert client.delete(f"/api/learning/topic-links/{first.json()['id']}").status_code == 204
    with Session(engine) as session:
        assert session.get(ProblemTopic, ids["topic"]) is not None
        assert session.get(KnowledgePoint, ids["point"]) is not None
        assert session.get(TopicKnowledgeLink, first.json()["id"]) is None
    assert client.delete(f"/api/learning/topic-links/{first.json()['id']}").status_code == 404


def test_deleting_one_side_keeps_the_other() -> None:
    ids = _seed()
    link = client.post("/api/learning/topic-links", json={"problem_topic_id": ids["topic"], "knowledge_point_id": ids["point"]}).json()
    assert client.delete(f"/api/goals/{ids['goal']}").status_code == 204
    with Session(engine) as session:
        assert session.get(KnowledgePoint, ids["point"]) is None
        assert session.get(TopicKnowledgeLink, link["id"]) is None
        assert session.get(ProblemTopic, ids["topic"]) is not None
        assert session.get(Problem, ids["problem"]) is not None
    ids = _seed()
    link = client.post("/api/learning/topic-links", json={"problem_topic_id": ids["topic"], "knowledge_point_id": ids["point"]}).json()
    assert client.delete(f"/api/problems/topics/{ids['topic']}").status_code == 204
    with Session(engine) as session:
        assert session.get(ProblemTopic, ids["topic"]) is None
        assert session.get(TopicKnowledgeLink, link["id"]) is None
        assert session.get(KnowledgePoint, ids["point"]) is not None
        assert session.get(Problem, ids["problem"]) is not None
    assert client.delete(f"/api/problems/topics/{ids['hidden_topic']}").status_code == 404
