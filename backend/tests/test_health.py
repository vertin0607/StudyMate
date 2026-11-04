"""确认应用可以导入，并且健康检查返回预期内容。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "StudyMate"
    assert body["phase"] == 9
    assert isinstance(body["server_time"], str)
    assert len(body["server_time"]) >= 19


def test_unknown_route_returns_404() -> None:
    response = client.get("/api/lessons")

    assert response.status_code == 404
