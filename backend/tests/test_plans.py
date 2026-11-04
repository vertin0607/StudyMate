"""学习计划接口。模型调用全部替换成假函数，不访问 DeepSeek。"""

import json

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import settings
from app.database import engine
from app.main import app
from app.models.knowledge import KnowledgePoint
from app.models.plan import StudyPlan
from app.services.ai.errors import AIError, redact

client = TestClient(app)


def goal_payload(**overrides: object) -> dict:
    payload = {
        "title": "梯度入门",
        "description": "从生活例子开始，理解梯度下降在更新参数时做了什么。",
        "target_date": "2026-12-31",
        "daily_minutes": 25,
    }
    payload.update(overrides)
    return payload


def sample_plan(total: int = 25) -> dict:
    tasks = [
        {
            "title": "用走山路理解梯度",
            "description": "先看每一步为什么要朝更低的方向走，再对应到参数更新。",
            "task_type": "learn",
            "estimated_minutes": 10,
            "knowledge_point": "梯度",
        },
        {
            "title": "手算一次参数更新",
            "description": "用 w = w - 学习率 × 梯度，计算一组很小的数字。",
            "task_type": "practice",
            "estimated_minutes": 10,
            "knowledge_point": "参数更新",
        },
        {
            "title": "合上笔记复述例子",
            "description": "不看公式，说出学习率和梯度分别改变了哪一个数。",
            "task_type": "quiz",
            "estimated_minutes": 5,
            "knowledge_point": "梯度",
        },
    ]
    if total != 25:
        tasks = [
            {**tasks[0], "estimated_minutes": 8},
            {**tasks[1], "estimated_minutes": total - 8},
        ]
    return {
        "plan_title": "用下山理解梯度方向",
        "plan_description": "今天只用一个很小的数字例子，看参数为什么要朝梯度反方向更新。",
        "total_minutes": total,
        "tasks": tasks,
    }


def test_redact_hides_secret() -> None:
    assert redact("key=abc123 failed", "abc123") == "key=*** failed"


def test_dashboard_and_today_do_not_call_model_before_generation(monkeypatch) -> None:
    def fail_if_called(_messages: list[dict[str, str]]) -> str:
        raise AssertionError("读取计划时不应调用 DeepSeek")

    monkeypatch.setattr("app.services.planning_service.complete_json", fail_if_called)
    goal_id = client.post("/api/goals", json=goal_payload()).json()["id"]

    dashboard = client.get("/api/plans/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["has_plan"] is False
    assert dashboard.json()["recent_goal"]["id"] == goal_id

    today = client.get("/api/plans/today", params={"goal_id": goal_id})
    assert today.status_code == 200
    assert today.json()["plan"] is None


def test_generate_is_reused_until_user_asks_to_regenerate(monkeypatch) -> None:
    calls = {"n": 0}

    def fake(_messages: list[dict[str, str]]) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps(sample_plan())
        return json.dumps(sample_plan(total=15))

    monkeypatch.setattr("app.services.planning_service.complete_json", fake)
    goal_id = client.post("/api/goals", json=goal_payload(title="梯度练习")).json()["id"]

    created = client.post("/api/plans/generate", json={"goal_id": goal_id})
    assert created.status_code == 200
    plan = created.json()["plan"]
    assert plan["version"] == 1
    assert plan["tasks"][0]["mastery_assessed"] is False
    assert calls["n"] == 1

    reread = client.get("/api/plans/today", params={"goal_id": goal_id})
    assert reread.json()["plan"]["id"] == plan["id"]
    assert calls["n"] == 1

    duplicate = client.post("/api/plans/generate", json={"goal_id": goal_id})
    assert duplicate.status_code == 409
    assert calls["n"] == 1

    task_id = plan["tasks"][0]["id"]
    completed = client.patch(f"/api/tasks/{task_id}/status", json={"status": "completed"})
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["mastery_assessed"] is False
    with Session(engine) as session:
        point = session.exec(select(KnowledgePoint).where(KnowledgePoint.name == "梯度")).one()
        assert point.mastery_level == 0
        assert point.status == "learning"

    regenerated = client.post(
        f"/api/plans/{plan['id']}/regenerate",
        json={"instruction": "今天只有15分钟，帮我缩短学习计划。"},
    )
    assert regenerated.status_code == 200
    new_plan = regenerated.json()["plan"]
    assert new_plan["version"] == 2
    assert new_plan["total_minutes"] == 15
    assert calls["n"] == 2

    history = client.get(f"/api/plans/{new_plan['id']}/history")
    assert [item["version"] for item in history.json()["versions"]] == [2, 1]
    assert "15分钟" in history.json()["revisions"][0]["reason"]
    with Session(engine) as session:
        old = session.get(StudyPlan, plan["id"])
        assert old is not None
        assert old.status == "archived"
        assert old.title == "用下山理解梯度方向"


def test_invalid_model_output_stops_after_two_attempts(monkeypatch) -> None:
    calls = {"n": 0}

    def fake(_messages: list[dict[str, str]]) -> str:
        calls["n"] += 1
        return "不是 JSON"

    monkeypatch.setattr("app.services.planning_service.complete_json", fake)
    goal_id = client.post("/api/goals", json=goal_payload(title="校验失败")).json()["id"]
    response = client.post("/api/plans/generate", json={"goal_id": goal_id})

    assert response.status_code == 502
    assert calls["n"] == 2
    assert client.get("/api/plans/today", params={"goal_id": goal_id}).json()["plan"] is None


def test_failed_regeneration_keeps_current_plan(monkeypatch) -> None:
    calls = {"n": 0}

    def fake(_messages: list[dict[str, str]]) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps(sample_plan())
        raise AIError("模拟连接失败")

    monkeypatch.setattr("app.services.planning_service.complete_json", fake)
    goal_id = client.post("/api/goals", json=goal_payload(title="保留旧计划")).json()["id"]
    plan_id = client.post("/api/plans/generate", json={"goal_id": goal_id}).json()["plan"]["id"]

    failed = client.post(f"/api/plans/{plan_id}/regenerate", json={"instruction": "缩短到15分钟"})
    assert failed.status_code == 502
    current = client.get("/api/plans/today", params={"goal_id": goal_id}).json()["plan"]
    assert current["id"] == plan_id
    assert current["status"] == "active"


def test_mastered_point_is_not_saved(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.planning_service.complete_json",
        lambda _messages: json.dumps(sample_plan()),
    )
    goal_id = client.post("/api/goals", json=goal_payload(title="已掌握梯度")).json()["id"]
    with Session(engine) as session:
        session.add(
            KnowledgePoint(
                goal_id=goal_id,
                name="梯度",
                description="已经能够独立解释",
                status="mastered",
                mastery_level=90,
            )
        )
        session.commit()

    response = client.post("/api/plans/generate", json={"goal_id": goal_id})
    assert response.status_code == 502
    assert client.get("/api/plans/today", params={"goal_id": goal_id}).json()["plan"] is None


def test_paused_goal_does_not_call_model(monkeypatch) -> None:
    def fail_if_called(_messages: list[dict[str, str]]) -> str:
        raise AssertionError("暂停的目标不应调用 DeepSeek")

    monkeypatch.setattr("app.services.planning_service.complete_json", fail_if_called)
    goal_id = client.post("/api/goals", json=goal_payload(title="暂停目标")).json()["id"]
    client.patch(f"/api/goals/{goal_id}/status", json={"status": "paused"})

    response = client.post("/api/plans/generate", json={"goal_id": goal_id})
    assert response.status_code == 400


def test_missing_plan_and_task_return_404(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.planning_service.complete_json",
        lambda _messages: (_ for _ in ()).throw(AssertionError("不应调用")),
    )
    assert client.get("/api/plans/99999").status_code == 404
    assert client.patch("/api/tasks/99999/status", json={"status": "completed"}).status_code == 404


def test_connection_reports_status_without_secret(monkeypatch) -> None:
    monkeypatch.setattr("app.routers.ai.ping", lambda: None)
    response = client.post("/api/ai/test-connection")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["model"]
    assert body["error"] is None
    if settings.deepseek_api_key:
        assert settings.deepseek_api_key not in response.text


def test_deleting_goal_removes_saved_plan(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.planning_service.complete_json",
        lambda _messages: json.dumps(sample_plan()),
    )
    goal_id = client.post("/api/goals", json=goal_payload(title="删除时带走计划")).json()["id"]
    created = client.post("/api/plans/generate", json={"goal_id": goal_id})
    plan_id = created.json()["plan"]["id"]

    deleted = client.delete(f"/api/goals/{goal_id}")

    assert deleted.status_code == 204
    assert client.get(f"/api/plans/{plan_id}").status_code == 404


def test_connection_when_key_missing(monkeypatch) -> None:
    monkeypatch.setattr("app.services.ai.deepseek_client.settings.deepseek_api_key", "")
    response = client.post("/api/ai/test-connection")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert "DEEPSEEK_API_KEY" in response.json()["error"]
