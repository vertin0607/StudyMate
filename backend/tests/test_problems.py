"""题库保存和题目分析。模型调用使用假响应。"""

import json

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models.problem import Problem, ProblemTestCase
from app.models.user import User
from app.services.ai.errors import AIError

client = TestClient(app)


def problem_body(**overrides) -> dict:
    body = {
        "title": "整数最大间隔",
        "description": "给定 n 个整数，求排序后相邻元素的最大差值。",
        "source_platform": "南开大学校内 OJ",
        "source_problem_id": "1001",
        "sample_input": "3\n1 3 7",
        "sample_output": "4",
        "test_cases": [
            {
                "name": "自定义 1",
                "input_data": "2\n1  2",
                "expected_output": "1\n",
                "case_type": "custom",
                "is_public": False,
                "note": "保留空格",
            }
        ],
    }
    body.update(overrides)
    return body


def analysis(main: str = "排序", secondary: str = "桶排序") -> str:
    return json.dumps(
        {
            "course": "数据结构与算法",
            "difficulty": "medium",
            "main_knowledge_points": [{"name": main, "reason": "需要处理元素顺序"}],
            "secondary_knowledge_points": [{"name": secondary, "reason": "桶划分只在有界条件下线性"}],
            "suggested_new_topics": [{"name": "最大间隔", "relevance": "secondary", "reason": "现有分类没有这个名称"}],
            "algorithm_types": ["桶排序"],
            "core_abilities": ["复杂度分析"],
            "solution_idea": "只比较相邻非空桶的间隔。",
            "algorithm_steps": ["求最值", "按桶放入"],
            "time_complexity": "O(n)",
            "space_complexity": "O(n)",
            "complexity_reason": "每个元素进出桶一次，桶大小有上界时才是线性。",
            "common_mistakes": ["忽略空桶"],
            "review_suggestions": ["复习桶排序适用条件"],
        },
        ensure_ascii=False,
    )


def test_import_cases_notes_and_duplicate_rules(monkeypatch) -> None:
    def fail(_messages, **_kwargs):
        raise AssertionError("保存题目不应调用模型")

    monkeypatch.setattr("app.services.problem_service.complete_json", fail)
    created = client.post("/api/problems/import", json=problem_body())
    assert created.status_code == 201
    problem = created.json()["problem"]
    assert created.json()["duplicate_warning"] is False
    assert problem["description"].startswith("给定")
    assert problem["test_cases"][0]["input_data"] == "2\n1  2"
    assert problem["test_cases"][0]["expected_output"] == "1\n"
    assert any(item["case_type"] == "sample" for item in problem["test_cases"])
    problem_id = problem["id"]
    case_id = problem["test_cases"][0]["id"]
    edited = client.put(
        f"/api/problems/{problem_id}/test-cases/{case_id}",
        json={"name": "自定义 1", "input_data": "2\n1  2", "expected_output": "1\n", "case_type": "custom", "is_public": True, "note": "已改"},
    )
    assert edited.json()["note"] == "已改"
    added = client.post(
        f"/api/problems/{problem_id}/test-cases",
        json={"name": "自定义 2", "input_data": "1\n8", "expected_output": "0", "case_type": "custom", "is_public": False},
    )
    assert added.status_code == 201
    note = client.post(f"/api/problems/{problem_id}/notes", json={"content": "先看相邻差", "solution_idea": "桶"})
    assert note.json()["content"] == "先看相邻差"
    assert client.get(f"/api/problems/{problem_id}/notes").json()["solution_idea"] == "桶"
    assert client.post("/api/problems/import", json=problem_body()).status_code == 409
    warned = client.post("/api/problems/import", json=problem_body(source_problem_id="", title="整数最大间隔"))
    assert warned.status_code == 201
    assert warned.json()["duplicate_warning"] is True
    assert client.post("/api/problems/import", json=problem_body(title="草稿", description="", status="draft", source_problem_id="draft")).status_code == 201
    assert client.post("/api/problems/import", json=problem_body(title="空描述", description="", source_problem_id="empty")).status_code == 422
    updated = client.put(f"/api/problems/{problem_id}", json=problem_body(title="整数最大间隔（修订）"))
    assert updated.json()["title"] == "整数最大间隔（修订）"
    assert len(client.get(f"/api/problems/{problem_id}/test-cases").json()["test_cases"]) == 3


def test_delete_removes_cases_and_other_user_cannot_read() -> None:
    problem_id = client.post("/api/problems/import", json=problem_body(source_problem_id="2002")).json()["problem"]["id"]
    with Session(engine) as session:
        other = User(username="other-problem")
        session.add(other)
        session.commit()
        session.refresh(other)
        row = session.get(Problem, problem_id)
        assert row is not None
        row.user_id = other.id
        session.add(row)
        session.commit()
    assert client.get(f"/api/problems/{problem_id}").status_code == 404
    with Session(engine) as session:
        row = session.get(Problem, problem_id)
        assert row is not None
        local = session.exec(select(User).where(User.username == "local")).one()
        row.user_id = local.id
        session.add(row)
        session.commit()
    assert client.delete(f"/api/problems/{problem_id}").status_code == 204
    with Session(engine) as session:
        assert session.exec(select(ProblemTestCase).where(ProblemTestCase.problem_id == problem_id)).all() == []


def test_analysis_links_topics_and_keeps_user_edits(monkeypatch) -> None:
    calls = {"n": 0}

    def fake(_messages, **_kwargs):
        calls["n"] += 1
        return analysis()

    monkeypatch.setattr("app.services.problem_service.complete_json", fake)
    problem_id = client.post("/api/problems/import", json=problem_body(source_problem_id="3003")).json()["problem"]["id"]
    assert client.get("/api/problems").status_code == 200
    assert calls["n"] == 0
    analyzed = client.post(f"/api/problems/{problem_id}/analyze")
    assert analyzed.status_code == 200
    body = analyzed.json()
    names = {item["name"] for item in body["topics"]}
    assert names == {"排序", "桶排序"}
    assert body["analysis"]["complexity_reason"].startswith("每个元素")
    assert body["description"].startswith("给定")
    assert body["test_cases"][0]["input_data"] == "2\n1  2"
    topics = client.get("/api/problems/topics").json()["categories"]
    sorting = next(item for group in topics for item in group["topics"] if item["name"] == "查找")
    locked = client.put(
        f"/api/problems/{problem_id}/classification",
        json={"course": "算法设计", "difficulty": "hard", "links": [{"topic_id": sorting["id"], "relevance": "primary", "reason": "我改成查找"}]},
    )
    assert locked.json()["classification_locked"] is True
    monkeypatch.setattr("app.services.problem_service.complete_json", lambda _messages, **_kwargs: analysis(main="贪心", secondary="分治"))
    again = client.post(f"/api/problems/{problem_id}/analyze")
    assert {item["name"] for item in again.json()["topics"]} == {"查找"}
    assert again.json()["course"] == "算法设计"
    confirmed = client.post(
        f"/api/problems/{problem_id}/topics/confirm",
        json={"name": "最大间隔", "relevance": "secondary", "reason": "确认新增"},
    )
    assert "最大间隔" in {item["name"] for item in confirmed.json()["topics"]}
    listed = client.get("/api/problems", params={"difficulty": "hard", "analysis_status": "completed"}).json()["problems"]
    assert [item["id"] for item in listed] == [problem_id]
    stats = client.get("/api/problems/statistics").json()
    assert stats["passed"] == 0
    assert stats["analyzed"] == 1


def test_invalid_analysis_keeps_problem(monkeypatch) -> None:
    calls = {"n": 0}

    def fake(_messages, **_kwargs):
        calls["n"] += 1
        return "不是 JSON"

    monkeypatch.setattr("app.services.problem_service.complete_json", fake)
    problem_id = client.post("/api/problems/import", json=problem_body(source_problem_id="4004")).json()["problem"]["id"]
    response = client.post(f"/api/problems/{problem_id}/analyze")
    assert response.status_code == 502
    assert calls["n"] == 2
    saved = client.get(f"/api/problems/{problem_id}").json()
    assert saved["analysis_status"] == "failed"
    assert saved["description"].startswith("给定")
    assert saved["test_cases"]


def test_model_error_keeps_problem(monkeypatch) -> None:
    def fail(_messages, **_kwargs):
        raise AIError("DeepSeek 请求超时，请稍后重试", status_code=504)

    monkeypatch.setattr("app.services.problem_service.complete_json", fail)
    problem_id = client.post("/api/problems/import", json=problem_body(source_problem_id="5005")).json()["problem"]["id"]
    assert client.post(f"/api/problems/{problem_id}/analyze").status_code == 504
    assert client.get(f"/api/problems/{problem_id}").json()["title"] == "整数最大间隔"


def test_delete_case_and_topic_filter() -> None:
    created = client.post("/api/problems/import", json=problem_body(source_problem_id="6006", title="另一题")).json()["problem"]
    case_id = next(item["id"] for item in created["test_cases"] if item["case_type"] == "custom")
    assert client.delete(f"/api/problems/{created['id']}/test-cases/{case_id}").status_code == 204
    remaining = client.get(f"/api/problems/{created['id']}/test-cases").json()["test_cases"]
    assert all(item["id"] != case_id for item in remaining)
