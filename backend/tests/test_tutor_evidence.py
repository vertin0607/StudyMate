"""导师证据溯源。模型调用全部使用假响应。"""

import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.database import engine
from app.main import app
from app.models.judge import ProblemJudgeResult
from app.models.knowledge import KnowledgePoint
from app.models.practice import ProblemLearningStatus, ProblemWrongRecord
from app.models.problem import Problem, ProblemTopic, ProblemTopicLink
from app.models.quiz import KnowledgeMasteryEvent, Quiz, QuizAnswer, QuizQuestion
from app.models.review import ReviewRecord, ReviewSchedule
from app.models.submission import ProblemSubmission
from app.models.topic_link import TopicKnowledgeLink
from app.models.tutor import TutorMessage
from app.models.user import User
from app.services.ai.errors import AIError
from app.services.goal_service import ensure_local_user
from app.services.tutor_evidence import (
    analyze_message,
    dedupe_evidence,
    is_formal_pass,
    memory_dedup_key,
    next_memory_status,
    public_diagnosis,
)

client = TestClient(app)
NOW = datetime(2026, 11, 4, tzinfo=timezone.utc)


def _goal(title: str = "证据目标") -> int:
    response = client.post(
        "/api/goals",
        json={"title": title, "description": "只用于证据测试。", "target_date": "2026-12-31", "daily_minutes": 25},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _point(goal_id: int, name: str, mastery: int = 0, status: str = "not_started") -> int:
    with Session(engine) as session:
        point = KnowledgePoint(goal_id=goal_id, name=name, mastery_level=mastery, status=status)
        session.add(point)
        session.commit()
        session.refresh(point)
        return point.id


def _analyze(goal_id: int | None, question: str) -> dict:
    with Session(engine) as session:
        user = ensure_local_user(session)
        return analyze_message(session, user_id=user.id, goal_id=goal_id, question=question)


def _problem(user_id: int, title: str) -> int:
    with Session(engine) as session:
        problem = Problem(user_id=user_id, title=title, created_at=NOW, updated_at=NOW)
        session.add(problem)
        session.commit()
        session.refresh(problem)
        return problem.id


def _submission(user_id: int, problem_id: int, code: str, minutes: int = 0) -> int:
    with Session(engine) as session:
        row = ProblemSubmission(
            user_id=user_id,
            problem_id=problem_id,
            source_code=code,
            status="judged",
            submitted_at=NOW + timedelta(minutes=minutes),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def _judge(user_id: int, problem_id: int, submission_id: int, status: str, compile_output: str = "") -> None:
    with Session(engine) as session:
        session.add(
            ProblemJudgeResult(
                user_id=user_id,
                problem_id=problem_id,
                submission_id=submission_id,
                status=status,
                compile_output=compile_output,
                judged_at=NOW,
            )
        )
        session.commit()


def test_explicit_concept_error() -> None:
    goal_id = _goal()
    point_id = _point(goal_id, "梯度下降", mastery=90, status="mastered")
    with Session(engine) as session:
        session.add(
            KnowledgeMasteryEvent(
                knowledge_point_id=point_id,
                previous_level=None,
                new_level=90,
                quiz_score=90,
                reason="检测",
            )
        )
        session.commit()
    analysis = _analyze(goal_id, "梯度下降就是不断寻找损失函数的最小值，然后直接得到最优参数。")
    assert analysis["category"] == "concept"
    assert analysis["evidence_status"] == "suspected"
    assert analysis["knowledge_point_id"] == point_id
    assert analysis["teaching_strategy"] == "basic"
    diagnosis = public_diagnosis(analysis)
    assert diagnosis is not None
    assert diagnosis["evidence_status"] == "suspected"


def test_explicit_formula_error() -> None:
    goal_id = _goal()
    _point(goal_id, "链式法则")
    analysis = _analyze(goal_id, r"我认为链式法则是 $\frac{\partial L}{\partial x}=\frac{\partial L}{\partial y}+\frac{\partial y}{\partial x}$。")
    assert analysis["category"] == "formula"
    assert analysis["evidence_status"] == "confirmed"
    assert analysis["knowledge_point_name"] == "链式法则"
    assert analysis["teaching_strategy"] == "basic"
    assert public_diagnosis(analysis)["category"] == "formula"


def test_explicit_reasoning_error() -> None:
    analysis = _analyze(None, "前向传播和反向传播我都知道，但反向传播不需要从输出层向前计算，每一层可以同时求。")
    assert analysis["category"] == "reasoning"
    assert analysis["evidence_status"] == "suspected"
    assert analysis["teaching_strategy"] == "intermediate"
    assert analysis["knowledge_point_id"] is None


def test_explicit_algorithm_error() -> None:
    analysis = _analyze(None, "KMP 的 next[0] = -1，这个定义和前缀函数的最长真前缀是一回事。")
    assert analysis["category"] == "algorithm"
    assert analysis["evidence_status"] == "suspected"
    assert analysis["teaching_strategy"] == "intermediate"


def test_compile_error_uses_latest_code_only() -> None:
    goal_id = _goal()
    with Session(engine) as session:
        user = ensure_local_user(session)
        user_id = user.id
    problem_id = _problem(user_id, "编译样例题")
    other_id = _problem(user_id, "另一道题")
    old_submission = _submission(user_id, problem_id, "OLD-CODE", minutes=0)
    latest_submission = _submission(user_id, problem_id, "LATEST-CODE", minutes=5)
    _submission(user_id, other_id, "OTHER-PROBLEM-CODE", minutes=6)
    _judge(user_id, problem_id, old_submission, "compile_error", "error: expected ';'")
    _judge(user_id, problem_id, latest_submission, "compile_error", "error: expected ';'")
    analysis = _analyze(goal_id, "编译样例题为什么编译不过？")
    assert analysis["category"] == "implementation"
    assert analysis["evidence_status"] == "confirmed"
    assert analysis["teaching_strategy"] == "code_debugging"
    assert analysis["model_context"]["latest_code"] == "LATEST-CODE"
    assert "OTHER-PROBLEM-CODE" not in json.dumps(analysis["model_context"], ensure_ascii=False)
    assert "OLD-CODE" not in json.dumps(analysis["model_context"], ensure_ascii=False)
    assert analysis["direct_event_count"] == 2


def test_implementation_error_from_code() -> None:
    analysis = _analyze(None, "循环边界写错了。\n```cpp\nfor (int i = 0; i <= n; i++) a[i] = 1;\n```")
    assert analysis["category"] == "implementation"
    assert analysis["evidence_status"] == "confirmed"
    assert analysis["teaching_strategy"] == "code_debugging"
    assert "a[i] = 1" in analysis["model_context"]["latest_code"]


def test_boundary_error() -> None:
    analysis = _analyze(None, "普通样例能过，但空数组和只有一个元素会错。")
    assert analysis["category"] == "boundary"
    assert analysis["evidence_status"] == "suspected"
    assert analysis["teaching_strategy"] == "code_debugging"


def test_plain_question_is_not_classified() -> None:
    goal_id = _goal()
    _point(goal_id, "梯度")
    analysis = _analyze(goal_id, "梯度到底是什么？")
    assert analysis["category"] == "none"
    assert analysis["evidence_status"] == "insufficient_data"
    assert public_diagnosis(analysis) is None


def test_vague_statement_is_insufficient() -> None:
    analysis = _analyze(None, "我有点乱，说不清楚。")
    assert analysis["category"] == "none"
    assert analysis["vague"] is True
    assert analysis["evidence_status"] == "insufficient_data"
    assert public_diagnosis(analysis) is None


def test_low_mastery_alone_is_not_confirmed() -> None:
    goal_id = _goal()
    point_id = _point(goal_id, "梯度", mastery=30, status="needs_review")
    with Session(engine) as session:
        session.add(
            KnowledgeMasteryEvent(
                knowledge_point_id=point_id,
                previous_level=None,
                new_level=30,
                quiz_score=30,
                reason="一次低分",
            )
        )
        session.commit()
    analysis = _analyze(goal_id, "梯度是什么？")
    assert analysis["category"] == "none"
    assert analysis["evidence_status"] == "insufficient_data"
    assert public_diagnosis(analysis) is None
    assert analysis["teaching_strategy"] == "basic"


def test_existing_diagnosis_does_not_become_a_new_error() -> None:
    goal_id = _goal()
    point_id = _point(goal_id, "梯度", mastery=40, status="needs_review")
    with Session(engine) as session:
        session.add(KnowledgeMasteryEvent(knowledge_point_id=point_id, previous_level=None, new_level=40, quiz_score=40, reason="第一次"))
        session.add(KnowledgeMasteryEvent(knowledge_point_id=point_id, previous_level=40, new_level=40, quiz_score=40, reason="第二次"))
        session.commit()
    analysis = _analyze(goal_id, "梯度是什么？")
    assert analysis["category"] == "none"
    assert "diagnosis" in "".join(analysis["evidence_keys"])
    assert analysis["direct_event_count"] == 0


def test_system_error_is_not_user_error() -> None:
    with Session(engine) as session:
        user_id = ensure_local_user(session).id
    problem_id = _problem(user_id, "环境异常题")
    submission_id = _submission(user_id, problem_id, "int main(){return 0;}")
    _judge(user_id, problem_id, submission_id, "system_error", "docker failed")
    analysis = _analyze(None, "环境异常题这次是什么情况？")
    assert analysis["category"] == "none"
    assert analysis["direct_event_count"] == 0
    assert analysis["model_context"]["latest_code"] is None


def test_unjudged_is_not_user_error() -> None:
    with Session(engine) as session:
        user_id = ensure_local_user(session).id
    problem_id = _problem(user_id, "尚未判题题")
    submission_id = _submission(user_id, problem_id, "int main(){return 0;}")
    _judge(user_id, problem_id, submission_id, "unjudged")
    analysis = _analyze(None, "尚未判题题还没有结果吗？")
    assert analysis["category"] == "none"
    assert analysis["direct_event_count"] == 0


def test_self_completed_is_not_formal_pass() -> None:
    assert is_formal_pass(None, "self_completed") is False
    assert is_formal_pass("accepted", "self_completed") is True
    with Session(engine) as session:
        user_id = ensure_local_user(session).id
    problem_id = _problem(user_id, "自评样例题")
    with Session(engine) as session:
        session.add(ProblemLearningStatus(user_id=user_id, problem_id=problem_id, status="self_completed"))
        session.commit()
    analysis = _analyze(None, "自评样例题是不是已经通过了？")
    assert analysis["formal_pass"] is False
    assert analysis["category"] == "none"


def test_wrong_answer_does_not_infer_category() -> None:
    with Session(engine) as session:
        user_id = ensure_local_user(session).id
    problem_id = _problem(user_id, "先序遍历题")
    submission_id = _submission(user_id, problem_id, "int main(){return 0;}")
    _judge(user_id, problem_id, submission_id, "wrong_answer")
    analysis = _analyze(None, "先序遍历题为什么不对？")
    assert analysis["category"] == "none"
    assert analysis["evidence_status"] == "insufficient_data"
    assert public_diagnosis(analysis) is None


def test_unlinked_topic_is_not_attributed() -> None:
    goal_id = _goal()
    point_id = _point(goal_id, "链式法则")
    with Session(engine) as session:
        user_id = ensure_local_user(session).id
        topic = ProblemTopic(user_id=user_id, category="algorithm", name="链式法则")
        session.add(topic)
        session.commit()
        session.refresh(topic)
        problem = Problem(user_id=user_id, title="未关联题", created_at=NOW, updated_at=NOW)
        session.add(problem)
        session.commit()
        session.refresh(problem)
        session.add(ProblemTopicLink(problem_id=problem.id, topic_id=topic.id, relevance="primary"))
        session.add(ProblemWrongRecord(user_id=user_id, problem_id=problem.id, reason_type="algorithm", reason_detail="next 定义"))
        session.commit()
    analysis = _analyze(goal_id, "未关联题我想问一下。")
    assert analysis["category"] == "algorithm"
    assert analysis["knowledge_point_id"] is None
    assert point_id not in (analysis["knowledge_point_id"],)
    assert analysis["evidence_status"] == "suspected"


def test_confirmed_link_can_attribute_problem() -> None:
    goal_id = _goal()
    point_id = _point(goal_id, "字符串匹配")
    with Session(engine) as session:
        user_id = ensure_local_user(session).id
        topic = ProblemTopic(user_id=user_id, category="algorithm", name="字符串")
        session.add(topic)
        session.commit()
        session.refresh(topic)
        problem = Problem(user_id=user_id, title="已关联题", created_at=NOW, updated_at=NOW)
        session.add(problem)
        session.commit()
        session.refresh(problem)
        session.add(ProblemTopicLink(problem_id=problem.id, topic_id=topic.id, relevance="primary"))
        session.add(
            TopicKnowledgeLink(user_id=user_id, problem_topic_id=topic.id, knowledge_point_id=point_id)
        )
        session.add(ProblemWrongRecord(user_id=user_id, problem_id=problem.id, reason_type="algorithm", reason_detail="失配"))
        session.commit()
        before = session.exec(select(func.count()).select_from(TopicKnowledgeLink)).one()
    analysis = _analyze(goal_id, "已关联题我想问一下。")
    assert analysis["knowledge_point_id"] == point_id
    with Session(engine) as session:
        after = session.exec(select(func.count()).select_from(TopicKnowledgeLink)).one()
    assert after == before


def test_similar_name_does_not_link() -> None:
    goal_id = _goal()
    point_id = _point(goal_id, "链式法则")
    analysis = _analyze(goal_id, "链法则的导数应该相加。")
    assert analysis["category"] == "formula"
    assert analysis["knowledge_point_id"] is None
    assert point_id != analysis["knowledge_point_id"]
    assert analysis["prerequisite_candidates"] == []


def test_prerequisite_is_only_a_candidate() -> None:
    goal_id = _goal()
    chain_id = _point(goal_id, "链式法则")
    backprop_id = _point(goal_id, "反向传播")
    _point(goal_id, "计算图")
    with Session(engine) as session:
        before = session.exec(select(func.count()).select_from(TopicKnowledgeLink)).one()
    named = _analyze(goal_id, "我在学反向传播，但不理解链式法则，我觉得导数应该相加。")
    unnamed = _analyze(goal_id, r"反向传播里我认为 $\frac{\partial L}{\partial x}=\frac{\partial L}{\partial y}+\frac{\partial y}{\partial x}$。")
    assert named["category"] == "formula"
    assert {item["knowledge_point_id"] for item in named["prerequisite_candidates"]} <= {chain_id, backprop_id}
    assert all(item["evidence_status"] == "suspected" for item in named["prerequisite_candidates"])
    assert named["prerequisite_candidates"]
    assert unnamed["knowledge_point_id"] == backprop_id
    assert unnamed["prerequisite_candidates"] == []
    with Session(engine) as session:
        after = session.exec(select(func.count()).select_from(TopicKnowledgeLink)).one()
    assert after == before


def test_duplicate_evidence_is_counted_once() -> None:
    goal_id = _goal()
    point_id = _point(goal_id, "链式法则")
    with Session(engine) as session:
        quiz = Quiz(goal_id=goal_id, title="公式检测", status="submitted", score=40)
        session.add(quiz)
        session.commit()
        session.refresh(quiz)
        question = QuizQuestion(
            quiz_id=quiz.id,
            knowledge_point_id=point_id,
            question_type="short",
            difficulty="easy",
            stem="写出链式法则",
            correct_answer="相乘",
            explanation="导数相乘",
        )
        session.add(question)
        session.commit()
        session.refresh(question)
        session.add(QuizAnswer(question_id=question.id, user_answer="相加", is_correct=False, error_reason="把导数写成了相加", score=0))
        session.commit()
    first = _analyze(goal_id, "链式法则的导数应该相加。")
    second = _analyze(goal_id, "链式法则的导数应该相加。")
    assert first["direct_event_count"] == second["direct_event_count"] == 2
    assert first["evidence_keys"] == second["evidence_keys"]
    assert len([key for key in first["evidence_keys"] if key.startswith("quiz_answer:")]) == 1
    duplicated = dedupe_evidence(
        [
            {"source_key": "quiz_answer:1", "counts": True},
            {"source_key": "quiz_answer:1", "counts": True},
        ]
    )
    assert len(duplicated) == 1


def test_other_user_evidence_is_hidden() -> None:
    goal_id = _goal()
    _point(goal_id, "梯度")
    with Session(engine) as session:
        other = User(username=f"other-evidence-{uuid.uuid4().hex}")
        session.add(other)
        session.commit()
        session.refresh(other)
        problem = Problem(user_id=other.id, title="别人的秘密题", created_at=NOW, updated_at=NOW)
        session.add(problem)
        session.commit()
        session.refresh(problem)
        submission = ProblemSubmission(
            user_id=other.id,
            problem_id=problem.id,
            source_code="SECRET-OTHER",
            status="judged",
            submitted_at=NOW,
        )
        session.add(submission)
        session.commit()
        session.refresh(submission)
        session.add(
            ProblemJudgeResult(
                user_id=other.id,
                problem_id=problem.id,
                submission_id=submission.id,
                status="compile_error",
                compile_output="SECRET-OTHER",
            )
        )
        session.commit()
    analysis = _analyze(goal_id, "别人的秘密题编译失败了。")
    blob = json.dumps(analysis, ensure_ascii=False, default=str)
    assert "SECRET-OTHER" not in blob
    assert analysis["category"] == "implementation"
    assert analysis["evidence_status"] == "suspected"
    assert analysis["model_context"]["latest_code"] is None or "SECRET-OTHER" not in analysis["model_context"]["latest_code"]


def test_reserved_dedup_key_and_status_do_not_use_null_columns() -> None:
    key = memory_dedup_key("formula", None, None)
    assert key == "formula|kp:0|problem:0"
    assert "None" not in key
    assert memory_dedup_key("formula", 3, None) != memory_dedup_key("formula", 4, None)
    assert next_memory_status("active", "none") == "active"
    assert next_memory_status("resolved", "none") == "resolved"
    assert next_memory_status("active", "success", independent_successes=1) == "improving"
    assert next_memory_status("improving", "success", independent_successes=2) == "resolved"
    assert next_memory_status("resolved", "error") == "active"


def test_model_failure_does_not_save(monkeypatch) -> None:
    def fail(_messages, **_kwargs):
        raise AIError("DeepSeek 请求超时，请稍后重试", status_code=504)

    monkeypatch.setattr("app.services.tutor_service.complete_json", fail)
    session_id = client.post("/api/tutor/sessions", json={}).json()["id"]
    assert client.post(f"/api/tutor/sessions/{session_id}/messages", json={"content": "梯度下降就是直接得到最优参数。"}).status_code == 504
    assert client.get(f"/api/tutor/sessions/{session_id}").json()["messages"] == []


def test_multiturn_dialogue_keeps_history(monkeypatch) -> None:
    replies = iter(["先看这个方向。", "减号表示沿下降方向更新。"])

    def fake(_messages, **_kwargs):
        return json.dumps({"reply": next(replies)}, ensure_ascii=False)

    monkeypatch.setattr("app.services.tutor_service.complete_json", fake)
    goal_id = _goal("多轮")
    _point(goal_id, "梯度")
    session_id = client.post("/api/tutor/sessions", json={"goal_id": goal_id}).json()["id"]
    first = client.post(f"/api/tutor/sessions/{session_id}/messages", json={"content": "梯度到底是什么？"})
    second = client.post(f"/api/tutor/sessions/{session_id}/messages", json={"content": "那减号呢？"})
    assert first.status_code == second.status_code == 200
    assert "diagnosis" not in first.json()
    detail = client.get(f"/api/tutor/sessions/{session_id}").json()
    assert [item["role"] for item in detail["messages"]] == ["user", "assistant", "user", "assistant"]


def test_ten_dialogues_and_learning_records_stay_unchanged(monkeypatch) -> None:
    captured: list[str] = []

    def fake(messages, **_kwargs):
        captured.append(messages[-1]["content"])
        return json.dumps({"reply": "我们只看这一处。你能用自己的话说一次吗？"}, ensure_ascii=False)

    monkeypatch.setattr("app.services.tutor_service.complete_json", fake)
    goal_id = _goal("十组对话")
    point_id = _point(goal_id, "链式法则", mastery=70, status="learning")
    with Session(engine) as session:
        user_id = ensure_local_user(session).id
        session.add(KnowledgeMasteryEvent(knowledge_point_id=point_id, previous_level=None, new_level=70, quiz_score=70, reason="检测"))
        session.commit()
    problem_id = _problem(user_id, "调试样例题")
    submission_id = _submission(user_id, problem_id, "DEBUG-LATEST")
    _judge(user_id, problem_id, submission_id, "compile_error", "error: missing ';'")
    with Session(engine) as session:
        before = {
            "mastery": session.exec(select(func.count()).select_from(KnowledgeMasteryEvent)).one(),
            "review_records": session.exec(select(func.count()).select_from(ReviewRecord)).one(),
            "review_schedules": session.exec(select(func.count()).select_from(ReviewSchedule)).one(),
            "judges": session.exec(select(func.count()).select_from(ProblemJudgeResult)).one(),
            "statuses": session.exec(select(func.count()).select_from(ProblemLearningStatus)).one(),
            "links": session.exec(select(func.count()).select_from(TopicKnowledgeLink)).one(),
            "messages": session.exec(select(func.count()).select_from(TutorMessage)).one(),
        }
    prompts = [
        "梯度下降就是不断寻找损失函数的最小值，然后直接得到最优参数。",
        r"我认为链式法则是 $\frac{\partial L}{\partial x}=\frac{\partial L}{\partial y}+\frac{\partial y}{\partial x}$。",
        "反向传播不需要从输出层向前计算，每一层可以同时求。",
        "KMP 的 next[0] = -1，这个定义和前缀函数的最长真前缀是一回事。",
        "调试样例题编译失败了。",
        "循环边界写错了。\n```cpp\nfor (int i = 0; i <= n; i++) a[i] = 1;\n```",
        "普通样例能过，但空数组会错。",
        "链式法则是什么？",
        "我有点乱，说不清楚。",
        "CLIP 里的对比学习是什么意思？",
    ]
    session_id = client.post("/api/tutor/sessions", json={"goal_id": goal_id}).json()["id"]
    diagnoses = []
    for prompt in prompts:
        response = client.post(f"/api/tutor/sessions/{session_id}/messages", json={"content": prompt})
        assert response.status_code == 200
        diagnoses.append(response.json().get("diagnosis"))
    assert [item["category"] if item else None for item in diagnoses] == [
        "concept",
        "formula",
        "reasoning",
        "algorithm",
        "implementation",
        "implementation",
        "boundary",
        None,
        None,
        None,
    ]
    assert diagnoses[0]["evidence_status"] == "suspected"
    assert diagnoses[1]["evidence_status"] == "confirmed"
    assert diagnoses[4]["teaching_strategy"] == "code_debugging"
    assert any("DEBUG-LATEST" in text for text in captured)
    assert all("SECRET-OTHER" not in text for text in captured)
    detail = client.get(f"/api/tutor/sessions/{session_id}").json()
    assert len(detail["messages"]) == 20
    with Session(engine) as session:
        point = session.get(KnowledgePoint, point_id)
        assert point is not None
        assert point.mastery_level == 70
        assert session.exec(select(func.count()).select_from(KnowledgeMasteryEvent)).one() == before["mastery"]
        assert session.exec(select(func.count()).select_from(ReviewRecord)).one() == before["review_records"]
        assert session.exec(select(func.count()).select_from(ReviewSchedule)).one() == before["review_schedules"]
        assert session.exec(select(func.count()).select_from(ProblemJudgeResult)).one() == before["judges"]
        assert session.exec(select(func.count()).select_from(ProblemLearningStatus)).one() == before["statuses"]
        assert session.exec(select(func.count()).select_from(TopicKnowledgeLink)).one() == before["links"]
        assert session.exec(select(func.count()).select_from(TutorMessage)).one() == before["messages"] + 20
