"""训练建议来自规则诊断。完成或忽略不会改掌握度、复习和练习状态。"""

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models.goal import LearningGoal
from app.models.knowledge import KnowledgePoint
from app.models.plan import StudyPlan
from app.models.practice import ProblemLearningStatus
from app.models.problem import Problem, ProblemTopic, ProblemTopicLink
from app.models.quiz import KnowledgeMasteryEvent
from app.models.recommendation import TrainingRecommendation
from app.models.review import ReviewSchedule
from app.models.submission import ProblemSubmission
from app.models.judge import ProblemJudgeResult
from app.models.user import User

client = TestClient(app)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _goal(session: Session, user_id: int, title: str, minutes: int, status: str = "active") -> LearningGoal:
    now = _now()
    goal = LearningGoal(
        user_id=user_id,
        title=title,
        description="训练建议",
        target_date=date.today(),
        daily_minutes=minutes,
        status=status,
        created_at=now,
        updated_at=now,
    )
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


def _point(session: Session, goal_id: int, name: str, status: str = "learning", mastery: int = 40) -> KnowledgePoint:
    now = _now()
    point = KnowledgePoint(goal_id=goal_id, name=name, status=status, mastery_level=mastery, created_at=now, updated_at=now)
    session.add(point)
    session.commit()
    session.refresh(point)
    return point


def _scores(session: Session, point_id: int, scores: list[int]) -> None:
    now = _now()
    previous = None
    for index, score in enumerate(scores):
        session.add(
            KnowledgeMasteryEvent(
                knowledge_point_id=point_id,
                previous_level=previous,
                new_level=score,
                quiz_score=score,
                reason="检测",
                created_at=now - timedelta(days=len(scores) - index),
            )
        )
        previous = score
    point = session.get(KnowledgePoint, point_id)
    point.mastery_level = scores[-1]
    session.add(point)
    session.commit()


def _topic(session: Session, user_id: int, name: str) -> ProblemTopic:
    topic = ProblemTopic(user_id=user_id, category="自定义", name=name, created_at=_now())
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


def _problem(session: Session, user_id: int, title: str, topic_id: int, status: str = "todo") -> Problem:
    now = _now()
    problem = Problem(user_id=user_id, title=title, created_at=now, updated_at=now)
    session.add(problem)
    session.commit()
    session.refresh(problem)
    session.add(ProblemTopicLink(problem_id=problem.id, topic_id=topic_id, relevance="primary", reason="测试"))
    if status != "todo":
        session.add(ProblemLearningStatus(user_id=user_id, problem_id=problem.id, status=status, created_at=now, updated_at=now))
    session.commit()
    return problem


def _wrong(session: Session, user_id: int, problem_id: int, reason: str) -> None:
    from app.models.practice import ProblemWrongRecord

    now = _now()
    session.add(ProblemWrongRecord(user_id=user_id, problem_id=problem_id, reason_type=reason, reason_detail="原因", created_at=now, updated_at=now))
    session.commit()


def _link(session: Session, user_id: int, topic_id: int, point_id: int) -> None:
    from app.models.topic_link import TopicKnowledgeLink

    session.add(TopicKnowledgeLink(user_id=user_id, problem_topic_id=topic_id, knowledge_point_id=point_id, created_at=_now()))
    session.commit()


def _generate(goal_id: int | None = None) -> dict:
    response = client.post("/api/learning/recommendations/generate" if goal_id is None else f"/api/learning/recommendations/generate?goal_id={goal_id}")
    assert response.status_code == 200
    return response.json()


def _local_id() -> int:
    with Session(engine) as session:
        return session.exec(select(User).where(User.username == "local")).one().id


def _saved_count() -> int:
    with Session(engine) as session:
        return len(session.exec(select(TrainingRecommendation)).all())


def test_confirmed_and_suspected_recommendations_keep_priority() -> None:
    with Session(engine) as session:
        user_id = _local_id()
        goal = _goal(session, user_id, "优先级目标", 60)
        confirmed = _point(session, goal.id, "连续低分")
        suspected = _point(session, goal.id, "单次低分")
        _scores(session, confirmed.id, [42, 51])
        _scores(session, suspected.id, [58])
        goal_id = goal.id
    payload = _generate(goal_id)
    rows = payload["recommendations"]
    assert payload["created_count"] == 2
    assert {row["category"] for row in rows} == {"knowledge_understanding"}
    by_name = {row["knowledge_point_name"]: row for row in rows}
    assert by_name["连续低分"]["priority"] == 2
    assert by_name["单次低分"]["priority"] == 4
    assert by_name["连续低分"]["priority"] < by_name["单次低分"]["priority"]
    assert all(row["diagnosis_report_id"] is None for row in rows)
    again = _generate(goal_id)
    assert again["created_count"] == 0
    assert _saved_count() == 2
    assert {row["id"] for row in again["recommendations"]} == {row["id"] for row in rows}


def test_insufficient_data_does_not_create_remedial_training() -> None:
    with Session(engine) as session:
        user_id = _local_id()
        goal = _goal(session, user_id, "数据不足目标", 40)
        quiet = _point(session, goal.id, "只有高分", mastery=80)
        _scores(session, quiet.id, [80, 90])
        goal_id = goal.id
    payload = _generate(goal_id)
    assert payload["created_count"] == 0
    assert payload["recommendations"] == []
    assert "不生成针对性补救训练" in payload["message"]


def test_forgetting_review_is_kept_ahead_of_other_training() -> None:
    today = datetime.now().astimezone().date()
    with Session(engine) as session:
        user_id = _local_id()
        goal = _goal(session, user_id, "复习优先", 15)
        point = _point(session, goal.id, "逾期知识点", mastery=40)
        _scores(session, point.id, [40, 45])
        session.add(ReviewSchedule(goal_id=goal.id, knowledge_point_id=point.id, next_review_date=today - timedelta(days=1), interval_days=3))
        topic = _topic(session, user_id, "算法题库")
        _link(session, user_id, topic.id, point.id)
        first = _problem(session, user_id, "算法题甲", topic.id)
        second = _problem(session, user_id, "算法题乙", topic.id)
        _wrong(session, user_id, first.id, "algorithm")
        _wrong(session, user_id, second.id, "algorithm")
        session.commit()
        goal_id = goal.id
    payload = _generate(goal_id)
    assert payload["created_count"] == 1
    only = payload["recommendations"][0]
    assert only["category"] == "forgetting"
    assert only["title"].startswith("复习：")
    assert only["priority"] == 1
    assert only["estimated_minutes"] == 15
    assert payload["budgets"][0]["used_minutes"] == 15
    assert any(item["reason"].startswith("超出每日学习时间") for item in payload["skipped"])


def test_recommendations_use_real_problems_and_confirmed_links() -> None:
    with Session(engine) as session:
        user_id = _local_id()
        goal = _goal(session, user_id, "真实题目", 60)
        linked_point = _point(session, goal.id, "已关联知识点")
        loose_point = _point(session, goal.id, "未关联知识点")
        linked_topic = _topic(session, user_id, "已确认题库")
        loose_topic = _topic(session, user_id, "未确认题库")
        empty_topic = _topic(session, user_id, "只有已通过题")
        _link(session, user_id, linked_topic.id, linked_point.id)
        usable = _problem(session, user_id, "可以练习的题", linked_topic.id)
        passed = _problem(session, user_id, "已经通过的题", linked_topic.id, "accepted")
        loose = _problem(session, user_id, "未关联的题", loose_topic.id)
        done = _problem(session, user_id, "不能再推荐的题", empty_topic.id, "accepted")
        _wrong(session, user_id, usable.id, "algorithm")
        _wrong(session, user_id, passed.id, "algorithm")
        _wrong(session, user_id, loose.id, "boundary")
        _wrong(session, user_id, done.id, "boundary")
        extra = _problem(session, user_id, "未关联第二题", loose_topic.id)
        done_two = _problem(session, user_id, "已通过第二题", empty_topic.id, "accepted")
        _wrong(session, user_id, extra.id, "boundary")
        _wrong(session, user_id, done_two.id, "boundary")
        session.commit()
        usable_id, passed_id, loose_id, done_id, goal_id = usable.id, passed.id, loose.id, done.id, goal.id
    payload = _generate(goal_id)
    linked = next(row for row in payload["recommendations"] if row["knowledge_point_name"] == "已关联知识点")
    assert linked["problem_id"] == usable_id
    assert linked["problem_title"] == "可以练习的题"
    assert linked["problem_id"] != passed_id
    independent = next(row for row in payload["recommendations"] if row["problem_topic_name"] == "未确认题库")
    assert independent["knowledge_point_id"] is None
    assert independent["goal_id"] is None
    assert independent["problem_id"] == loose_id
    assert independent["problem_title"] == "未关联的题"
    assert "未关联知识点" not in (independent["knowledge_point_name"] or "")
    missing = next(row for row in payload["recommendations"] if row["problem_topic_name"] == "只有已通过题")
    assert missing["problem_id"] is None
    assert "题库暂无合适题目" in missing["description"]
    assert all(row["problem_id"] != done_id for row in payload["recommendations"])
    with Session(engine) as session:
        assert session.get(Problem, usable_id) is not None
        assert session.get(Problem, loose_id) is not None


def test_daily_budget_keeps_higher_priority_items() -> None:
    with Session(engine) as session:
        user_id = _local_id()
        goal = _goal(session, user_id, "时间预算", 30)
        for name in ("甲知识点", "乙知识点", "丙知识点"):
            point = _point(session, goal.id, name)
            _scores(session, point.id, [30, 40])
        tight = _goal(session, user_id, "只留已确认", 15)
        confirmed = _point(session, tight.id, "应保留")
        suspected = _point(session, tight.id, "应让出")
        _scores(session, confirmed.id, [20, 30])
        _scores(session, suspected.id, [33])
        wide_id, tight_id = goal.id, tight.id
    wide = _generate(wide_id)
    assert wide["created_count"] == 2
    assert sum(row["estimated_minutes"] for row in wide["recommendations"]) == 30
    assert wide["budgets"][0]["used_minutes"] <= 30
    assert any(item["reason"].startswith("超出每日学习时间") for item in wide["skipped"])
    tight_payload = _generate(tight_id)
    assert [row["knowledge_point_name"] for row in tight_payload["recommendations"]] == ["应保留"]
    assert tight_payload["recommendations"][0]["priority"] == 2


def test_status_changes_do_not_touch_learning_records() -> None:
    with Session(engine) as session:
        user_id = _local_id()
        goal = _goal(session, user_id, "状态隔离", 40)
        point = _point(session, goal.id, "待完成知识点", mastery=48)
        _scores(session, point.id, [40, 48])
        session.add(ReviewSchedule(goal_id=goal.id, knowledge_point_id=point.id, next_review_date=date.today() + timedelta(days=3), interval_days=4))
        topic = _topic(session, user_id, "练习题库")
        problem = _problem(session, user_id, "保持练习状态", topic.id, "attempting")
        session.add(StudyPlan(goal_id=goal.id, plan_date=date.today(), title="原计划", description="不变", total_minutes=20, created_at=_now(), updated_at=_now()))
        session.commit()
        point_id, problem_id, goal_id = point.id, problem.id, goal.id

    def snapshot() -> dict:
        with Session(engine) as session:
            schedule = session.exec(select(ReviewSchedule).where(ReviewSchedule.knowledge_point_id == point_id)).one()
            status = session.exec(select(ProblemLearningStatus).where(ProblemLearningStatus.problem_id == problem_id)).one()
            point_row = session.get(KnowledgePoint, point_id)
            return {
                "events": len(session.exec(select(KnowledgeMasteryEvent)).all()),
                "mastery": point_row.mastery_level,
                "interval": schedule.interval_days,
                "schedules": len(session.exec(select(ReviewSchedule)).all()),
                "learning": status.status,
                "plans": len(session.exec(select(StudyPlan)).all()),
                "submissions": len(session.exec(select(ProblemSubmission)).all()),
                "judges": len(session.exec(select(ProblemJudgeResult)).all()),
            }

    created = _generate(goal_id)
    before = snapshot()
    recommendation_id = created["recommendations"][0]["id"]
    completed = client.patch(f"/api/learning/recommendations/{recommendation_id}/status", json={"status": "completed"})
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert snapshot() == before
    ignored = client.patch(f"/api/learning/recommendations/{recommendation_id}/status", json={"status": "ignored"})
    assert ignored.status_code == 409
    with Session(engine) as session:
        row = session.get(TrainingRecommendation, recommendation_id)
        row.status = "pending"
        session.add(row)
        session.commit()
    ignored = client.patch(f"/api/learning/recommendations/{recommendation_id}/status", json={"status": "ignored"})
    assert ignored.status_code == 200
    assert snapshot() == before


def test_user_isolation_and_goal_lifecycle() -> None:
    with Session(engine) as session:
        local = session.exec(select(User).where(User.username == "local")).one()
        other = User(username="other-recommendation")
        session.add(other)
        session.commit()
        session.refresh(other)
        goal = _goal(session, local.id, "会删除的目标", 40)
        paused = _goal(session, local.id, "暂停目标", 40)
        finished = _goal(session, local.id, "完成目标", 40)
        hidden = _goal(session, other.id, "别人的目标", 40)
        point = _point(session, goal.id, "删除前的知识点")
        paused_point = _point(session, paused.id, "暂停里的知识点")
        finished_point = _point(session, finished.id, "完成后的知识点")
        hidden_point = _point(session, hidden.id, "别人的知识点")
        _scores(session, point.id, [20, 30])
        _scores(session, paused_point.id, [20, 30])
        _scores(session, finished_point.id, [20, 30])
        _scores(session, hidden_point.id, [10, 15])
        topic = _topic(session, local.id, "删除后仍在")
        problem = _problem(session, local.id, "目标删除后还在", topic.id)
        session.add(TrainingRecommendation(user_id=other.id, goal_id=hidden.id, knowledge_point_id=hidden_point.id, category="knowledge_understanding", title="别人的建议", description="不可见", reason="隔离", estimated_minutes=10, priority=2, completion_criteria="不可见", status="pending"))
        session.commit()
        goal_id, paused_id, finished_id, hidden_id, problem_id = goal.id, paused.id, finished.id, hidden.id, problem.id
    own = _generate(goal_id)
    assert own["created_count"] == 1
    assert client.post(f"/api/learning/recommendations/generate?goal_id={hidden_id}").status_code == 404
    listed = client.get("/api/learning/recommendations").json()["recommendations"]
    assert all(row["title"] != "别人的建议" for row in listed)
    hidden_recommendation = next(row_id for row_id, title in _titles() if title == "别人的建议")
    assert client.get(f"/api/learning/recommendations/{hidden_recommendation}").status_code == 404
    assert client.patch(f"/api/goals/{paused_id}/status", json={"status": "paused"}).status_code == 200
    paused_payload = _generate(paused_id)
    assert paused_payload["created_count"] == 0
    assert "暂停" in paused_payload["message"]
    assert client.patch(f"/api/goals/{finished_id}/status", json={"status": "completed"}).status_code == 200
    finished_payload = _generate(finished_id)
    assert finished_payload["created_count"] == 0
    assert "完成" in finished_payload["message"]
    assert client.delete(f"/api/goals/{goal_id}").status_code == 204
    with Session(engine) as session:
        assert session.exec(select(TrainingRecommendation).where(TrainingRecommendation.goal_id == goal_id)).all() == []
        assert session.get(Problem, problem_id) is not None
        assert session.exec(select(ProblemTopic).where(ProblemTopic.name == "删除后仍在")).one() is not None


def _titles() -> list[tuple[int, str]]:
    with Session(engine) as session:
        return [(row.id, row.title) for row in session.exec(select(TrainingRecommendation)).all()]


def test_skilled_point_is_not_retrained_until_review_is_due() -> None:
    today = datetime.now().astimezone().date()
    with Session(engine) as session:
        user_id = _local_id()
        goal = _goal(session, user_id, "熟练目标", 60)
        quiet = _point(session, goal.id, "已经熟练", status="mastered", mastery=90)
        due = _point(session, goal.id, "熟练但逾期", status="mastered", mastery=88)
        topic = _topic(session, user_id, "熟练题库")
        _link(session, user_id, topic.id, quiet.id)
        first = _problem(session, user_id, "熟练题甲", topic.id)
        second = _problem(session, user_id, "熟练题乙", topic.id)
        _wrong(session, user_id, first.id, "algorithm")
        _wrong(session, user_id, second.id, "algorithm")
        session.add(ReviewSchedule(goal_id=goal.id, knowledge_point_id=due.id, next_review_date=today - timedelta(days=1), interval_days=6))
        session.commit()
        goal_id = goal.id
    payload = _generate(goal_id)
    assert [row["title"] for row in payload["recommendations"]] == ["复习：熟练但逾期"]
    assert all(row["problem_title"] != "熟练题甲" for row in payload["recommendations"])


def test_empty_generation_has_no_recommendations() -> None:
    payload = _generate()
    assert payload["created_count"] == 0
    assert payload["recommendations"] == []
    assert "没有进行中的学习目标" in payload["message"]
    assert client.get("/api/learning/recommendations").json() == {"recommendations": []}
