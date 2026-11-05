"""题目讲解和知识点讲解。模型调用全部替换成假函数。"""

import json

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models.explain import QuestionExplanation
from app.models.review import ReviewSchedule
from app.services.ai.explain_parser import parse_knowledge_explain, parse_question_explain
from app.services.review_service import local_today
from tests.test_quizzes import answers_for, prepare_task, quiz_body
from tests.test_reviews import perfect_quiz

client = TestClient(app)


def question_payload() -> dict:
    return {
        "focus": "考查梯度下降时参数应该沿什么方向更新。",
        "correct_answer": "A",
        "walkthrough": "损失增大最快的方向是梯度方向，因此参数要沿反方向走一小步。",
        "error_analysis": "用户选择了沿梯度增大参数，这会让损失继续上升。",
        "extension": "可以想成下山：每一步朝更低的方向走，而不是朝更陡的上坡走。",
    }


def knowledge_payload() -> dict:
    return {
        "definition": "梯度下降是一种沿着损失下降方向逐步更新参数的优化方法。",
        "why": "许多模型要用它在可计算的时间内找到一组更好的参数。",
        "principles": "梯度指向函数增大最快的方向，因此更新时通常减去学习率乘梯度。",
        "process": "先计算当前点的梯度，再按学习率迈出一步，然后重复直到变化很小。",
        "examples": "如果梯度是 2、学习率是 0.1，参数就减去 0.2。",
        "pitfalls": "学习率过大可能越过最低点，过小则收敛很慢。",
        "summary": "记住方向和步长：朝损失下降的方向走，并用学习率控制步伐。",
    }


def test_parsers_require_complete_fields() -> None:
    text = parse_question_explain(json.dumps(question_payload()))
    assert "考查知识点" in text
    assert "错误分析" in text
    lecture = parse_knowledge_explain(json.dumps(knowledge_payload()))
    assert "这个知识点是什么" in lecture


def test_question_explain_uses_user_answer_and_is_cached(monkeypatch) -> None:
    _goal_id, task_id, point_id = prepare_task(monkeypatch, "题目讲解")
    monkeypatch.setattr("app.services.quiz_service.complete_json", lambda _messages, **_kwargs: json.dumps(quiz_body(point_id, perfect=True)))
    quiz = client.post("/api/quizzes/generate", json={"task_id": task_id}).json()
    question_id = quiz["questions"][0]["id"]
    assert client.post(f"/api/quizzes/{quiz['id']}/questions/{question_id}/explain").status_code == 409
    submitted = client.post(f"/api/quizzes/{quiz['id']}/submit", json=answers_for(quiz, perfect=True))
    assert submitted.status_code == 200
    mastery_before = client.get(f"/api/knowledge/{point_id}").json()["mastery_level"]
    calls = {"n": 0}

    def fake(messages: list[dict[str, str]], **_kwargs) -> str:
        calls["n"] += 1
        assert "user" in messages[-1]["content"]
        assert "is_correct" in messages[-1]["content"]
        return json.dumps(question_payload())

    monkeypatch.setattr("app.services.explain_service.complete_json", fake)
    first = client.post(f"/api/quizzes/{quiz['id']}/questions/{question_id}/explain")
    second = client.post(f"/api/quizzes/{quiz['id']}/questions/{question_id}/explain")
    assert first.status_code == 200
    assert "考查知识点" in first.json()["content"]
    assert second.json()["content"] == first.json()["content"]
    assert calls["n"] == 1
    result = client.get(f"/api/quizzes/{quiz['id']}/result").json()
    assert result["questions"][0]["has_explanation"] is True
    assert client.get(f"/api/knowledge/{point_id}").json()["mastery_level"] == mastery_before
    with Session(engine) as session:
        assert session.exec(select(QuestionExplanation)).one().question_id == question_id


def test_question_explain_invalid_json_is_not_saved(monkeypatch) -> None:
    _goal_id, task_id, point_id = prepare_task(monkeypatch, "讲解失败")
    monkeypatch.setattr("app.services.quiz_service.complete_json", lambda _messages, **_kwargs: json.dumps(quiz_body(point_id, perfect=True)))
    quiz = client.post("/api/quizzes/generate", json={"task_id": task_id}).json()
    submitted = client.post(f"/api/quizzes/{quiz['id']}/submit", json=answers_for(quiz, perfect=True))
    assert submitted.status_code == 200
    monkeypatch.setattr("app.services.explain_service.complete_json", lambda _messages, **_kwargs: "不是 JSON")
    question_id = quiz["questions"][0]["id"]
    assert client.post(f"/api/quizzes/{quiz['id']}/questions/{question_id}/explain").status_code == 502
    assert client.get(f"/api/quizzes/{quiz['id']}/questions/{question_id}/explain").status_code == 404


def test_knowledge_explain_and_followup_do_not_change_mastery(monkeypatch) -> None:
    _goal_id, task_id, point_id = prepare_task(monkeypatch, "知识点讲解")
    monkeypatch.setattr("app.services.quiz_service.complete_json", lambda _messages, **_kwargs: json.dumps(quiz_body(point_id, perfect=True)))
    quiz = client.post("/api/quizzes/generate", json={"task_id": task_id}).json()
    submitted = client.post(f"/api/quizzes/{quiz['id']}/submit", json=answers_for(quiz, perfect=True)).json()
    schedule_id = submitted["reviews"][0]["id"]
    mastery_before = client.get(f"/api/knowledge/{point_id}").json()["mastery_level"]
    monkeypatch.setattr("app.services.explain_service.complete_json", lambda _messages, **_kwargs: json.dumps(knowledge_payload()))
    empty = client.get(f"/api/reviews/{schedule_id}/explain").json()
    assert empty["messages"] == []
    lecture = client.post(f"/api/reviews/{schedule_id}/explain")
    assert lecture.status_code == 200
    assert lecture.json()["messages"][0]["role"] == "assistant"
    again = client.post(f"/api/reviews/{schedule_id}/explain")
    assert len(again.json()["messages"]) == 1
    monkeypatch.setattr(
        "app.services.explain_service.complete_json",
        lambda _messages, **_kwargs: json.dumps({"reply": "可以用下山来理解：每一步朝更低的方向走一小步。"}),
    )
    follow = client.post(f"/api/reviews/{schedule_id}/explain/messages", json={"content": "能不能举个更简单的例子？"})
    assert follow.status_code == 200
    assert len(follow.json()["messages"]) == 3
    assert client.get(f"/api/knowledge/{point_id}").json()["mastery_level"] == mastery_before
    with Session(engine) as session:
        schedule = session.get(ReviewSchedule, schedule_id)
        assert schedule is not None
        assert schedule.last_score == submitted["score"]


def test_review_quiz_explain_reuses_question_service(monkeypatch) -> None:
    _goal_id, task_id, point_id = prepare_task(monkeypatch, "复习题讲解")
    monkeypatch.setattr("app.services.quiz_service.complete_json", lambda _messages, **_kwargs: json.dumps(perfect_quiz(point_id)))
    quiz = client.post("/api/quizzes/generate", json={"task_id": task_id}).json()
    submitted = client.post(f"/api/quizzes/{quiz['id']}/submit", json=answers_for(quiz, perfect=True)).json()
    schedule_id = submitted["reviews"][0]["id"]
    with Session(engine) as session:
        schedule = session.get(ReviewSchedule, schedule_id)
        assert schedule is not None
        schedule.next_review_date = local_today()
        session.add(schedule)
        session.commit()
    monkeypatch.setattr("app.services.review_service.complete_json", lambda _messages, **_kwargs: json.dumps(perfect_quiz(point_id)))
    paper = client.post(f"/api/reviews/{schedule_id}/start").json()
    answers = {"answers": [{"question_id": item["id"], "answer": "A"} for item in paper["questions"]]}
    result = client.post(f"/api/quizzes/{paper['id']}/submit", json=answers)
    assert result.status_code == 200
    assert result.json()["task_id"] is None
    monkeypatch.setattr("app.services.explain_service.complete_json", lambda _messages, **_kwargs: json.dumps(question_payload()))
    explained = client.post(f"/api/quizzes/{paper['id']}/questions/{paper['questions'][0]['id']}/explain")
    assert explained.status_code == 200
    assert "详细解析" in explained.json()["content"]
