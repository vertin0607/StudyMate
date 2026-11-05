"""规则诊断只读取已有记录。连续低分、判题状态和未确认关联都按记录本身计算。"""

import inspect
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models.goal import LearningGoal
from app.models.judge import ProblemJudgeCaseResult, ProblemJudgeResult
from app.models.knowledge import KnowledgePoint
from app.models.practice import ProblemLearningStatus, ProblemPracticeRecord, ProblemWrongRecord
from app.models.problem import Problem, ProblemTestCase, ProblemTopic, ProblemTopicLink
from app.models.quiz import KnowledgeMasteryEvent
from app.models.review import ReviewSchedule
from app.models.submission import ProblemSubmission
from app.models.topic_link import TopicKnowledgeLink
from app.models.tutor import TutorMessage, TutorSession
from app.models.user import User
from app.services import diagnosis_rules
from app.services.actor import acting_as

client = TestClient(app)


def _counts() -> dict[str, int]:
    with Session(engine) as session:
        return {
            "goals": len(session.exec(select(LearningGoal)).all()),
            "points": len(session.exec(select(KnowledgePoint)).all()),
            "events": len(session.exec(select(KnowledgeMasteryEvent)).all()),
            "schedules": len(session.exec(select(ReviewSchedule)).all()),
            "topics": len(session.exec(select(ProblemTopic)).all()),
            "problems": len(session.exec(select(Problem)).all()),
            "topic_links": len(session.exec(select(TopicKnowledgeLink)).all()),
            "problem_topics": len(session.exec(select(ProblemTopicLink)).all()),
            "submissions": len(session.exec(select(ProblemSubmission)).all()),
            "judges": len(session.exec(select(ProblemJudgeResult)).all()),
            "cases": len(session.exec(select(ProblemJudgeCaseResult)).all()),
            "wrongs": len(session.exec(select(ProblemWrongRecord)).all()),
            "statuses": len(session.exec(select(ProblemLearningStatus)).all()),
            "practice": len(session.exec(select(ProblemPracticeRecord)).all()),
            "messages": len(session.exec(select(TutorMessage)).all()),
        }


def _local() -> tuple[User, datetime]:
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        return session.exec(select(User).where(User.username == "local")).one(), now


def _add_goal(session: Session, user_id: int, title: str, now: datetime) -> LearningGoal:
    goal = LearningGoal(user_id=user_id, title=title, description="诊断", target_date=date.today(), daily_minutes=25, created_at=now, updated_at=now)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


def _add_point(session: Session, goal_id: int, name: str, now: datetime, mastery: int = 0, status: str = "not_started") -> KnowledgePoint:
    point = KnowledgePoint(goal_id=goal_id, name=name, mastery_level=mastery, status=status, created_at=now, updated_at=now)
    session.add(point)
    session.commit()
    session.refresh(point)
    return point


def _score(session: Session, point_id: int, score: int, mastery: int, when: datetime, previous: int | None = None) -> None:
    session.add(KnowledgeMasteryEvent(knowledge_point_id=point_id, previous_level=previous, new_level=mastery, quiz_score=score, reason="检测", created_at=when))


def _topic(session: Session, user_id: int, name: str, now: datetime) -> ProblemTopic:
    topic = ProblemTopic(user_id=user_id, category="自定义", name=name, created_at=now)
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


def _problem(session: Session, user_id: int, title: str, now: datetime) -> Problem:
    problem = Problem(user_id=user_id, title=title, created_at=now, updated_at=now)
    session.add(problem)
    session.commit()
    session.refresh(problem)
    return problem


def _classify(session: Session, problem_id: int, topic_id: int) -> None:
    session.add(ProblemTopicLink(problem_id=problem_id, topic_id=topic_id, relevance="primary", reason="测试"))


def _confirm(session: Session, user_id: int, topic_id: int, point_id: int, now: datetime) -> None:
    session.add(TopicKnowledgeLink(user_id=user_id, problem_topic_id=topic_id, knowledge_point_id=point_id, created_at=now))


def _submit(session: Session, user_id: int, problem_id: int, status: str, now: datetime) -> ProblemSubmission:
    row = ProblemSubmission(user_id=user_id, problem_id=problem_id, source_code="int main(){return 0;}", status=status, submitted_at=now)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _judge(session: Session, user_id: int, submission: ProblemSubmission, status: str, now: datetime) -> ProblemJudgeResult:
    row = ProblemJudgeResult(user_id=user_id, submission_id=submission.id, problem_id=submission.problem_id, status=status, total_cases=1, passed_cases=1 if status == "accepted" else 0, failed_cases=0 if status == "accepted" else 1, judged_at=now, created_at=now)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _diagnosis(goal_id: int | None = None) -> dict:
    response = client.get("/api/learning/diagnosis" if goal_id is None else f"/api/learning/diagnosis?goal_id={goal_id}")
    assert response.status_code == 200
    return response.json()


def _category(payload: dict, category: str, knowledge_name: str | None = None, topic_name: str | None = None) -> dict:
    rows = payload["by_category"][category]
    if knowledge_name is not None:
        rows = [row for row in rows if row["knowledge_point_name"] == knowledge_name]
    if topic_name is not None:
        rows = [row for row in rows if any(topic["name"] == topic_name for topic in row["problem_topics"])]
    assert len(rows) == 1
    return rows[0]


def test_low_scores_use_time_order() -> None:
    with Session(engine) as session:
        local = session.exec(select(User).where(User.username == "local")).one()
        now = datetime.now(timezone.utc)
        goal = _add_goal(session, local.id, "低分目标", now)
        confirmed = _add_point(session, goal.id, "连续低分", now, 40, "needs_review")
        broken = _add_point(session, goal.id, "中间高分", now, 50, "needs_review")
        once = _add_point(session, goal.id, "单次低分", now, 45, "learning")
        _score(session, confirmed.id, 42, 40, now - timedelta(days=2), None)
        _score(session, confirmed.id, 51, 40, now - timedelta(days=1), 40)
        _score(session, broken.id, 41, 40, now - timedelta(days=2), None)
        _score(session, broken.id, 90, 70, now - timedelta(days=1), 40)
        _score(session, broken.id, 58, 50, now, 70)
        _score(session, once.id, 59, 45, now, None)
        session.commit()
        session.get(KnowledgePoint, confirmed.id).mastery_level = 40
        session.get(KnowledgePoint, broken.id).mastery_level = 50
        session.get(KnowledgePoint, once.id).mastery_level = 45
        session.commit()

    payload = _diagnosis()
    streak = _category(payload, "knowledge_understanding", "连续低分")
    assert streak["status"] == "confirmed"
    assert streak["evidence_count"] == 2
    assert [item["score"] for item in streak["evidence"]] == [42, 51]
    assert all(item["in_current_streak"] for item in streak["evidence"])
    reset = _category(payload, "knowledge_understanding", "中间高分")
    assert reset["status"] == "suspected"
    assert reset["evidence_count"] == 1
    assert [item["in_current_streak"] for item in reset["evidence"]] == [False, False, True]
    assert reset["evidence"][1]["score"] == 90
    single = _category(payload, "knowledge_understanding", "单次低分")
    assert single["status"] == "suspected"
    assert single["evidence_count"] == 1


def test_algorithm_implementation_and_boundary_rules() -> None:
    with Session(engine) as session:
        local = session.exec(select(User).where(User.username == "local")).one()
        now = datetime.now(timezone.utc)
        goal = _add_goal(session, local.id, "做题目标", now)
        point = _add_point(session, goal.id, "字符串", now)
        compile_point = _add_point(session, goal.id, "编译知识点", now)
        compile_once_point = _add_point(session, goal.id, "单次编译", now)
        plain_point = _add_point(session, goal.id, "普通答案", now)
        boundary_point = _add_point(session, goal.id, "边界知识点", now)
        algorithm_topic = _topic(session, local.id, "算法题库", now)
        compile_topic = _topic(session, local.id, "实现题库", now)
        once_topic = _topic(session, local.id, "单次实现", now)
        plain_topic = _topic(session, local.id, "普通题库", now)
        boundary_topic = _topic(session, local.id, "边界题库", now)
        for topic, knowledge in (
            (algorithm_topic, point),
            (compile_topic, compile_point),
            (once_topic, compile_once_point),
            (plain_topic, plain_point),
            (boundary_topic, boundary_point),
        ):
            _confirm(session, local.id, topic.id, knowledge.id, now)
        first = _problem(session, local.id, "算法甲", now)
        second = _problem(session, local.id, "算法乙", now)
        compile_problem = _problem(session, local.id, "编译两次", now)
        once_problem = _problem(session, local.id, "编译一次", now)
        plain = _problem(session, local.id, "普通错误", now)
        edge_a = _problem(session, local.id, "边界甲", now)
        edge_b = _problem(session, local.id, "边界乙", now)
        for problem, topic in (
            (first, algorithm_topic),
            (second, algorithm_topic),
            (plain, plain_topic),
            (compile_problem, compile_topic),
            (once_problem, once_topic),
            (edge_a, boundary_topic),
            (edge_b, boundary_topic),
        ):
            _classify(session, problem.id, topic.id)
        session.add(ProblemWrongRecord(user_id=local.id, problem_id=first.id, reason_type="algorithm", reason_detail="思路", created_at=now, updated_at=now))
        session.add(ProblemWrongRecord(user_id=local.id, problem_id=second.id, reason_type="algorithm", reason_detail="思路", created_at=now, updated_at=now))
        session.add(ProblemWrongRecord(user_id=local.id, problem_id=edge_a.id, reason_type="boundary", reason_detail="空数组", created_at=now, updated_at=now))
        session.add(ProblemWrongRecord(user_id=local.id, problem_id=edge_b.id, reason_type="boundary", reason_detail="负数", created_at=now, updated_at=now))
        _judge(session, local.id, _submit(session, local.id, compile_problem.id, "compile_error", now), "compile_error", now)
        _judge(session, local.id, _submit(session, local.id, compile_problem.id, "compile_error", now + timedelta(minutes=1)), "compile_error", now)
        _judge(session, local.id, _submit(session, local.id, once_problem.id, "compile_error", now), "compile_error", now)
        _judge(session, local.id, _submit(session, local.id, plain.id, "wrong_answer", now), "wrong_answer", now)
        _judge(session, local.id, _submit(session, local.id, plain.id, "wrong_answer", now + timedelta(minutes=1)), "wrong_answer", now)
        session.commit()

    payload = _diagnosis()
    algorithm = _category(payload, "algorithm", "字符串", "算法题库")
    assert algorithm["status"] == "confirmed"
    assert algorithm["evidence_count"] == 2
    assert {item["problem_title"] for item in algorithm["evidence"] if item["counts"]} == {"算法甲", "算法乙"}
    implementation = _category(payload, "implementation", "编译知识点")
    assert implementation["status"] == "confirmed"
    assert implementation["evidence_count"] == 2
    once = _category(payload, "implementation", "单次编译")
    assert once["status"] == "suspected"
    assert once["evidence_count"] == 1
    boundary = _category(payload, "boundary", "边界知识点")
    assert boundary["status"] == "confirmed"
    assert boundary["evidence_count"] == 2
    plain_algorithm = _category(payload, "algorithm", "普通答案")
    plain_boundary = _category(payload, "boundary", "普通答案")
    assert plain_algorithm["status"] == "suspected"
    assert "辅助证据" in plain_algorithm["reason"]
    assert plain_boundary["status"] == "insufficient_data"
    assert plain_boundary["evidence_count"] == 0
    assert any(item["type"] == "judge_result" and item["status"] == "wrong_answer" and item["counts"] is False for item in plain_boundary["evidence"])


def test_special_statuses_are_not_user_mistakes() -> None:
    with Session(engine) as session:
        local = session.exec(select(User).where(User.username == "local")).one()
        now = datetime.now(timezone.utc)
        goal = _add_goal(session, local.id, "状态目标", now)
        point = _add_point(session, goal.id, "状态知识点", now)
        topic = _topic(session, local.id, "状态题库", now)
        _confirm(session, local.id, topic.id, point.id, now)
        broken = _problem(session, local.id, "环境异常", now)
        noted = _problem(session, local.id, "自评完成", now)
        waiting = _problem(session, local.id, "尚未判题", now)
        for problem in (broken, noted, waiting):
            _classify(session, problem.id, topic.id)
        for _ in range(2):
            _judge(session, local.id, _submit(session, local.id, broken.id, "system_error", now), "system_error", now)
        session.add(ProblemLearningStatus(user_id=local.id, problem_id=noted.id, status="self_completed", created_at=now, updated_at=now))
        session.add(ProblemPracticeRecord(user_id=local.id, problem_id=noted.id, completion_type="independent", created_at=now))
        _submit(session, local.id, waiting.id, "unjudged", now)
        session.commit()

    payload = _diagnosis()
    for category in ("algorithm", "implementation", "boundary"):
        row = _category(payload, category, "状态知识点")
        assert row["status"] == "insufficient_data"
        assert row["evidence_count"] == 0
        assert all(item["counts"] is False for item in row["evidence"])
    algorithm = _category(payload, "algorithm", "状态知识点")
    assert any(item.get("status") == "system_error" and "不是用户答案错误" in item["note"] for item in algorithm["evidence"])
    assert any(item.get("status") == "self_completed" and "不是系统判题通过" in item["note"] for item in algorithm["evidence"])
    assert any(item.get("status") == "unjudged" and "不形成判题结论" in item["note"] for item in algorithm["evidence"])
    assert not any(item["counts"] and item.get("status") == "accepted" for item in algorithm["evidence"])


def test_sample_pass_counts_once_per_submission() -> None:
    with Session(engine) as session:
        local = session.exec(select(User).where(User.username == "local")).one()
        now = datetime.now(timezone.utc)
        goal = _add_goal(session, local.id, "样例目标", now)
        point = _add_point(session, goal.id, "样例知识点", now)
        topic = _topic(session, local.id, "样例题库", now)
        _confirm(session, local.id, topic.id, point.id, now)
        problem = _problem(session, local.id, "样例通过题", now)
        _classify(session, problem.id, topic.id)
        sample = ProblemTestCase(problem_id=problem.id, name="样例", case_type="sample", created_at=now, updated_at=now)
        custom_a = ProblemTestCase(problem_id=problem.id, name="隐藏一", case_type="custom", created_at=now, updated_at=now)
        custom_b = ProblemTestCase(problem_id=problem.id, name="隐藏二", case_type="custom", created_at=now, updated_at=now)
        session.add(sample)
        session.add(custom_a)
        session.add(custom_b)
        session.commit()
        session.refresh(sample)
        session.refresh(custom_a)
        session.refresh(custom_b)
        submission = _submit(session, local.id, problem.id, "wrong_answer", now)
        judge = _judge(session, local.id, submission, "wrong_answer", now)
        session.add(ProblemJudgeCaseResult(judge_result_id=judge.id, test_case_id=sample.id, status="accepted"))
        session.add(ProblemJudgeCaseResult(judge_result_id=judge.id, test_case_id=custom_a.id, status="wrong_answer"))
        session.add(ProblemJudgeCaseResult(judge_result_id=judge.id, test_case_id=custom_b.id, status="wrong_answer"))
        session.commit()

    row = _category(_diagnosis(), "boundary", "样例知识点")
    assert row["status"] == "suspected"
    assert row["evidence_count"] == 1
    matched = [item for item in row["evidence"] if item["type"] == "sample_passed_other_failed"]
    assert len(matched) == 1
    assert matched[0]["failed_case_count"] == 2


def test_unlinked_topics_stay_separate_until_confirmed() -> None:
    with Session(engine) as session:
        local = session.exec(select(User).where(User.username == "local")).one()
        now = datetime.now(timezone.utc)
        goal = _add_goal(session, local.id, "关联目标", now)
        point = _add_point(session, goal.id, "学习点", now)
        loose = _topic(session, local.id, "未确认题库", now)
        linked = _topic(session, local.id, "已确认题库", now)
        _confirm(session, local.id, linked.id, point.id, now)
        outside = _problem(session, local.id, "未关联错题", now)
        inside = _problem(session, local.id, "已关联错题", now)
        _classify(session, outside.id, loose.id)
        _classify(session, inside.id, linked.id)
        session.add(ProblemWrongRecord(user_id=local.id, problem_id=outside.id, reason_type="algorithm", reason_detail="未关联", created_at=now, updated_at=now))
        session.add(ProblemWrongRecord(user_id=local.id, problem_id=inside.id, reason_type="algorithm", reason_detail="已关联", created_at=now, updated_at=now))
        chat = TutorSession(user_id=local.id, goal_id=goal.id, title="只是提问", created_at=now, updated_at=now)
        session.add(chat)
        session.commit()
        session.refresh(chat)
        session.add(TutorMessage(session_id=chat.id, role="user", content="这是什么", knowledge_point_ids_json=f"[{point.id}]", created_at=now))
        session.commit()

    payload = _diagnosis()
    knowledge = next(row for row in payload["knowledge_points"] if row["name"] == "学习点")
    assert {item["category"] for item in knowledge["diagnoses"]} >= {"knowledge_understanding", "algorithm"}
    algorithm = _category(payload, "algorithm", "学习点")
    assert algorithm["status"] == "suspected"
    assert {item["problem_title"] for item in algorithm["evidence"] if item["counts"]} == {"已关联错题"}
    independent = next(row for row in payload["problem_topics"] if row["name"] == "未确认题库")
    assert independent["diagnoses"][0]["knowledge_point_id"] is None
    assert any(item["problem_title"] == "未关联错题" and item["counts"] for item in independent["diagnoses"][0]["evidence"])
    assert "已确认题库" not in {row["name"] for row in payload["problem_topics"]}
    understanding = _category(payload, "knowledge_understanding", "学习点")
    assert understanding["status"] == "insufficient_data"
    assert "提问" not in understanding["reason"]


def test_review_due_and_overdue_are_distinct() -> None:
    today = datetime.now().astimezone().date()
    with Session(engine) as session:
        local = session.exec(select(User).where(User.username == "local")).one()
        now = datetime.now(timezone.utc)
        goal = _add_goal(session, local.id, "复习目标", now)
        due = _add_point(session, goal.id, "今天到期", now, 70, "reviewing")
        overdue = _add_point(session, goal.id, "已经逾期", now, 40, "needs_review")
        forgotten = _add_point(session, goal.id, "掌握度下降", now, 40, "needs_review")
        unchanged = _add_point(session, goal.id, "没有历史", now, 40, "learning")
        session.add(ReviewSchedule(goal_id=goal.id, knowledge_point_id=due.id, next_review_date=today, last_score=80))
        session.add(ReviewSchedule(goal_id=goal.id, knowledge_point_id=overdue.id, next_review_date=today - timedelta(days=2), last_score=40))
        _score(session, forgotten.id, 90, 80, now - timedelta(days=2), None)
        _score(session, forgotten.id, 50, 40, now, 80)
        _score(session, unchanged.id, 40, 40, now, None)
        session.commit()

    payload = _diagnosis()
    due_row = _category(payload, "forgetting", "今天到期")
    overdue_row = _category(payload, "forgetting", "已经逾期")
    drop_row = _category(payload, "forgetting", "掌握度下降")
    plain_row = _category(payload, "forgetting", "没有历史")
    assert due_row["status"] == "suspected"
    assert due_row["evidence"][1]["due"] is True
    assert due_row["evidence"][1]["overdue"] is False
    assert overdue_row["status"] == "confirmed"
    assert overdue_row["evidence"][1]["overdue"] is True
    assert overdue_row["evidence"][1]["due"] is False
    assert drop_row["status"] == "confirmed"
    assert drop_row["evidence"][0]["mastery_drop"] is True
    assert drop_row["evidence"][0]["historical_high"] == 80
    assert drop_row["evidence"][0]["mastery_level"] == 40
    assert plain_row["status"] == "insufficient_data"
    assert plain_row["evidence"][0]["mastery_drop"] is False
    assert plain_row["evidence"][0]["has_historical_evidence"] is False


def test_goal_filter_and_user_isolation() -> None:
    with Session(engine) as session:
        local = session.exec(select(User).where(User.username == "local")).one()
        other = User(username="other-rules")
        session.add(other)
        session.commit()
        session.refresh(other)
        now = datetime.now(timezone.utc)
        own = _add_goal(session, local.id, "自己的目标", now)
        other_goal = _add_goal(session, local.id, "另一个目标", now)
        hidden = _add_goal(session, other.id, "别人的目标", now)
        own_point = _add_point(session, own.id, "自己的知识点", now, 30, "needs_review")
        other_point = _add_point(session, other_goal.id, "另一个知识点", now, 30, "needs_review")
        hidden_point = _add_point(session, hidden.id, "别人的知识点", now, 20, "needs_review")
        _score(session, own_point.id, 30, 30, now - timedelta(days=1))
        _score(session, own_point.id, 40, 30, now, 30)
        _score(session, hidden_point.id, 10, 20, now - timedelta(days=1))
        _score(session, hidden_point.id, 15, 20, now, 20)
        hidden_topic = _topic(session, other.id, "别人的题库", now)
        hidden_problem = _problem(session, other.id, "别人的错题", now)
        _classify(session, hidden_problem.id, hidden_topic.id)
        session.add(ProblemWrongRecord(user_id=other.id, problem_id=hidden_problem.id, reason_type="algorithm", reason_detail="别人", created_at=now, updated_at=now))
        linked_topic = _topic(session, local.id, "只属于另一个目标", now)
        linked_problem = _problem(session, local.id, "另一个目标的题", now)
        _classify(session, linked_problem.id, linked_topic.id)
        _confirm(session, local.id, linked_topic.id, other_point.id, now)
        session.add(ProblemWrongRecord(user_id=local.id, problem_id=linked_problem.id, reason_type="algorithm", reason_detail="另一个", created_at=now, updated_at=now))
        session.commit()
        own_id = own.id
        hidden_id = hidden.id

    filtered = _diagnosis(own_id)
    assert {row["name"] for row in filtered["knowledge_points"]} == {"自己的知识点"}
    assert "另一个知识点" not in filtered["by_category"]["knowledge_understanding"][0]["reason"]
    assert all(row["knowledge_point_name"] != "另一个知识点" for rows in filtered["by_category"].values() for row in rows)
    assert "别人的知识点" not in str(filtered)
    assert "别人的错题" not in str(filtered)
    assert "只属于另一个目标" not in str(filtered)
    assert client.get(f"/api/learning/diagnosis?goal_id={hidden_id}").status_code == 404


def test_empty_diagnosis_has_full_shape_and_reads_do_not_write() -> None:
    source = inspect.getsource(diagnosis_rules)
    assert "complete_json" not in source
    assert "session.add" not in source
    assert ".commit(" not in source
    before = _counts()
    first = _diagnosis()
    second = _diagnosis()
    assert first == second
    assert _counts() == before
    assert first == {
        "goal_id": None,
        "summary": {"total": 0, "confirmed": 0, "suspected": 0, "insufficient_data": 0},
        "by_category": {name: [] for name in ("knowledge_understanding", "algorithm", "implementation", "boundary", "forgetting")},
        "knowledge_points": [],
        "problem_topics": [],
        "links": [],
    }
    with Session(engine) as session:
        local = session.exec(select(User).where(User.username == "local")).one()
        with acting_as(local.id):
            diagnosis_rules.diagnose(session, None)
        assert list(session.new) == []
        assert list(session.dirty) == []
