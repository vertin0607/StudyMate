"""教学会话。模型调用使用假响应，页面读取不会触发它。"""

import json

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models.knowledge import KnowledgePoint
from app.models.tutor import TutorMessage, TutorSession
from app.models.user import User
from app.services.ai.errors import AIError
from app.services.tutor_math import normalize_tutor_math
from app.services.tutor_service import select_focus, teaching_strategy

client = TestClient(app)


def test_strategy_follows_mastery() -> None:
    assert teaching_strategy(None, False)[0] == "basic"
    assert "类比" in teaching_strategy(40, True)[1]
    assert teaching_strategy(74, True)[0] == "intermediate"
    assert "符号" in teaching_strategy(74, True)[1]
    assert teaching_strategy(95, True)[0] == "advanced"
    points = [
        {"name": "链式法则", "mastery_level": 80, "mastery_assessed": True},
        {"name": "反向传播", "mastery_level": 40, "mastery_assessed": True},
    ]
    focused = select_focus(points, "反向传播和链式法则有什么关系？")
    assert focused[0]["name"] == "反向传播"


def test_reading_sessions_does_not_call_model(monkeypatch) -> None:
    def fail(_messages, **_kwargs):
        raise AssertionError("读取会话不应调用模型")

    monkeypatch.setattr("app.services.tutor_service.complete_json", fail)
    goal_id = client.post(
        "/api/goals",
        json={"title": "教学读取", "description": "看梯度怎样更新参数。", "target_date": "2026-12-31", "daily_minutes": 25},
    ).json()["id"]
    created = client.post("/api/tutor/sessions", json={"goal_id": goal_id})
    assert created.status_code == 201
    session_id = created.json()["id"]
    assert client.get("/api/tutor/sessions").status_code == 200
    assert client.get(f"/api/tutor/sessions/{session_id}").json()["messages"] == []


def test_message_stays_in_the_same_session_and_uses_level(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake(messages, **_kwargs):
        captured["text"] = messages[-1]["content"]
        return json.dumps({"reply": "梯度表示下山最陡的方向。你能说出减号在更新里起什么作用吗？"}, ensure_ascii=False)

    monkeypatch.setattr("app.services.tutor_service.complete_json", fake)
    goal_id = client.post(
        "/api/goals",
        json={"title": "梯度入门", "description": "用下山理解参数更新。", "target_date": "2026-12-31", "daily_minutes": 25},
    ).json()["id"]
    with Session(engine) as session:
        point = KnowledgePoint(goal_id=goal_id, name="梯度", description="参数更新方向", status="needs_review", mastery_level=45)
        session.add(point)
        session.commit()
        session.refresh(point)
        point_id = point.id
    session_id = client.post("/api/tutor/sessions", json={"goal_id": goal_id}).json()["id"]
    first = client.post(f"/api/tutor/sessions/{session_id}/messages", json={"content": "梯度到底是什么？"})
    assert first.status_code == 200
    assert "类比" in captured["text"]
    assert "梯度" in captured["text"]
    monkeypatch.setattr(
        "app.services.tutor_service.complete_json",
        lambda _messages, **_kwargs: json.dumps({"reply": "减号让参数朝着下降的方向走。"}, ensure_ascii=False),
    )
    second = client.post(f"/api/tutor/sessions/{session_id}/messages", json={"content": "那减号呢？"})
    assert second.status_code == 200
    detail = client.get(f"/api/tutor/sessions/{session_id}").json()
    assert [item["role"] for item in detail["messages"]] == ["user", "assistant", "user", "assistant"]
    assert detail["title"] == "梯度到底是什么？"
    with Session(engine) as session:
        saved = session.get(KnowledgePoint, point_id)
        assert saved is not None
        assert saved.mastery_level == 45


def test_invalid_reply_is_not_saved(monkeypatch) -> None:
    calls = {"n": 0}

    def fake(_messages, **_kwargs):
        calls["n"] += 1
        return "不是 JSON"

    monkeypatch.setattr("app.services.tutor_service.complete_json", fake)
    session_id = client.post("/api/tutor/sessions", json={}).json()["id"]
    response = client.post(f"/api/tutor/sessions/{session_id}/messages", json={"content": "你好"})
    assert response.status_code == 502
    assert calls["n"] == 2
    assert client.get(f"/api/tutor/sessions/{session_id}").json()["messages"] == []


def test_model_error_rolls_back_before_save(monkeypatch) -> None:
    def fail(_messages, **_kwargs):
        raise AIError("DeepSeek 请求超时，请稍后重试", status_code=504)

    monkeypatch.setattr("app.services.tutor_service.complete_json", fail)
    session_id = client.post("/api/tutor/sessions", json={}).json()["id"]
    assert client.post(f"/api/tutor/sessions/{session_id}/messages", json={"content": "还在吗"}).status_code == 504
    assert client.get(f"/api/tutor/sessions/{session_id}").json()["messages"] == []


def test_failed_commit_does_not_keep_half_reply(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.tutor_service.complete_json",
        lambda _messages, **_kwargs: json.dumps({"reply": "先记住这一句。"}),
    )
    session_id = client.post("/api/tutor/sessions", json={}).json()["id"]

    def fail(_session: Session) -> None:
        raise HTTPException(status_code=500, detail="保存失败，请稍后重试")

    monkeypatch.setattr("app.services.tutor_service.goal_service.commit_or_raise", fail)
    assert client.post(f"/api/tutor/sessions/{session_id}/messages", json={"content": "保存失败时呢"}).status_code == 500
    with Session(engine) as session:
        assert session.exec(select(TutorMessage).where(TutorMessage.session_id == session_id)).all() == []


def test_delete_session_and_goal_cleanup(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.tutor_service.complete_json",
        lambda _messages, **_kwargs: json.dumps({"reply": "好，我们下次继续。"}),
    )
    goal_id = client.post(
        "/api/goals",
        json={"title": "会删掉的目标", "description": "只用来检查级联。", "target_date": "2026-12-31", "daily_minutes": 20},
    ).json()["id"]
    session_id = client.post("/api/tutor/sessions", json={"goal_id": goal_id}).json()["id"]
    assert client.post(f"/api/tutor/sessions/{session_id}/messages", json={"content": "先记一笔"}).status_code == 200
    assert client.delete(f"/api/goals/{goal_id}").status_code == 204
    assert client.get(f"/api/tutor/sessions/{session_id}").status_code == 404

    kept = client.post("/api/tutor/sessions", json={}).json()["id"]
    assert client.delete(f"/api/tutor/sessions/{kept}").status_code == 204
    assert client.get(f"/api/tutor/sessions/{kept}").status_code == 404


def test_other_user_cannot_read_session() -> None:
    session_id = client.post("/api/tutor/sessions", json={}).json()["id"]
    with Session(engine) as session:
        other = User(username="other-tutor")
        session.add(other)
        session.commit()
        session.refresh(other)
        row = session.get(TutorSession, session_id)
        assert row is not None
        row.user_id = other.id
        session.add(row)
        session.commit()
    assert client.get(f"/api/tutor/sessions/{session_id}").status_code == 404


def test_math_text_keeps_one_copy_and_standard_delimiters() -> None:
    source = "先看下标 \\( x_i \\)。\n$$ x_i $$\n$$x_i$$\n代码里不要改：\n```\n$x_i$\n```\n求和 $$ \\sum_{i=1}^{n} x_i $$。"
    normalized = normalize_tutor_math(source)

    before_code = normalized.split("```")[0]
    assert before_code.count("$$") == 2
    assert "$x_i$" in before_code
    assert "```\n$x_i$\n```" in normalized
    assert "\\sum_{i=1}^{n} x_i" in normalized


def test_prompt_requires_checked_math() -> None:
    from pathlib import Path

    prompt = Path("app/prompts/tutor.txt").read_text(encoding="utf-8")
    assert "不要先给出错误计算" in prompt
    assert "O(n)" in prompt
    assert "偏导" in prompt


def test_blank_message_is_rejected() -> None:
    session_id = client.post("/api/tutor/sessions", json={}).json()["id"]
    assert client.post(f"/api/tutor/sessions/{session_id}/messages", json={"content": "   "}).status_code == 422
