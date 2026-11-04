"""代码草稿和提交记录。不调用模型，也不运行代码。"""

import inspect

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models.problem import Problem
from app.models.submission import ProblemCodeDraft, ProblemSubmission
from app.models.user import User
from app.services import submission_service

client = TestClient(app)

CODE_A = "#include <iostream>\nint main() {\n    return 0;\n}"
CODE_B = "int main(){return 1;}"


def problem_body(**overrides) -> dict:
    body = {
        "title": "整数最大间隔",
        "description": "给定 n 个整数，求排序后相邻元素的最大差值。",
        "source_platform": "南开大学校内 OJ",
        "source_problem_id": "1001",
        "sample_input": "3\n1 3 7",
        "sample_output": "4",
    }
    body.update(overrides)
    return body


def _reject_model(_messages, **_kwargs):
    raise AssertionError("草稿和提交不应调用模型")


def test_draft_is_saved_per_problem(monkeypatch) -> None:
    monkeypatch.setattr("app.services.problem_service.complete_json", _reject_model)
    first = client.post("/api/problems/import", json=problem_body(source_problem_id="8101")).json()["problem"]["id"]
    second = client.post("/api/problems/import", json=problem_body(source_problem_id="8102", title="另一题")).json()["problem"]["id"]
    assert client.get(f"/api/problems/{first}/draft").json() == {
        "problem_id": first,
        "language": "cpp",
        "source_code": "",
        "updated_at": None,
        "saved": False,
    }
    saved = client.put(f"/api/problems/{first}/draft", json={"source_code": "int  a = 1;\n", "language": "cpp"})
    assert saved.status_code == 200
    assert saved.json()["source_code"] == "int  a = 1;\n"
    assert saved.json()["saved"] is True
    assert client.put(f"/api/problems/{first}/draft", json={"source_code": CODE_A}).json()["source_code"] == CODE_A
    assert client.get(f"/api/problems/{first}/draft").json()["source_code"] == CODE_A
    assert client.get(f"/api/problems/{second}/draft").json()["source_code"] == ""
    with Session(engine) as session:
        assert len(session.exec(select(ProblemCodeDraft).where(ProblemCodeDraft.problem_id == first)).all()) == 1


def test_submissions_stay_distinct_from_drafts(monkeypatch) -> None:
    monkeypatch.setattr("app.services.problem_service.complete_json", _reject_model)
    problem_id = client.post("/api/problems/import", json=problem_body(source_problem_id="8201")).json()["problem"]["id"]
    assert client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": "   \n"}).status_code == 422
    assert client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": ""}).status_code == 422
    first = client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": CODE_A})
    second = client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": CODE_B})
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["status"] == "unjudged"
    assert first.json()["judged"] is False
    assert first.json()["message"] == "代码已提交，尚未判题"
    assert first.json()["source_code"] == CODE_A
    client.put(f"/api/problems/{problem_id}/draft", json={"source_code": "draft only"})
    listed = client.get(f"/api/problems/{problem_id}/submissions").json()["submissions"]
    assert [item["id"] for item in listed] == [second.json()["id"], first.json()["id"]]
    assert all("source_code" not in item for item in listed)
    assert listed[1]["code_length"] == len(CODE_A)
    detail = client.get(f"/api/submissions/{first.json()['id']}").json()
    assert detail["source_code"] == CODE_A
    assert client.get(f"/api/problems/{problem_id}/draft").json()["source_code"] == "draft only"


def test_other_user_cannot_read_and_delete_problem_cleans_code() -> None:
    problem_id = client.post("/api/problems/import", json=problem_body(source_problem_id="8301")).json()["problem"]["id"]
    client.put(f"/api/problems/{problem_id}/draft", json={"source_code": CODE_A})
    submission_id = client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": CODE_B}).json()["id"]
    with Session(engine) as session:
        other = User(username="other-submission")
        session.add(other)
        session.commit()
        session.refresh(other)
        row = session.get(ProblemSubmission, submission_id)
        assert row is not None
        row.user_id = other.id
        session.add(row)
        session.commit()
    assert client.get(f"/api/submissions/{submission_id}").status_code == 404
    assert client.delete(f"/api/submissions/{submission_id}").status_code == 404
    with Session(engine) as session:
        assert session.get(ProblemSubmission, submission_id) is not None
        parent = session.get(Problem, problem_id)
        other = session.exec(select(User).where(User.username == "other-submission")).one()
        assert parent is not None
        parent.user_id = other.id
        session.add(parent)
        session.commit()
    assert client.get(f"/api/problems/{problem_id}/draft").status_code == 404
    assert client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": CODE_A}).status_code == 404
    with Session(engine) as session:
        local = session.exec(select(User).where(User.username == "local")).one()
        parent = session.get(Problem, problem_id)
        row = session.get(ProblemSubmission, submission_id)
        assert parent is not None and row is not None
        parent.user_id = local.id
        row.user_id = local.id
        session.add(parent)
        session.add(row)
        session.commit()
    assert client.delete(f"/api/submissions/{submission_id}").status_code == 204
    assert client.get(f"/api/submissions/{submission_id}").status_code == 404
    client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": CODE_A})
    assert client.delete(f"/api/problems/{problem_id}").status_code == 204
    with Session(engine) as session:
        assert session.exec(select(ProblemCodeDraft).where(ProblemCodeDraft.problem_id == problem_id)).all() == []
        assert session.exec(select(ProblemSubmission).where(ProblemSubmission.problem_id == problem_id)).all() == []


def test_submission_service_does_not_execute_code_or_call_model() -> None:
    source = inspect.getsource(submission_service)
    assert "subprocess" not in source
    assert "complete_json" not in source
    assert "os.system" not in source
