"""知识检测。模型调用全部替换成假函数。"""

import json

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models.goal import LearningGoal
from app.models.knowledge import KnowledgePoint
from app.models.quiz import Quiz, QuizAnswer
from app.models.user import User
from app.services.ai.errors import AIError

client = TestClient(app)


def goal_payload(**overrides: object) -> dict:
    payload = {
        "title": "梯度检测",
        "description": "用一个很小的数字例子理解梯度下降怎样更新参数。",
        "target_date": "2026-12-31",
        "daily_minutes": 25,
    }
    payload.update(overrides)
    return payload


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


def question(point_id: int, question_type: str, answer: str, stem: str, difficulty: str = "basic") -> dict:
    options = []
    if question_type == "single":
        options = [
            {"key": "A", "text": "参数沿梯度反方向更新"},
            {"key": "B", "text": "参数沿梯度方向增大"},
            {"key": "C", "text": "学习率只改变样本数量"},
        ]
    elif question_type == "multiple":
        options = [
            {"key": "A", "text": "梯度指出增长最快的方向"},
            {"key": "B", "text": "学习率决定步子大小"},
            {"key": "C", "text": "更新时通常减去梯度"},
        ]
    return {
        "question_type": question_type,
        "difficulty": difficulty,
        "stem": stem,
        "options": options,
        "correct_answer": answer,
        "explanation": "这道题要看清梯度和参数更新方向的关系，而不是只记公式。",
        "knowledge_point_id": point_id,
    }


def quiz_body(point_id: int, perfect: bool = False) -> dict:
    if perfect:
        questions = [
            question(point_id, "single", "A", f"第{index}题：参数为什么要减去梯度？")
            for index in range(1, 6)
        ]
    else:
        questions = [
            question(point_id, "single", "A", "参数更新时，应该朝哪个方向走？"),
            question(point_id, "true_false", "T", "判断：学习率越大，同一次更新的步子通常越大。"),
            question(point_id, "multiple", "A,C", "哪些说法符合这次学习的梯度更新？", "medium"),
            question(point_id, "short", "参数要沿梯度反方向走一小步。", "用一句话说明梯度下降在改什么。", "medium"),
            question(point_id, "scenario", "先减小学习率，避免一次迈过最低点。", "如果一步更新后损失反而变大，下一步怎么处理？"),
        ]
    return {"title": "梯度概念检测", "questions": questions}


def prepare_task(monkeypatch, title: str = "梯度检测") -> tuple[int, int, int]:
    monkeypatch.setattr("app.services.planning_service.complete_json", lambda _messages: json.dumps(plan_payload()))
    goal_id = client.post("/api/goals", json=goal_payload(title=title)).json()["id"]
    plan = client.post("/api/plans/generate", json={"goal_id": goal_id}).json()["plan"]
    task_id = plan["tasks"][0]["id"]
    client.patch(f"/api/tasks/{task_id}/status", json={"status": "completed"})
    with Session(engine) as session:
        point_id = session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id == goal_id)).one().id
    return goal_id, task_id, point_id


def answers_for(quiz: dict, perfect: bool = False) -> dict:
    items = []
    for question_item in quiz["questions"]:
        if perfect or question_item["question_type"] == "single":
            answer = "A"
        elif question_item["question_type"] == "true_false":
            answer = "T"
        elif question_item["question_type"] == "multiple":
            answer = "A"
        else:
            answer = "我用自己的话说：参数沿着让损失下降的方向改一点点。"
        items.append({"question_id": question_item["id"], "answer": answer})
    return {"answers": items}


def test_generate_hides_answers_and_reuses_ready_quiz(monkeypatch) -> None:
    _goal_id, task_id, point_id = prepare_task(monkeypatch, "隐藏答案")
    calls = {"n": 0}

    def fake(_messages: list[dict[str, str]]) -> str:
        calls["n"] += 1
        return json.dumps(quiz_body(point_id))

    monkeypatch.setattr("app.services.quiz_service.complete_json", fake)
    created = client.post("/api/quizzes/generate", json={"task_id": task_id})
    again = client.post("/api/quizzes/generate", json={"task_id": task_id})

    assert created.status_code == 200
    quiz = created.json()
    assert quiz["question_count"] == 5
    assert "correct_answer" not in quiz["questions"][0]
    assert "explanation" not in quiz["questions"][0]
    assert again.json()["id"] == quiz["id"]
    assert calls["n"] == 1


def test_invalid_quiz_json_is_not_saved(monkeypatch) -> None:
    _goal_id, task_id, _point_id = prepare_task(monkeypatch, "无效试卷")
    calls = {"n": 0}

    def fake(_messages: list[dict[str, str]]) -> str:
        calls["n"] += 1
        return "不是 JSON"

    monkeypatch.setattr("app.services.quiz_service.complete_json", fake)
    response = client.post("/api/quizzes/generate", json={"task_id": task_id})

    assert response.status_code == 502
    assert calls["n"] == 2
    with Session(engine) as session:
        assert session.exec(select(Quiz)).first() is None


def test_incomplete_question_is_rejected(monkeypatch) -> None:
    _goal_id, task_id, point_id = prepare_task(monkeypatch, "缺字段")
    payload = quiz_body(point_id)
    del payload["questions"][0]["stem"]
    monkeypatch.setattr("app.services.quiz_service.complete_json", lambda _messages: json.dumps(payload))

    response = client.post("/api/quizzes/generate", json={"task_id": task_id})

    assert response.status_code == 502
    with Session(engine) as session:
        assert session.exec(select(Quiz)).first() is None


def test_objective_and_short_answers_are_scored(monkeypatch) -> None:
    goal_id, task_id, point_id = prepare_task(monkeypatch, "混合评分")

    def fake(messages: list[dict[str, str]]) -> str:
        if "请为下面的回答评分" in messages[-1]["content"]:
            body = json.loads(messages[-1]["content"].split("\n", 1)[1])
            return json.dumps(
                {
                    "grades": [
                        {
                            "question_id": item["question_id"],
                            "score": 80 if "一句话" in item["stem"] else 40,
                            "max_score": 100,
                            "correct": "一句话" in item["stem"],
                            "error_reason": "" if "一句话" in item["stem"] else "没有说明要减小步长",
                            "suggestion": "补上学习率过大时的处理。",
                            "reference_answer": item["reference_answer"],
                        }
                        for item in body["questions"]
                    ]
                }
            )
        return json.dumps(quiz_body(point_id))

    monkeypatch.setattr("app.services.quiz_service.complete_json", fake)
    quiz = client.post("/api/quizzes/generate", json={"task_id": task_id}).json()
    submitted = client.post(f"/api/quizzes/{quiz['id']}/submit", json=answers_for(quiz))

    assert submitted.status_code == 200
    result = submitted.json()
    assert result["score"] == 64
    assert result["correct_count"] == 3
    assert result["wrong_count"] == 2
    assert result["level_label"] == "需要巩固"
    assert result["questions"][2]["is_correct"] is False
    assert result["mastery_updates"][0]["new_level"] == 64
    assert result["mastery_updates"][0]["status"] != "proficient"
    point = client.get(f"/api/knowledge/{point_id}").json()
    assert point["mastery_assessed"] is True
    assert point["status"] == "improving"
    history = client.get(f"/api/knowledge/{point_id}/history").json()
    assert history["events"][0]["previous_level"] is None
    assert client.get("/api/quizzes/history", params={"goal_id": goal_id}).json()["quizzes"][0]["score"] == 64


def test_failed_short_grading_does_not_finish_quiz(monkeypatch) -> None:
    _goal_id, task_id, point_id = prepare_task(monkeypatch, "评分失败")

    def fake(messages: list[dict[str, str]]) -> str:
        if "请为下面的回答评分" in messages[-1]["content"]:
            raise AIError("模拟评分失败")
        return json.dumps(quiz_body(point_id))

    monkeypatch.setattr("app.services.quiz_service.complete_json", fake)
    quiz = client.post("/api/quizzes/generate", json={"task_id": task_id}).json()
    failed = client.post(f"/api/quizzes/{quiz['id']}/submit", json=answers_for(quiz))

    assert failed.status_code == 502
    current = client.get(f"/api/quizzes/{quiz['id']}")
    assert current.json()["status"] == "ready"
    assert "correct_answer" not in current.json()["questions"][0]
    with Session(engine) as session:
        point = session.get(KnowledgePoint, point_id)
        assert point is not None
        assert point.mastery_level == 0
        assert point.status == "learning"
        assert session.exec(select(QuizAnswer)).first() is None


def test_repeat_submit_is_rejected(monkeypatch) -> None:
    _goal_id, task_id, point_id = prepare_task(monkeypatch, "重复提交")
    monkeypatch.setattr("app.services.quiz_service.complete_json", lambda _messages: json.dumps(quiz_body(point_id, perfect=True)))
    quiz = client.post("/api/quizzes/generate", json={"task_id": task_id}).json()
    payload = answers_for(quiz, perfect=True)
    assert client.post(f"/api/quizzes/{quiz['id']}/submit", json=payload).status_code == 200
    assert client.post(f"/api/quizzes/{quiz['id']}/submit", json=payload).status_code == 409


def test_two_high_scores_raise_mastery_gradually(monkeypatch) -> None:
    _goal_id, task_id, point_id = prepare_task(monkeypatch, "连续高分")
    monkeypatch.setattr("app.services.quiz_service.complete_json", lambda _messages: json.dumps(quiz_body(point_id, perfect=True)))
    first = client.post("/api/quizzes/generate", json={"task_id": task_id}).json()
    first_result = client.post(f"/api/quizzes/{first['id']}/submit", json=answers_for(first, perfect=True)).json()
    assert first_result["score"] == 100
    assert first_result["level_label"] == "掌握良好"
    assert first_result["mastery_updates"][0]["new_level"] == 74
    assert first_result["mastery_updates"][0]["status"] == "improving"

    second = client.post("/api/quizzes/generate", json={"task_id": task_id}).json()
    second_result = client.post(f"/api/quizzes/{second['id']}/submit", json=answers_for(second, perfect=True)).json()
    assert second_result["mastery_updates"][0]["previous_level"] == 74
    assert second_result["mastery_updates"][0]["new_level"] == 90
    assert second_result["mastery_updates"][0]["status"] == "proficient"


def test_low_score_marks_needs_review(monkeypatch) -> None:
    _goal_id, task_id, point_id = prepare_task(monkeypatch, "低分巩固")
    monkeypatch.setattr("app.services.quiz_service.complete_json", lambda _messages: json.dumps(quiz_body(point_id, perfect=True)))
    quiz = client.post("/api/quizzes/generate", json={"task_id": task_id}).json()
    wrong = answers_for(quiz, perfect=True)
    for item in wrong["answers"]:
        item["answer"] = "B"
    result = client.post(f"/api/quizzes/{quiz['id']}/submit", json=wrong).json()

    assert result["score"] == 0
    assert result["mastery_updates"][0]["status"] == "needs_review"
    analytics = client.get("/api/learning/analytics").json()
    assert analytics["quiz_count"] == 1
    assert analytics["latest_score"] == 0
    assert analytics["needs_review_count"] == 1
    assert analytics["mastered_count"] == 0
    assert analytics["completed_tasks"] == 1


def test_plan_prompt_receives_mastery(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake(messages: list[dict[str, str]]) -> str:
        captured["text"] = messages[-1]["content"]
        return json.dumps(plan_payload())

    monkeypatch.setattr("app.services.planning_service.complete_json", fake)
    goal_id = client.post("/api/goals", json=goal_payload(title="计划读取掌握度")).json()["id"]
    with Session(engine) as session:
        session.add(
            KnowledgePoint(
                goal_id=goal_id,
                name="反向传播",
                description="误差如何向前一层传递",
                status="needs_review",
                mastery_level=45,
            )
        )
        session.commit()

    assert client.post("/api/plans/generate", json={"goal_id": goal_id}).status_code == 200
    assert "needs_review" in captured["text"]
    assert "45" in captured["text"]


def test_unfinished_task_does_not_call_model(monkeypatch) -> None:
    monkeypatch.setattr("app.services.planning_service.complete_json", lambda _messages: json.dumps(plan_payload()))
    goal_id = client.post("/api/goals", json=goal_payload(title="未完成不能检测")).json()["id"]
    task_id = client.post("/api/plans/generate", json={"goal_id": goal_id}).json()["plan"]["tasks"][0]["id"]

    def fail_if_called(_messages: list[dict[str, str]]) -> str:
        raise AssertionError("未完成的任务不应出题")

    monkeypatch.setattr("app.services.quiz_service.complete_json", fail_if_called)
    assert client.post("/api/quizzes/generate", json={"task_id": task_id}).status_code == 400


def test_delete_goal_removes_quiz(monkeypatch) -> None:
    goal_id, task_id, point_id = prepare_task(monkeypatch, "删除检测")
    monkeypatch.setattr("app.services.quiz_service.complete_json", lambda _messages: json.dumps(quiz_body(point_id, perfect=True)))
    quiz_id = client.post("/api/quizzes/generate", json={"task_id": task_id}).json()["id"]

    assert client.delete(f"/api/goals/{goal_id}").status_code == 204
    assert client.get(f"/api/quizzes/{quiz_id}").status_code == 404
    assert client.get(f"/api/knowledge/{point_id}").status_code == 404


def test_other_user_cannot_read_quiz(monkeypatch) -> None:
    _goal_id, task_id, point_id = prepare_task(monkeypatch, "隔离检测")
    monkeypatch.setattr("app.services.quiz_service.complete_json", lambda _messages: json.dumps(quiz_body(point_id, perfect=True)))
    quiz_id = client.post("/api/quizzes/generate", json={"task_id": task_id}).json()["id"]
    with Session(engine) as session:
        other = User(username="other")
        session.add(other)
        session.commit()
        session.refresh(other)
        goal = session.exec(select(LearningGoal).where(LearningGoal.title == "隔离检测")).one()
        goal.user_id = other.id
        session.add(goal)
        session.commit()

    assert client.get(f"/api/quizzes/{quiz_id}").status_code == 404
    assert client.get(f"/api/knowledge/{point_id}").status_code == 404


def test_failed_commit_does_not_mark_quiz_completed(monkeypatch) -> None:
    _goal_id, task_id, point_id = prepare_task(monkeypatch, "事务回滚")
    monkeypatch.setattr("app.services.quiz_service.complete_json", lambda _messages: json.dumps(quiz_body(point_id, perfect=True)))
    quiz = client.post("/api/quizzes/generate", json={"task_id": task_id}).json()

    def fail(_session: Session) -> None:
        raise HTTPException(status_code=500, detail="保存失败，请稍后重试")

    monkeypatch.setattr("app.services.quiz_service.goal_service.commit_or_raise", fail)
    response = client.post(f"/api/quizzes/{quiz['id']}/submit", json=answers_for(quiz, perfect=True))

    assert response.status_code == 500
    assert client.get(f"/api/quizzes/{quiz['id']}").json()["status"] == "ready"
