"""成长汇总只读。连续读取不得写入，也不使用会补建复习计划的统计接口。"""

import inspect
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import settings
from app.database import engine
from app.main import app
from app.models.goal import LearningGoal
from app.models.judge import ProblemJudgeResult
from app.models.knowledge import KnowledgePoint
from app.models.plan import StudyPlan, StudyTask
from app.models.practice import ProblemLearningStatus, ProblemPracticeRecord, ProblemWrongRecord
from app.models.problem import Problem
from app.models.quiz import KnowledgeMasteryEvent, Quiz
from app.models.recommendation import TrainingRecommendation
from app.models.review import ReviewRecord, ReviewSchedule
from app.models.submission import ProblemSubmission
from app.models.user import User
from app.services import growth_service
from app.services.actor import acting_as

client = TestClient(app)


def _today():
    return datetime.now().astimezone().date()


def _at(day_offset: int, hour: int = 12) -> datetime:
    local = datetime.now().astimezone().replace(hour=hour, minute=0, second=0, microsecond=0)
    return (local + timedelta(days=day_offset)).astimezone(timezone.utc)


def _local_user() -> User:
    with Session(engine) as session:
        return session.exec(select(User).where(User.username == "local")).one()


def _goal(session: Session, user_id: int, title: str) -> LearningGoal:
    now = datetime.now(timezone.utc)
    goal = LearningGoal(user_id=user_id, title=title, description="成长", target_date=_today(), daily_minutes=25, created_at=now, updated_at=now)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


def _point(session: Session, goal_id: int, name: str) -> KnowledgePoint:
    now = datetime.now(timezone.utc)
    point = KnowledgePoint(goal_id=goal_id, name=name, created_at=now, updated_at=now)
    session.add(point)
    session.commit()
    session.refresh(point)
    return point


def _plan(session: Session, goal_id: int) -> StudyPlan:
    now = datetime.now(timezone.utc)
    plan = StudyPlan(
        goal_id=goal_id,
        plan_date=_today(),
        title="计划",
        description="一天只学一个知识点",
        total_minutes=25,
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def _task(session: Session, plan_id: int, when: datetime | None, estimated: int = 25) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        StudyTask(
            plan_id=plan_id,
            title="任务",
            description="完成一个小知识点",
            task_type="learn",
            estimated_minutes=estimated,
            status="completed",
            completed_at=when,
            created_at=now,
            updated_at=now,
        )
    )


def _quiz(session: Session, goal_id: int, score: int, when: datetime, title: str = "检测") -> Quiz:
    quiz = Quiz(goal_id=goal_id, title=title, status="completed", score=score, submitted_at=when, created_at=when)
    session.add(quiz)
    session.commit()
    session.refresh(quiz)
    return quiz


def _event(session: Session, point_id: int, score: int, level: int, when: datetime) -> None:
    session.add(KnowledgeMasteryEvent(knowledge_point_id=point_id, previous_level=None, new_level=level, quiz_score=score, reason="检测", created_at=when))


def _problem(session: Session, user_id: int, title: str) -> Problem:
    now = datetime.now(timezone.utc)
    problem = Problem(user_id=user_id, title=title, created_at=now, updated_at=now)
    session.add(problem)
    session.commit()
    session.refresh(problem)
    return problem


def _submission(session: Session, user_id: int, problem_id: int, status: str, when: datetime) -> ProblemSubmission:
    row = ProblemSubmission(user_id=user_id, problem_id=problem_id, source_code="int main(){return 0;}", status=status, submitted_at=when)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _judge(session: Session, user_id: int, submission: ProblemSubmission, status: str, when: datetime) -> None:
    session.add(
        ProblemJudgeResult(
            user_id=user_id,
            submission_id=submission.id,
            problem_id=submission.problem_id,
            status=status,
            judged_at=when,
            created_at=when,
        )
    )


def _dump() -> str:
    models = [
        User,
        LearningGoal,
        KnowledgePoint,
        KnowledgeMasteryEvent,
        Quiz,
        ReviewSchedule,
        ReviewRecord,
        StudyPlan,
        StudyTask,
        Problem,
        ProblemSubmission,
        ProblemJudgeResult,
        ProblemPracticeRecord,
        ProblemLearningStatus,
        ProblemWrongRecord,
        TrainingRecommendation,
    ]
    with Session(engine) as session:
        payload = {}
        for model in models:
            rows = session.exec(select(model).order_by(model.id)).all()
            payload[model.__name__] = [row.model_dump(mode="json") for row in rows]
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def test_service_does_not_use_writing_review_paths() -> None:
    source = inspect.getsource(growth_service)
    for name in ("risk_report", "review_statistics", "complete_json", "ensure_local_user", "session.add", "session.commit"):
        assert name not in source


def test_empty_growth_and_day_choices() -> None:
    empty = client.get("/api/learning/growth")
    assert empty.status_code == 200
    body = empty.json()
    assert body["days"] == 30
    assert len(body["series"]) == 30
    assert body["summary"]["study_day_count"] == 0
    assert body["summary"]["current_streak_days"] == 0
    assert body["summary"]["pass_rate"] is None
    assert body["summary"]["pass_rate_denominator"] == 0
    assert body["summary"]["actual_practice_seconds"] is None
    assert body["practice_scope"] == "current_user_all_problems"
    assert body["practice"]["practice_scope"] == "current_user_all_problems"
    assert body["weaknesses"]["improved"] == []
    assert all(day["has_activity"] is False and day["actual_practice_seconds"] is None for day in body["series"])

    assert client.get("/api/learning/growth", params={"days": 14}).status_code == 422
    assert len(client.get("/api/learning/growth", params={"days": 7}).json()["series"]) == 7
    assert len(client.get("/api/learning/growth", params={"days": 90}).json()["series"]) == 90
    assert client.get("/api/learning/growth", params={"goal_id": 99999}).status_code == 404


def test_local_dates_streak_and_estimated_minutes_are_not_duration() -> None:
    user = _local_user()
    today = _today()
    local_midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    before_midnight = local_midnight - timedelta(minutes=30)
    after_midnight = local_midnight + timedelta(minutes=30)
    with Session(engine) as session:
        goal = _goal(session, user.id, "日期")
        point = _point(session, goal.id, "日期知识点")
        plan = _plan(session, goal.id)
        for offset in (0, -1, -2, -4, -10):
            _task(session, plan.id, _at(offset), estimated=25)
        _task(session, plan.id, None, estimated=40)
        schedule = ReviewSchedule(goal_id=goal.id, knowledge_point_id=point.id, next_review_date=today, updated_at=datetime.now(timezone.utc))
        session.add(schedule)
        session.commit()
        session.refresh(schedule)
        session.add(
            ReviewRecord(
                schedule_id=schedule.id,
                knowledge_point_id=point.id,
                reviewed_at=_at(-3),
                result="postponed",
                next_interval=1,
                next_review_date=today,
                reason="推迟",
            )
        )
        problem = _problem(session, user.id, "跨天练习")
        session.add(
            ProblemPracticeRecord(
                user_id=user.id,
                problem_id=problem.id,
                started_at=before_midnight.astimezone(timezone.utc),
                completed_at=after_midnight.astimezone(timezone.utc),
                created_at=before_midnight,
            )
        )
        session.add(
            ProblemPracticeRecord(user_id=user.id, problem_id=problem.id, started_at=_at(-2), completed_at=None, created_at=_at(-2))
        )
        session.add(
            ProblemPracticeRecord(
                user_id=user.id,
                problem_id=problem.id,
                started_at=_at(-2),
                completed_at=_at(-2) - timedelta(minutes=5),
                created_at=_at(-2),
            )
        )
        session.commit()

    body = client.get("/api/learning/growth", params={"days": 7}).json()
    summary = body["summary"]
    assert summary["study_day_count"] == 5
    assert summary["current_streak_days"] == 3
    assert summary["studied_today"] is True
    assert summary["completed_task_count"] == 5
    assert summary["review_count"] == 0
    assert summary["actual_practice_seconds"] == 3600
    assert summary["practiced_problem_count"] == 1
    by_date = {item["date"]: item for item in body["series"]}
    assert by_date[(today - timedelta(days=3)).isoformat()]["has_activity"] is False
    assert (today - timedelta(days=10)).isoformat() not in by_date
    assert by_date[(today - timedelta(days=4)).isoformat()]["has_activity"] is True
    start_day = before_midnight.astimezone().date().isoformat()
    end_day = after_midnight.astimezone().date().isoformat()
    assert start_day != end_day
    assert by_date[start_day]["has_duration_record"] is True
    assert by_date[start_day]["actual_practice_seconds"] == 3600
    assert by_date[end_day]["actual_practice_seconds"] is None
    assert by_date[end_day]["has_activity"] is True
    assert all(item["actual_practice_seconds"] != 25 * 60 for item in body["series"])


def test_problem_counts_judge_classes_and_duration() -> None:
    user = _local_user()
    when = _at(0, 9)
    with Session(engine) as session:
        problem = _problem(session, user.id, "同一题多次提交")
        other = _problem(session, user.id, "其他错误")
        broken = _problem(session, user.id, "环境异常")
        pending = _problem(session, user.id, "尚未判题")
        manual = _problem(session, user.id, "自评完成")
        for status in ("accepted", "wrong_answer", "compile_error"):
            submission = _submission(session, user.id, problem.id, status, when)
            _judge(session, user.id, submission, status, when)
        for status in ("runtime_error", "time_limit_exceeded"):
            submission = _submission(session, user.id, other.id, status, when)
            _judge(session, user.id, submission, status, when)
        errored = _submission(session, user.id, broken.id, "system_error", when)
        _judge(session, user.id, errored, "system_error", when)
        _submission(session, user.id, pending.id, "unjudged", when)
        session.add(ProblemLearningStatus(user_id=user.id, problem_id=manual.id, status="self_completed", created_at=when, updated_at=when))
        session.add(ProblemLearningStatus(user_id=user.id, problem_id=problem.id, status="accepted", created_at=when, updated_at=when))
        session.add(ProblemPracticeRecord(user_id=user.id, problem_id=problem.id, started_at=when, completed_at=when + timedelta(seconds=90), created_at=when))
        session.add(ProblemPracticeRecord(user_id=user.id, problem_id=problem.id, started_at=when, completed_at=None, created_at=when))
        session.add(ProblemWrongRecord(user_id=user.id, problem_id=problem.id, reason_type="algorithm", created_at=when, updated_at=when))
        session.commit()

    practice = client.get("/api/learning/growth").json()["practice"]
    assert practice["submission_count"] == 7
    assert practice["submitted_problem_count"] == 4
    assert practice["practiced_problem_count"] == 1
    assert practice["local_accepted_submission_count"] == 1
    assert practice["local_accepted_problem_count"] == 1
    assert practice["judge_counts"] == {
        "accepted": 1,
        "wrong_answer": 1,
        "compile_error": 1,
        "time_limit_exceeded": 1,
        "runtime_error": 1,
        "system_error": 1,
        "unjudged": 1,
    }
    assert practice["pass_rate_numerator"] == 1
    assert practice["pass_rate_denominator"] == 5
    assert practice["pass_rate"] == 0.2
    assert practice["actual_practice_seconds"] == 90
    assert practice["actual_practice_record_count"] == 1
    assert practice["self_completed_problem_count"] == 1
    assert practice["wrong_record_count"] == 1


def test_improvement_requires_evidence_on_the_same_subject() -> None:
    user = _local_user()
    early = _at(-5, 9)
    later = _at(-1, 9)
    with Session(engine) as session:
        goal = _goal(session, user.id, "薄弱点")
        recovered = _point(session, goal.id, "已恢复")
        still = _point(session, goal.id, "仍然低分")
        other = _point(session, goal.id, "另一知识点")
        relapsed = _point(session, goal.id, "再次下降")
        reviewed = _point(session, goal.id, "复习后通过")
        _event(session, recovered.id, 40, 40, early)
        _event(session, recovered.id, 85, 80, later)
        _event(session, still.id, 30, 30, early)
        _event(session, other.id, 90, 90, later)
        _event(session, relapsed.id, 40, 40, early)
        _event(session, relapsed.id, 88, 88, early + timedelta(days=1))
        _event(session, relapsed.id, 50, 50, later)
        _event(session, reviewed.id, 45, 45, early)
        _quiz(session, goal.id, 45, early)
        schedule = ReviewSchedule(goal_id=goal.id, knowledge_point_id=reviewed.id, next_review_date=_today(), updated_at=later)
        session.add(schedule)
        session.commit()
        session.refresh(schedule)
        session.add(
            ReviewRecord(
                schedule_id=schedule.id,
                knowledge_point_id=reviewed.id,
                reviewed_at=later,
                score=92,
                result="pass",
                next_interval=3,
                next_review_date=_today(),
                reason="复习通过",
            )
        )
        session.add(
            TrainingRecommendation(
                user_id=user.id,
                goal_id=goal.id,
                knowledge_point_id=still.id,
                category="knowledge_understanding",
                title="补基础",
                description="完成建议不等于薄弱点消失",
                reason="低分",
                estimated_minutes=15,
                priority=2,
                completion_criteria="做完即可",
                status="completed",
                created_at=later,
                updated_at=later,
            )
        )
        fixed = _problem(session, user.id, "后来通过")
        open_error = _problem(session, user.id, "系统异常后通过")
        manual = _problem(session, user.id, "自评不能算通过")
        bounced = _problem(session, user.id, "通过后又错")
        first = _submission(session, user.id, fixed.id, "wrong_answer", early)
        second = _submission(session, user.id, fixed.id, "accepted", later)
        _judge(session, user.id, first, "wrong_answer", early)
        _judge(session, user.id, second, "accepted", later)
        noise = _submission(session, user.id, open_error.id, "system_error", early)
        followed = _submission(session, user.id, open_error.id, "accepted", later)
        _judge(session, user.id, noise, "system_error", early)
        _judge(session, user.id, followed, "accepted", later)
        wrong = _submission(session, user.id, manual.id, "wrong_answer", early)
        _judge(session, user.id, wrong, "wrong_answer", early)
        session.add(ProblemLearningStatus(user_id=user.id, problem_id=manual.id, status="self_completed", created_at=later, updated_at=later))
        bad = _submission(session, user.id, bounced.id, "wrong_answer", early)
        good = _submission(session, user.id, bounced.id, "accepted", early + timedelta(days=1))
        again = _submission(session, user.id, bounced.id, "wrong_answer", later)
        _judge(session, user.id, bad, "wrong_answer", early)
        _judge(session, user.id, good, "accepted", early + timedelta(days=1))
        _judge(session, user.id, again, "wrong_answer", later)
        session.commit()

    weaknesses = client.get("/api/learning/growth").json()["weaknesses"]
    improved = {(item["subject"], item["name"]) for item in weaknesses["improved"]}
    present = {(item["subject"], item["name"]) for item in weaknesses["still_present"]}
    assert improved == {("knowledge", "已恢复"), ("knowledge", "复习后通过"), ("problem", "后来通过")}
    assert ("knowledge", "仍然低分") in present
    assert ("knowledge", "再次下降") in present
    assert ("problem", "自评不能算通过") in present
    assert ("problem", "通过后又错") in present
    assert ("knowledge", "另一知识点") not in improved
    assert ("problem", "系统异常后通过") not in improved
    assert ("problem", "系统异常后通过") not in present
    recovered_item = next(item for item in weaknesses["improved"] if item["name"] == "已恢复")
    assert recovered_item["earlier"]["quiz_score"] == 40
    assert recovered_item["later"]["quiz_score"] == 85
    assert recovered_item["earlier"]["source"] == "quiz"
    assert recovered_item["later"]["source"] == "quiz"
    assert recovered_item["earlier"]["id"] != recovered_item["later"]["id"]
    review_item = next(item for item in weaknesses["improved"] if item["name"] == "复习后通过")
    assert review_item["earlier"]["source"] == "quiz"
    assert review_item["later"]["source"] == "review"
    assert review_item["later"]["score"] == 92


def test_goal_filter_keeps_other_goal_activity_out() -> None:
    user = _local_user()
    with Session(engine) as session:
        first = _goal(session, user.id, "目标甲")
        second = _goal(session, user.id, "目标乙")
        point = _point(session, second.id, "只属于乙")
        plan = _plan(session, first.id)
        _task(session, plan.id, _at(0), estimated=25)
        _quiz(session, second.id, 70, _at(-1))
        _event(session, point.id, 70, 70, _at(-1))
        problem = _problem(session, user.id, "用户题目")
        _submission(session, user.id, problem.id, "unjudged", _at(0))
        solved = _problem(session, user.id, "另一道用户题目")
        accepted = _submission(session, user.id, solved.id, "accepted", _at(0))
        _judge(session, user.id, accepted, "accepted", _at(0))
        session.commit()
        first_id, second_id = first.id, second.id

    all_goals = client.get("/api/learning/growth", params={"days": 7}).json()
    only_first = client.get("/api/learning/growth", params={"goal_id": first_id, "days": 7}).json()
    only_second = client.get("/api/learning/growth", params={"goal_id": second_id, "days": 7}).json()
    assert all_goals["summary"]["completed_task_count"] == 1
    assert all_goals["summary"]["completed_quiz_count"] == 1
    assert all_goals["summary"]["study_day_count"] == 2
    assert only_first["summary"]["completed_task_count"] == 1
    assert only_first["summary"]["completed_quiz_count"] == 0
    assert only_first["summary"]["current_streak_days"] == 1
    assert only_first["mastery"]["points"] == []
    assert only_second["summary"]["completed_task_count"] == 0
    assert only_second["summary"]["completed_quiz_count"] == 1
    assert only_second["summary"]["current_streak_days"] == 0
    assert [item["name"] for item in only_second["mastery"]["points"]] == ["只属于乙"]
    assert only_first["summary"]["submission_count"] == 2
    assert only_second["summary"]["submission_count"] == 2
    assert all_goals["practice_scope"] == "current_user_all_problems"
    assert only_first["practice_scope"] == all_goals["practice_scope"]
    assert only_second["practice_scope"] == all_goals["practice_scope"]
    for key in ("submitted_problem_count", "submission_count", "local_accepted_problem_count", "local_accepted_submission_count", "pass_rate", "pass_rate_numerator", "pass_rate_denominator"):
        assert only_first["summary"][key] == all_goals["summary"][key]
        assert only_second["summary"][key] == all_goals["summary"][key]
    assert only_first["practice"]["judge_counts"] == all_goals["practice"]["judge_counts"]
    assert only_second["practice"]["judge_counts"] == all_goals["practice"]["judge_counts"]
    assert all_goals["summary"]["pass_rate_numerator"] == 1
    assert all_goals["summary"]["pass_rate_denominator"] == 1
    assert all(item["submission_count"] == 0 for item in only_first["series"])
    assert sum(item["submission_count"] for item in only_first["practice"]["series"]) == 2


def test_utc_and_local_midnights_use_server_local_date() -> None:
    user = _local_user()
    local_midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    utc_midnight = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    utc_midnight = utc_midnight.replace(hour=0)
    samples = {
        "本地午夜前": (local_midnight - timedelta(minutes=30)).astimezone(timezone.utc),
        "本地午夜后": (local_midnight + timedelta(minutes=30)).astimezone(timezone.utc),
        "UTC午夜前": (utc_midnight - timedelta(minutes=30)).astimezone(timezone.utc),
        "UTC午夜后": (utc_midnight + timedelta(minutes=30)).astimezone(timezone.utc),
    }
    with Session(engine) as session:
        goal = _goal(session, user.id, "时区")
        for title, moment in samples.items():
            _quiz(session, goal.id, 80, moment, title)
        session.commit()

    body = client.get("/api/learning/growth", params={"days": 7}).json()
    listed = {item["title"]: item["date"] for item in body["quizzes"]["last_7_days"]}
    saw_local_difference = False
    for title, moment in samples.items():
        local_day = moment.astimezone().date().isoformat()
        utc_day = moment.astimezone(timezone.utc).date().isoformat()
        assert listed[title] == local_day
        if local_day != utc_day:
            saw_local_difference = True
            assert listed[title] != utc_day
    before_local = samples["本地午夜前"]
    after_local = samples["本地午夜后"]
    if before_local.date() == after_local.date():
        assert listed["本地午夜前"] != listed["本地午夜后"]
    before_utc = samples["UTC午夜前"]
    after_utc = samples["UTC午夜后"]
    if before_utc.astimezone().date() == after_utc.astimezone().date():
        assert listed["UTC午夜前"] == listed["UTC午夜后"]
        assert before_utc.date() != after_utc.date()
    if datetime.now().astimezone().utcoffset() != timedelta(0):
        assert saw_local_difference

    with Session(engine) as session:
        quiz = session.exec(select(Quiz).where(Quiz.title == "UTC午夜前")).one()
        assert quiz.submitted_at is not None
        assert quiz.submitted_at.tzinfo == timezone.utc
        quiz_id = quiz.id
    stored = sqlite3.connect(settings.database_path).execute("select submitted_at from quizzes where id = ?", (quiz_id,)).fetchone()[0]
    assert stored.startswith(samples["UTC午夜前"].strftime("%Y-%m-%d %H:%M"))
    assert "+" not in stored


def test_other_user_records_stay_out() -> None:
    local = _local_user()
    with Session(engine) as session:
        own = _problem(session, local.id, "自己的题")
        _submission(session, local.id, own.id, "unjudged", _at(0))
        other = User(username=uuid4().hex, created_at=datetime.now(timezone.utc))
        session.add(other)
        session.commit()
        session.refresh(other)
        goal = _goal(session, other.id, "别人的目标")
        problem = _problem(session, other.id, "别人的题")
        submission = _submission(session, other.id, problem.id, "accepted", _at(0))
        _judge(session, other.id, submission, "accepted", _at(0))
        session.commit()
        other_goal_id = goal.id

    body = client.get("/api/learning/growth").json()
    assert body["summary"]["submission_count"] == 1
    assert body["summary"]["local_accepted_submission_count"] == 0
    assert client.get("/api/learning/growth", params={"goal_id": other_goal_id}).status_code == 404


def test_repeated_reads_do_not_write() -> None:
    user = _local_user()
    with Session(engine) as session:
        goal = _goal(session, user.id, "只读")
        point = _point(session, goal.id, "只读知识点")
        _event(session, point.id, 60, 60, _at(-1))
        session.commit()
    before = _dump()
    with Session(engine) as session:
        with acting_as(user.id):
            growth_service.growth(session, None, 30)
        assert list(session.new) == []
        assert list(session.dirty) == []
    first = client.get("/api/learning/growth")
    second = client.get("/api/learning/growth")
    assert first.status_code == 200
    assert first.json() == second.json()
    assert _dump() == before
