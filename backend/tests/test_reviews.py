"""复习队列和间隔更新。出题使用假响应，不请求 DeepSeek。"""

import json
from datetime import timedelta

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models.goal import LearningGoal
from app.models.knowledge import KnowledgePoint
from app.models.quiz import KnowledgeMasteryEvent
from app.models.review import ReviewSchedule
from app.models.user import User
from app.services.ai.errors import AIError
from app.services.review_service import local_today

client = TestClient(app)


def goal_payload(title: str) -> dict:
    return {
        "title": title,
        "description": "用一个很小的数字例子理解梯度下降怎样更新参数。",
        "target_date": "2026-12-31",
        "daily_minutes": 25,
    }


def plan_payload() -> dict:
    return {
        "plan_title": "用下山理解梯度方向",
        "plan_description": "今天只用一个很小的数字例子，看参数为什么要朝梯度反方向更新。",
        "total_minutes": 25,
        "tasks": [
            {
                "title": "用走山路理解梯度",
                "description": "先看每一步为什么要朝更低的方向走，再对应到参数更新。",
                "task_type": "learn",
                "estimated_minutes": 25,
                "knowledge_point": "梯度",
            }
        ],
    }


def perfect_quiz(point_id: int) -> dict:
    return {
        "title": "梯度复习检测",
        "questions": [
            {
                "question_type": "single",
                "difficulty": "basic",
                "stem": f"第{index}题：参数为什么要减去梯度？",
                "options": [
                    {"key": "A", "text": "参数沿梯度反方向更新"},
                    {"key": "B", "text": "参数沿梯度方向增大"},
                    {"key": "C", "text": "学习率只改变样本数量"},
                ],
                "correct_answer": "A",
                "explanation": "这道题要看清梯度和参数更新方向的关系，而不是只记公式。",
                "knowledge_point_id": point_id,
            }
            for index in range(1, 6)
        ],
    }


def prepare(monkeypatch, title: str) -> tuple[int, int]:
    monkeypatch.setattr("app.services.planning_service.complete_json", lambda _messages: json.dumps(plan_payload()))
    goal_id = client.post("/api/goals", json=goal_payload(title)).json()["id"]
    task_id = client.post("/api/plans/generate", json={"goal_id": goal_id}).json()["plan"]["tasks"][0]["id"]
    client.patch(f"/api/tasks/{task_id}/status", json={"status": "completed"})
    with Session(engine) as session:
        point_id = session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id == goal_id)).one().id
    return goal_id, point_id, task_id


def submit_perfect(monkeypatch, task_id: int, point_id: int) -> dict:
    monkeypatch.setattr("app.services.quiz_service.complete_json", lambda _messages, **_kwargs: json.dumps(perfect_quiz(point_id)))
    quiz = client.post("/api/quizzes/generate", json={"task_id": task_id}).json()
    answers = {"answers": [{"question_id": item["id"], "answer": "A"} for item in quiz["questions"]]}
    return client.post(f"/api/quizzes/{quiz['id']}/submit", json=answers).json()


def test_first_assessment_schedules_one_day_and_refresh_does_not_duplicate(monkeypatch) -> None:
    goal_id, point_id, task_id = prepare(monkeypatch, "首次复习")
    result = submit_perfect(monkeypatch, task_id, point_id)
    review = result["reviews"][0]

    assert review["interval_days"] == 1
    assert review["next_review_date"] == str(local_today() + timedelta(days=1))
    assert client.get(f"/api/knowledge/{point_id}").json()["memory"]["stage_label"] == "等待第一次复习"
    first = client.get("/api/reviews/today").json()
    second = client.post("/api/reviews/generate").json()
    assert first["due_count"] == 0
    assert second["due_count"] == 0
    with Session(engine) as session:
        rows = session.exec(select(ReviewSchedule).where(ReviewSchedule.goal_id == goal_id)).all()
        assert len(rows) == 1
    trends = client.get("/api/learning/trends", params={"knowledge_id": point_id}).json()
    assert trends["series"][0]["sufficient"] is False


def test_passing_review_extends_and_repeat_submit_does_not(monkeypatch) -> None:
    _goal_id, point_id, task_id = prepare(monkeypatch, "延长间隔")
    submit_perfect(monkeypatch, task_id, point_id)
    with Session(engine) as session:
        schedule = session.exec(select(ReviewSchedule)).one()
        schedule.next_review_date = local_today()
        session.add(schedule)
        session.commit()
        schedule_id = schedule.id
    calls = {"n": 0}

    def fake(_messages: list[dict[str, str]], **_kwargs) -> str:
        calls["n"] += 1
        return json.dumps(perfect_quiz(point_id))

    monkeypatch.setattr("app.services.review_service.complete_json", fake)
    started = client.post(f"/api/reviews/{schedule_id}/start")
    again = client.post(f"/api/reviews/{schedule_id}/start")
    assert started.status_code == 200
    assert again.json()["id"] == started.json()["id"]
    assert calls["n"] == 1
    answers = {"answers": [{"question_id": item["id"], "answer": "A"} for item in started.json()["questions"]]}
    submitted = client.post(f"/api/quizzes/{started.json()['id']}/submit", json=answers)
    assert submitted.status_code == 200
    assert submitted.json()["reviews"][0]["interval_days"] == 3
    assert client.post(f"/api/quizzes/{started.json()['id']}/submit", json=answers).status_code == 409
    detail = client.get(f"/api/reviews/{schedule_id}").json()
    assert detail["interval_days"] == 3
    assert client.get("/api/learning/trends", params={"knowledge_id": point_id}).json()["sufficient"] is True


def test_failed_review_shrinks_interval(monkeypatch) -> None:
    _goal_id, point_id, task_id = prepare(monkeypatch, "缩短间隔")
    submit_perfect(monkeypatch, task_id, point_id)
    with Session(engine) as session:
        schedule = session.exec(select(ReviewSchedule)).one()
        schedule.successful_passes = 3
        schedule.interval_days = 14
        schedule.next_review_date = local_today()
        session.add(schedule)
        session.commit()
    monkeypatch.setattr("app.services.quiz_service.complete_json", lambda _messages, **_kwargs: json.dumps(perfect_quiz(point_id)))
    quiz = client.post("/api/quizzes/generate", json={"task_id": task_id}).json()
    wrong = {"answers": [{"question_id": item["id"], "answer": "B"} for item in quiz["questions"]]}
    result = client.post(f"/api/quizzes/{quiz['id']}/submit", json=wrong).json()

    assert result["reviews"][0]["interval_days"] == 1
    assert "1 天" in result["reviews"][0]["reason"]


def test_queue_priority_overdue_and_postpone(monkeypatch) -> None:
    monkeypatch.setattr("app.services.planning_service.complete_json", lambda _messages: json.dumps(plan_payload()))
    goal_id = client.post("/api/goals", json=goal_payload("复习队列")).json()["id"]
    today = local_today()
    with Session(engine) as session:
        weak = KnowledgePoint(goal_id=goal_id, name="反向传播", description="误差向前传递", status="needs_review", mastery_level=45)
        strong = KnowledgePoint(goal_id=goal_id, name="前向传播", description="输入到输出", status="basic", mastery_level=90)
        later = KnowledgePoint(goal_id=goal_id, name="Softmax", description="把分数变成概率", status="basic", mastery_level=82)
        session.add(weak)
        session.add(strong)
        session.add(later)
        session.commit()
        session.refresh(weak)
        session.refresh(strong)
        session.refresh(later)
        session.add(ReviewSchedule(goal_id=goal_id, knowledge_point_id=weak.id, next_review_date=today - timedelta(days=2), last_score=45, interval_days=1, reason="逾期"))
        session.add(ReviewSchedule(goal_id=goal_id, knowledge_point_id=strong.id, next_review_date=today, last_score=90, interval_days=7, reason="今日"))
        session.add(ReviewSchedule(goal_id=goal_id, knowledge_point_id=later.id, next_review_date=today + timedelta(days=2), last_score=82, interval_days=3, reason="即将"))
        session.commit()
        weak_schedule = session.exec(select(ReviewSchedule).where(ReviewSchedule.knowledge_point_id == weak.id)).one().id

    queue = client.get("/api/reviews/today").json()
    assert queue["overdue"][0]["name"] == "反向传播"
    assert queue["overdue"][0]["risk"] == "high"
    assert "45" in queue["overdue"][0]["risk_reason"]
    assert client.get("/api/reviews/overdue").json()["items"][0]["name"] == "反向传播"
    assert client.get("/api/reviews/upcoming").json()["items"][0]["name"] == "Softmax"
    postponed = client.patch(f"/api/reviews/{weak_schedule}/postpone", json={"days": 3}).json()
    assert postponed["next_review_date"] == str(today + timedelta(days=3))
    assert postponed["postpone_count"] == 1
    assert client.get("/api/reviews/overdue").json()["items"] == []
    history = client.get("/api/reviews/history").json()["records"]
    assert history[0]["result"] == "postponed"
    with Session(engine) as session:
        assert session.exec(select(KnowledgeMasteryEvent)).first() is None


def test_plan_prompt_receives_due_reviews(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake(messages: list[dict[str, str]]) -> str:
        captured["text"] = messages[-1]["content"]
        return json.dumps(plan_payload())

    monkeypatch.setattr("app.services.planning_service.complete_json", fake)
    goal_id = client.post("/api/goals", json=goal_payload("计划读取复习")).json()["id"]
    with Session(engine) as session:
        point = KnowledgePoint(goal_id=goal_id, name="反向传播", description="误差向前传递", status="needs_review", mastery_level=45)
        session.add(point)
        session.commit()
        session.refresh(point)
        session.add(
            ReviewSchedule(
                goal_id=goal_id,
                knowledge_point_id=point.id,
                next_review_date=local_today(),
                last_score=45,
                interval_days=1,
                reason="今天该复习反向传播",
            )
        )
        session.commit()

    assert client.post("/api/plans/generate", json={"goal_id": goal_id}).status_code == 200
    assert "反向传播" in captured["text"]
    assert "due_reviews" in captured["text"]


def test_future_review_cannot_start(monkeypatch) -> None:
    _goal_id, _point_id, task_id = prepare(monkeypatch, "未到期")
    result = submit_perfect(monkeypatch, task_id, _point_id)
    schedule_id = result["reviews"][0]["id"]

    def fail_if_called(_messages: list[dict[str, str]], **_kwargs) -> str:
        raise AssertionError("未到期不应出题")

    monkeypatch.setattr("app.services.review_service.complete_json", fail_if_called)
    assert client.post(f"/api/reviews/{schedule_id}/start").status_code == 400


def test_invalid_review_quiz_is_not_saved(monkeypatch) -> None:
    _goal_id, point_id, task_id = prepare(monkeypatch, "无效复习题")
    submit_perfect(monkeypatch, task_id, point_id)
    with Session(engine) as session:
        schedule = session.exec(select(ReviewSchedule)).one()
        schedule.next_review_date = local_today()
        session.add(schedule)
        session.commit()
        schedule_id = schedule.id
    calls = {"n": 0}

    def fake(_messages: list[dict[str, str]], **_kwargs) -> str:
        calls["n"] += 1
        return "不是 JSON"

    monkeypatch.setattr("app.services.review_service.complete_json", fake)
    assert client.post(f"/api/reviews/{schedule_id}/start").status_code == 502
    assert calls["n"] == 2
    assert client.get(f"/api/reviews/{schedule_id}").json()["open_quiz_id"] is None


def test_paused_goal_is_absent_and_delete_clears_schedule(monkeypatch) -> None:
    goal_id, _point_id, task_id = prepare(monkeypatch, "暂停不再复习")
    schedule_id = submit_perfect(monkeypatch, task_id, _point_id)["reviews"][0]["id"]
    with Session(engine) as session:
        schedule = session.get(ReviewSchedule, schedule_id)
        assert schedule is not None
        schedule.next_review_date = local_today()
        session.add(schedule)
        session.commit()
    client.patch(f"/api/goals/{goal_id}/status", json={"status": "paused"})
    assert client.get("/api/reviews/today").json()["due_count"] == 0
    assert client.delete(f"/api/goals/{goal_id}").status_code == 204
    assert client.get(f"/api/reviews/{schedule_id}").status_code == 404


def test_other_user_cannot_read_review(monkeypatch) -> None:
    _goal_id, _point_id, task_id = prepare(monkeypatch, "复习隔离")
    schedule_id = submit_perfect(monkeypatch, task_id, _point_id)["reviews"][0]["id"]
    with Session(engine) as session:
        other = User(username="other-review")
        session.add(other)
        session.commit()
        session.refresh(other)
        goal = session.get(LearningGoal, _goal_id)
        assert goal is not None
        goal.user_id = other.id
        session.add(goal)
        session.commit()

    assert client.get(f"/api/reviews/{schedule_id}").status_code == 404


def test_failed_postpone_keeps_date(monkeypatch) -> None:
    _goal_id, _point_id, task_id = prepare(monkeypatch, "推迟回滚")
    review = submit_perfect(monkeypatch, task_id, _point_id)["reviews"][0]
    original = review["next_review_date"]

    def fail(_session: Session) -> None:
        raise HTTPException(status_code=500, detail="保存失败，请稍后重试")

    monkeypatch.setattr("app.services.review_service.goal_service.commit_or_raise", fail)
    response = client.patch(f"/api/reviews/{review['id']}/postpone", json={"days": 2})

    assert response.status_code == 500
    assert client.get(f"/api/reviews/{review['id']}").json()["next_review_date"] == original


def test_statistics_do_not_invent_progress(monkeypatch) -> None:
    prepare(monkeypatch, "统计不足")
    stats = client.get("/api/learning/review-statistics").json()

    assert stats["sufficient"] is False
    assert stats["average_score"] is None
    assert stats["most_improved"] == []
