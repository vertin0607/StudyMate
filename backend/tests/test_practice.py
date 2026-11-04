"""练习状态、练习记录和错题。不判题，不调用模型，不改掌握度。"""

import inspect

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models.practice import ProblemLearningStatus, ProblemPracticeRecord, ProblemWrongRecord
from app.models.problem import Problem
from app.models.submission import ProblemSubmission
from app.models.user import User
from app.services import practice_service
from app.services.practice_service import mastery_and_review_counts

client = TestClient(app)


def problem_body(**overrides) -> dict:
    body = {
        "title": "练习题",
        "description": "记录练习过程，不判断代码对错。",
        "source_platform": "南开大学校内 OJ",
        "source_problem_id": "8300",
    }
    body.update(overrides)
    return body


def _reject_model(_messages, **_kwargs):
    raise AssertionError("练习记录不应调用模型")


def test_status_practice_and_statistics_stay_separate_from_judging(monkeypatch) -> None:
    monkeypatch.setattr("app.services.problem_service.complete_json", _reject_model)
    with Session(engine) as session:
        before = mastery_and_review_counts(session)
    first = client.post("/api/problems/import", json=problem_body(source_problem_id="8310")).json()["problem"]["id"]
    second = client.post("/api/problems/import", json=problem_body(source_problem_id="8311", title="另一题")).json()["problem"]["id"]
    assert client.get(f"/api/problems/{first}/learning-status").json()["status"] == "todo"
    assert client.patch(f"/api/problems/{first}/learning-status", json={"status": "accepted"}).status_code == 422
    assert client.patch(f"/api/problems/{first}/learning-status", json={"status": "self_completed"}).json()["status"] == "self_completed"
    started = client.post(f"/api/problems/{second}/practice/start").json()
    assert started["created"] is True
    again = client.post(f"/api/problems/{second}/practice/start").json()
    assert again["created"] is False
    assert again["record"]["id"] == started["record"]["id"]
    assert client.get(f"/api/problems/{second}/learning-status").json()["status"] == "attempting"
    unfinished = client.post(
        f"/api/problems/{second}/practice/{started['record']['id']}/complete",
        json={"completion_type": "unfinished", "note": "先停一下"},
    )
    assert unfinished.json()["completion_type"] == "unfinished"
    assert unfinished.json()["open"] is False
    second_round = client.post(f"/api/problems/{second}/practice/start").json()
    assert second_round["created"] is True
    done = client.post(
        f"/api/problems/{second}/practice/{second_round['record']['id']}/complete",
        json={"completion_type": "with_hint", "note": "看了边界"},
    )
    assert done.json()["used_hint"] is True
    assert done.json()["viewed_solution"] is False
    assert client.post(
        f"/api/problems/{second}/practice/{second_round['record']['id']}/complete",
        json={"completion_type": "independent"},
    ).status_code == 409
    history = client.get(f"/api/problems/{second}/practice-history").json()["records"]
    assert len(history) == 2
    assert client.get(f"/api/problems/{first}/practice-history").json()["records"] == []
    assert client.get(f"/api/problems/{second}/learning-status").json()["status"] == "attempting"
    stats = client.get("/api/problems/practice-statistics").json()
    assert stats["total"] == 2
    assert stats["self_completed"] == 1
    assert stats["attempting"] == 1
    assert stats["accepted"] == 0
    assert stats["wrong_answer"] == 0
    assert stats["practice_total"] == 2
    assert stats["started_problems"] == 1
    assert stats["practice_today"] == 2
    assert stats["submission_count"] == 0
    assert stats["wrong_count"] == 0
    trends = client.get("/api/problems/practice-trends").json()["days"]
    assert len(trends) == 7
    assert trends[-1]["practice_count"] == 2
    assert trends[-1]["submission_count"] == 0
    with Session(engine) as session:
        assert mastery_and_review_counts(session) == before


def test_wrong_mark_does_not_judge_submission(monkeypatch) -> None:
    monkeypatch.setattr("app.services.problem_service.complete_json", _reject_model)
    problem_id = client.post("/api/problems/import", json=problem_body(source_problem_id="8320")).json()["problem"]["id"]
    assert client.put(f"/api/problems/{problem_id}/classification", json={"course": "数据结构与算法", "difficulty": "medium", "links": []}).status_code == 200
    submission = client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": "int main(){return 0;}\n"})
    assert submission.json()["status"] == "unjudged"
    assert client.get("/api/problems/wrong").json()["problems"] == []
    created = client.post(
        f"/api/problems/{problem_id}/wrong",
        json={"reason_type": "boundary", "reason_detail": "漏了 n=1", "related_submission_id": submission.json()["id"]},
    )
    assert created.status_code == 201
    assert client.post(f"/api/problems/{problem_id}/wrong", json={"reason_type": "syntax", "reason_detail": "重复"}).status_code == 409
    updated = client.put(
        f"/api/problems/{problem_id}/wrong",
        json={"reason_type": "implementation", "reason_detail": "循环写反了", "related_submission_id": submission.json()["id"]},
    )
    assert updated.json()["reason_type"] == "implementation"
    listed = client.get("/api/problems/wrong", params={"difficulty": "medium"}).json()["problems"]
    assert listed[0]["reason_detail"] == "循环写反了"
    assert client.get(f"/api/submissions/{submission.json()['id']}").json()["status"] == "unjudged"
    assert client.delete(f"/api/problems/{problem_id}/wrong").status_code == 204
    assert client.get("/api/problems/wrong").json()["problems"] == []
    stats = client.get("/api/problems/practice-statistics").json()
    assert stats["submission_count"] == 1
    assert stats["wrong_count"] == 0
    assert stats["accepted"] == 0
    assert stats["practice_total"] == 0


def test_other_user_cannot_read_and_delete_cleans_practice() -> None:
    problem_id = client.post("/api/problems/import", json=problem_body(source_problem_id="8330")).json()["problem"]["id"]
    client.patch(f"/api/problems/{problem_id}/learning-status", json={"status": "attempting"})
    record_id = client.post(f"/api/problems/{problem_id}/practice/start").json()["record"]["id"]
    client.post(f"/api/problems/{problem_id}/wrong", json={"reason_type": "other", "reason_detail": "自己的错题"})
    with Session(engine) as session:
        other = User(username="other-practice")
        session.add(other)
        session.commit()
        session.refresh(other)
        parent = session.get(Problem, problem_id)
        assert parent is not None
        parent.user_id = other.id
        session.add(parent)
        session.commit()
    assert client.get(f"/api/problems/{problem_id}/learning-status").status_code == 404
    assert client.get(f"/api/problems/{problem_id}/practice-history").status_code == 404
    assert client.patch(f"/api/problems/{problem_id}/learning-status", json={"status": "todo"}).status_code == 404
    with Session(engine) as session:
        local = session.exec(select(User).where(User.username == "local")).one()
        parent = session.get(Problem, problem_id)
        status = session.exec(select(ProblemLearningStatus).where(ProblemLearningStatus.problem_id == problem_id)).one()
        assert parent is not None
        parent.user_id = local.id
        status.status = "accepted"
        session.add(parent)
        session.add(status)
        session.commit()
    locked = client.patch(f"/api/problems/{problem_id}/learning-status", json={"status": "todo"})
    assert locked.status_code == 409
    assert client.get(f"/api/problems/{problem_id}/learning-status").json()["status"] == "accepted"
    assert client.delete(f"/api/problems/{problem_id}").status_code == 204
    with Session(engine) as session:
        assert session.get(ProblemPracticeRecord, record_id) is None
        assert session.exec(select(ProblemLearningStatus).where(ProblemLearningStatus.problem_id == problem_id)).all() == []
        assert session.exec(select(ProblemWrongRecord).where(ProblemWrongRecord.problem_id == problem_id)).all() == []
        assert session.exec(select(ProblemSubmission)).all() == []


def test_practice_service_does_not_execute_code_or_call_model() -> None:
    source = inspect.getsource(practice_service)
    assert "subprocess" not in source
    assert "complete_json" not in source
    assert "os.system" not in source
