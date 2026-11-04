"""学习目标的创建、查询、编辑、状态和删除。"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import BACKEND_DIR, resolve_database_path
from app.database import engine
from app.main import app
from app.models.goal import LearningGoal

client = TestClient(app)


def goal_payload(**overrides: object) -> dict:
    payload = {
        "title": "DeCLIP 研究学习",
        "description": "理解论文方法和公式，并能分析实验结果。",
        "target_date": "2026-12-31",
        "daily_minutes": 25,
    }
    payload.update(overrides)
    return payload


def test_relative_database_path_stays_under_backend() -> None:
    resolved = resolve_database_path("data/studymate.db")

    assert resolved == (BACKEND_DIR / "data" / "studymate.db").resolve()
    assert resolved.parent.name == "data"


def test_create_and_list_goal() -> None:
    created = client.post("/api/goals", json=goal_payload())

    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "DeCLIP 研究学习"
    assert body["status"] == "active"
    assert body["daily_minutes"] == 25
    assert body["user_id"] > 0

    listed = client.get("/api/goals")
    assert listed.status_code == 200
    assert any(item["id"] == body["id"] for item in listed.json())


def test_client_cannot_assign_another_user() -> None:
    response = client.post("/api/goals", json=goal_payload(title="用户隔离", user_id=999))

    assert response.status_code == 201
    assert response.json()["user_id"] != 999


def test_get_update_status_and_delete_goal() -> None:
    goal_id = client.post("/api/goals", json=goal_payload(title="Python 基础")).json()["id"]

    fetched = client.get(f"/api/goals/{goal_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Python 基础"

    updated = client.put(
        f"/api/goals/{goal_id}",
        json=goal_payload(title="Python 进阶", daily_minutes=40, target_date="2027-01-15"),
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Python 进阶"
    assert updated.json()["daily_minutes"] == 40

    paused = client.patch(f"/api/goals/{goal_id}/status", json={"status": "paused"})
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    resumed = client.patch(f"/api/goals/{goal_id}/status", json={"status": "active"})
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "active"

    completed = client.patch(f"/api/goals/{goal_id}/status", json={"status": "completed"})
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    deleted = client.delete(f"/api/goals/{goal_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/goals/{goal_id}").status_code == 404


def test_missing_goal_returns_404() -> None:
    assert client.get("/api/goals/99999").status_code == 404
    assert client.put("/api/goals/99999", json=goal_payload()).status_code == 404
    assert client.patch("/api/goals/99999/status", json={"status": "paused"}).status_code == 404
    assert client.delete("/api/goals/99999").status_code == 404


def test_invalid_goal_is_rejected() -> None:
    blank = client.post("/api/goals", json=goal_payload(title="   "))
    assert blank.status_code == 422
    assert "学习目标名称" in blank.json()["detail"]

    minutes = client.post("/api/goals", json=goal_payload(title="时间无效", daily_minutes=0))
    assert minutes.status_code == 422
    assert "每日学习时间" in minutes.json()["detail"]

    bad_date = client.post("/api/goals", json=goal_payload(title="日期无效", target_date="明天"))
    assert bad_date.status_code == 422
    assert "预计完成日期" in bad_date.json()["detail"]

    bad_status = client.post("/api/goals", json=goal_payload(title="状态载体"))
    goal_id = bad_status.json()["id"]
    status_response = client.patch(f"/api/goals/{goal_id}/status", json={"status": "archived"})
    assert status_response.status_code == 422
    assert "状态" in status_response.json()["detail"]


def test_duplicate_title_is_rejected() -> None:
    first = client.post("/api/goals", json=goal_payload(title="重复目标"))
    assert first.status_code == 201

    second = client.post("/api/goals", json=goal_payload(title="重复目标"))
    assert second.status_code == 409
    assert "同名" in second.json()["detail"]


def test_goal_persists_in_sqlite() -> None:
    created = client.post("/api/goals", json=goal_payload(title="持久化目标"))
    goal_id = created.json()["id"]

    with Session(engine) as session:
        stored = session.get(LearningGoal, goal_id)

    assert stored is not None
    assert stored.title == "持久化目标"
    assert client.get(f"/api/goals/{goal_id}").json()["title"] == "持久化目标"
