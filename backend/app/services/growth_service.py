"""学习成长汇总。只读取已有记录，不写库，不调用模型。"""

from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.goal import LearningGoal
from app.models.judge import ProblemJudgeResult
from app.models.knowledge import KnowledgePoint
from app.models.plan import StudyPlan, StudyTask
from app.models.practice import ProblemLearningStatus, ProblemPracticeRecord, ProblemWrongRecord
from app.models.problem import Problem
from app.models.quiz import KnowledgeMasteryEvent, Quiz
from app.models.review import ReviewRecord
from app.models.submission import ProblemSubmission
from app.models.user import User
from app.services.goal_service import LOCAL_USERNAME

ALLOWED_DAYS = (7, 30, 90)
REVIEW_ACTIVITY = {"pass", "partial", "fail", "initial"}
USER_VERDICTS = {"accepted", "wrong_answer", "compile_error", "time_limit_exceeded", "runtime_error"}
USER_ERRORS = {"wrong_answer", "compile_error", "time_limit_exceeded", "runtime_error"}
PRACTICE_SCOPE = "current_user_all_problems"
QUIZ_NOTE = "不同检测的难度可能不同，成绩升降不能单独说明能力一定提升。"
WEAKNESS_NOTE = "只有同一知识点或同一题目的前后记录才能记为已改善。完成训练建议不会改变这里的结论。"


def growth(session: Session, goal_id: int | None, days: int) -> dict:
    """汇总当前用户的成长记录。goal_id 只收窄学习目标侧的数据。"""
    if days not in ALLOWED_DAYS:
        raise HTTPException(status_code=422, detail="days 只能是 7、30 或 90")
    today = datetime.now().astimezone().date()
    user = session.exec(select(User).where(User.username == LOCAL_USERNAME)).first()
    if user is None or user.id is None:
        if goal_id is not None:
            raise HTTPException(status_code=404, detail="学习目标不存在")
        return _empty(goal_id, days, today)
    goals = list(session.exec(select(LearningGoal).where(LearningGoal.user_id == user.id).order_by(LearningGoal.id)).all())
    if goal_id is not None and all(goal.id != goal_id for goal in goals):
        raise HTTPException(status_code=404, detail="学习目标不存在")
    selected = goals if goal_id is None else [goal for goal in goals if goal.id == goal_id]
    goal_ids = [goal.id for goal in selected if goal.id is not None]
    points = _points(session, goal_ids)
    point_ids = [point.id for point in points if point.id is not None]
    tasks = _completed_tasks(session, goal_ids)
    quizzes = _completed_quizzes(session, goal_ids)
    reviews = _reviews(session, point_ids)
    events = _events(session, point_ids)
    problems = list(session.exec(select(Problem).where(Problem.user_id == user.id).order_by(Problem.id)).all())
    problem_ids = {problem.id for problem in problems if problem.id is not None}
    submissions = [
        row
        for row in session.exec(select(ProblemSubmission).where(ProblemSubmission.user_id == user.id)).all()
        if row.problem_id in problem_ids
    ]
    judges = [
        row
        for row in session.exec(select(ProblemJudgeResult).where(ProblemJudgeResult.user_id == user.id)).all()
        if row.problem_id in problem_ids
    ]
    practices = [
        row
        for row in session.exec(select(ProblemPracticeRecord).where(ProblemPracticeRecord.user_id == user.id)).all()
        if row.problem_id in problem_ids
    ]
    statuses = [
        row
        for row in session.exec(select(ProblemLearningStatus).where(ProblemLearningStatus.user_id == user.id)).all()
        if row.problem_id in problem_ids
    ]
    wrongs = [
        row
        for row in session.exec(select(ProblemWrongRecord).where(ProblemWrongRecord.user_id == user.id)).all()
        if row.problem_id in problem_ids
    ]
    include_practice_in_study = goal_id is None
    study_days = _study_days(tasks, quizzes, reviews, practices if include_practice_in_study else [], submissions if include_practice_in_study else [])
    practice_stats = _practice_stats(submissions, judges, practices, statuses, wrongs)
    return {
        "goal_id": goal_id,
        "days": days,
        "today": today.isoformat(),
        "scope": {
            "study_activity": "all_goals" if goal_id is None else "selected_goal",
            "practice": PRACTICE_SCOPE,
            "dates": "server_local",
        },
        "practice_scope": PRACTICE_SCOPE,
        "summary": _summary(today, study_days, tasks, quizzes, reviews, practice_stats),
        "series": _series(today, days, tasks, quizzes, reviews, practices if include_practice_in_study else [], submissions if include_practice_in_study else []),
        "mastery": _mastery(points, events, reviews),
        "quizzes": _quiz_section(today, quizzes, points, events),
        "practice": {**practice_stats, "series": _practice_series(today, days, practices, submissions)},
        "weaknesses": _weaknesses(points, events, reviews, problems, judges),
    }


def _empty(goal_id: int | None, days: int, today: date) -> dict:
    stats = _practice_stats([], [], [], [], [])
    return {
        "goal_id": goal_id,
        "days": days,
        "today": today.isoformat(),
        "scope": {"study_activity": "all_goals" if goal_id is None else "selected_goal", "practice": PRACTICE_SCOPE, "dates": "server_local"},
        "practice_scope": PRACTICE_SCOPE,
        "summary": _summary(today, set(), [], [], [], stats),
        "series": _series(today, days, [], [], [], [], []),
        "mastery": {"sufficient": False, "points": []},
        "quizzes": _quiz_section(today, [], [], {}),
        "practice": {**stats, "series": _practice_series(today, days, [], [])},
        "weaknesses": {"improved": [], "still_present": [], "note": WEAKNESS_NOTE},
    }


def _points(session: Session, goal_ids: list[int]) -> list[KnowledgePoint]:
    if not goal_ids:
        return []
    return list(session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id.in_(goal_ids)).order_by(KnowledgePoint.id)).all())


def _completed_tasks(session: Session, goal_ids: list[int]) -> list[StudyTask]:
    if not goal_ids:
        return []
    rows = session.exec(
        select(StudyTask).join(StudyPlan, StudyPlan.id == StudyTask.plan_id).where(StudyPlan.goal_id.in_(goal_ids), StudyTask.status == "completed")
    ).all()
    return [row for row in rows if row.completed_at is not None]


def _completed_quizzes(session: Session, goal_ids: list[int]) -> list[Quiz]:
    if not goal_ids:
        return []
    rows = session.exec(select(Quiz).where(Quiz.goal_id.in_(goal_ids), Quiz.status == "completed")).all()
    return [row for row in rows if row.submitted_at is not None and row.score is not None]


def _reviews(session: Session, point_ids: list[int]) -> list[ReviewRecord]:
    if not point_ids:
        return []
    return list(session.exec(select(ReviewRecord).where(ReviewRecord.knowledge_point_id.in_(point_ids))).all())


def _events(session: Session, point_ids: list[int]) -> dict[int, list[KnowledgeMasteryEvent]]:
    grouped: dict[int, list[KnowledgeMasteryEvent]] = {point_id: [] for point_id in point_ids}
    if not point_ids:
        return grouped
    rows = session.exec(
        select(KnowledgeMasteryEvent)
        .where(KnowledgeMasteryEvent.knowledge_point_id.in_(point_ids))
        .order_by(KnowledgeMasteryEvent.created_at, KnowledgeMasteryEvent.id)
    ).all()
    for row in rows:
        grouped.setdefault(row.knowledge_point_id, []).append(row)
    return grouped


def _summary(today: date, study_days: set[date], tasks: list[StudyTask], quizzes: list[Quiz], reviews: list[ReviewRecord], practice: dict) -> dict:
    active_reviews = [row for row in reviews if row.result in REVIEW_ACTIVITY]
    return {
        "study_day_count": len(study_days),
        "current_streak_days": _streak(study_days, today),
        "studied_today": today in study_days,
        "completed_task_count": len(tasks),
        "completed_quiz_count": len(quizzes),
        "review_count": len(active_reviews),
        "practiced_problem_count": practice["practiced_problem_count"],
        "submitted_problem_count": practice["submitted_problem_count"],
        "submission_count": practice["submission_count"],
        "local_accepted_problem_count": practice["local_accepted_problem_count"],
        "local_accepted_submission_count": practice["local_accepted_submission_count"],
        "pass_rate": practice["pass_rate"],
        "pass_rate_numerator": practice["pass_rate_numerator"],
        "pass_rate_denominator": practice["pass_rate_denominator"],
        "actual_practice_seconds": practice["actual_practice_seconds"],
        "self_completed_problem_count": practice["self_completed_problem_count"],
    }


def _study_days(tasks: list[StudyTask], quizzes: list[Quiz], reviews: list[ReviewRecord], practices: list[ProblemPracticeRecord], submissions: list[ProblemSubmission]) -> set[date]:
    days: set[date] = set()
    for task in tasks:
        days.add(_local_day(task.completed_at))
    for quiz in quizzes:
        days.add(_local_day(quiz.submitted_at))
    for review in reviews:
        if review.result in REVIEW_ACTIVITY:
            days.add(_local_day(review.reviewed_at))
    for practice in practices:
        days.add(_local_day(practice.started_at))
        if practice.completed_at is not None:
            days.add(_local_day(practice.completed_at))
    for submission in submissions:
        days.add(_local_day(submission.submitted_at))
    return days


def _streak(days: set[date], today: date) -> int:
    streak = 0
    cursor = today
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _series(today: date, days: int, tasks: list[StudyTask], quizzes: list[Quiz], reviews: list[ReviewRecord], practices: list[ProblemPracticeRecord], submissions: list[ProblemSubmission]) -> list[dict]:
    window = _window(today, days)
    rows = {day: _blank_day(day) for day in window}
    for task in tasks:
        day = _local_day(task.completed_at)
        if day in rows:
            rows[day]["completed_task_count"] += 1
    for quiz in quizzes:
        day = _local_day(quiz.submitted_at)
        if day in rows:
            rows[day]["completed_quiz_count"] += 1
    for review in reviews:
        if review.result not in REVIEW_ACTIVITY:
            continue
        day = _local_day(review.reviewed_at)
        if day in rows:
            rows[day]["review_count"] += 1
    _add_practice_days(rows, practices, submissions)
    active = _study_days(tasks, quizzes, reviews, practices, submissions)
    for day, row in rows.items():
        row["has_activity"] = day in active
    return [rows[day] for day in window]


def _practice_series(today: date, days: int, practices: list[ProblemPracticeRecord], submissions: list[ProblemSubmission]) -> list[dict]:
    window = _window(today, days)
    rows = {day: _blank_day(day) for day in window}
    _add_practice_days(rows, practices, submissions)
    active = _study_days([], [], [], practices, submissions)
    for day, row in rows.items():
        row["has_activity"] = day in active
    return [rows[day] for day in window]


def _add_practice_days(rows: dict[date, dict], practices: list[ProblemPracticeRecord], submissions: list[ProblemSubmission]) -> None:
    for practice in practices:
        day = _local_day(practice.started_at)
        if day in rows:
            rows[day]["practice_count"] += 1
        seconds = _duration_seconds(practice)
        if seconds is None or day not in rows:
            continue
        row = rows[day]
        if not row["has_duration_record"]:
            row["actual_practice_seconds"] = 0
            row["has_duration_record"] = True
        row["actual_practice_seconds"] += seconds
    for submission in submissions:
        day = _local_day(submission.submitted_at)
        if day in rows:
            rows[day]["submission_count"] += 1


def _practice_stats(submissions: list[ProblemSubmission], judges: list[ProblemJudgeResult], practices: list[ProblemPracticeRecord], statuses: list[ProblemLearningStatus], wrongs: list[ProblemWrongRecord]) -> dict:
    judge_by_submission = {row.submission_id: row for row in judges}
    counts = {name: 0 for name in ("accepted", "wrong_answer", "compile_error", "time_limit_exceeded", "runtime_error", "system_error", "unjudged")}
    accepted_problems: set[int] = set()
    duration_seconds = 0
    duration_count = 0
    for submission in submissions:
        judge = judge_by_submission.get(submission.id)
        if judge is None or judge.status not in USER_VERDICTS | {"system_error"}:
            counts["unjudged"] += 1
            continue
        if judge.status == "system_error":
            counts["system_error"] += 1
            continue
        counts[judge.status] += 1
        if judge.status == "accepted":
            accepted_problems.add(submission.problem_id)
    for practice in practices:
        seconds = _duration_seconds(practice)
        if seconds is None:
            continue
        duration_seconds += seconds
        duration_count += 1
    numerator = counts["accepted"]
    denominator = sum(counts[name] for name in USER_VERDICTS)
    return {
        "scope": PRACTICE_SCOPE,
        "practice_scope": PRACTICE_SCOPE,
        "practiced_problem_count": len({row.problem_id for row in practices}),
        "submitted_problem_count": len({row.problem_id for row in submissions}),
        "submission_count": len(submissions),
        "local_accepted_problem_count": len(accepted_problems),
        "local_accepted_submission_count": numerator,
        "judge_counts": counts,
        "pass_rate_numerator": numerator,
        "pass_rate_denominator": denominator,
        "pass_rate": None if denominator == 0 else round(numerator / denominator, 4),
        "pass_rate_note": "分母是本地已出结果的提交，不含 system_error 和 unjudged。分子是其中的 accepted。这是本地测试通过，不是南开 OJ 官方 AC。",
        "actual_practice_seconds": None if duration_count == 0 else duration_seconds,
        "actual_practice_record_count": duration_count,
        "duration_note": "只累计同时有开始和结束、且结束不早于开始的练习。任务预计分钟不计入。",
        "self_completed_problem_count": sum(1 for row in statuses if row.status == "self_completed"),
        "wrong_record_count": len({row.problem_id for row in wrongs}),
    }


def _mastery(points: list[KnowledgePoint], events: dict[int, list[KnowledgeMasteryEvent]], reviews: list[ReviewRecord]) -> dict:
    rows = []
    for point in points:
        if point.id is None:
            continue
        history = events.get(point.id, [])
        review_dates = sorted({_local_day(row.reviewed_at).isoformat() for row in reviews if row.knowledge_point_id == point.id and row.result in REVIEW_ACTIVITY})
        rows.append(
            {
                "knowledge_point_id": point.id,
                "name": point.name,
                "goal_id": point.goal_id,
                "mastery_assessed": bool(history),
                "current_mastery": None if not history else history[-1].new_level,
                "direction": _direction(history),
                "history": [
                    {
                        "id": event.id,
                        "date": _local_day(event.created_at).isoformat(),
                        "previous_level": event.previous_level,
                        "mastery_level": event.new_level,
                        "quiz_score": event.quiz_score,
                    }
                    for event in history
                ],
                "review_dates": review_dates,
            }
        )
    return {"sufficient": any(len(item["history"]) >= 2 for item in rows), "points": rows}


def _direction(history: list[KnowledgeMasteryEvent]) -> str:
    if len(history) < 2:
        return "insufficient"
    delta = history[-1].new_level - history[0].new_level
    if delta > 0:
        return "up"
    if delta < 0:
        return "down"
    return "stable"


def _quiz_section(today: date, quizzes: list[Quiz], points: list[KnowledgePoint], events: dict[int, list[KnowledgeMasteryEvent]]) -> dict:
    ordered = sorted(quizzes, key=lambda item: (_aware(item.submitted_at), item.id or 0))
    scores = [quiz.score for quiz in ordered if quiz.score is not None]
    names = {point.id: point.name for point in points}
    by_point = []
    for point in points:
        if point.id is None:
            continue
        point_scores = [event.quiz_score for event in events.get(point.id, [])]
        by_point.append(
            {
                "knowledge_point_id": point.id,
                "name": names.get(point.id, point.name),
                "count": len(point_scores),
                "average_score": None if not point_scores else round(sum(point_scores) / len(point_scores)),
                "highest_score": None if not point_scores else max(point_scores),
                "lowest_score": None if not point_scores else min(point_scores),
                "scores": point_scores,
            }
        )
    return {
        "count": len(ordered),
        "average_score": None if not scores else round(sum(scores) / len(scores)),
        "highest_score": None if not scores else max(scores),
        "lowest_score": None if not scores else min(scores),
        "latest_score": None if not scores else scores[-1],
        "note": QUIZ_NOTE,
        "last_7_days": [_quiz_item(quiz) for quiz in ordered if _in_recent(today, quiz.submitted_at, 7)],
        "last_30_days": [_quiz_item(quiz) for quiz in ordered if _in_recent(today, quiz.submitted_at, 30)],
        "by_knowledge_point": by_point,
    }


def _quiz_item(quiz: Quiz) -> dict:
    return {
        "id": quiz.id,
        "goal_id": quiz.goal_id,
        "title": quiz.title,
        "date": _local_day(quiz.submitted_at).isoformat(),
        "score": quiz.score,
    }


def _weaknesses(points: list[KnowledgePoint], events: dict[int, list[KnowledgeMasteryEvent]], reviews: list[ReviewRecord], problems: list[Problem], judges: list[ProblemJudgeResult]) -> dict:
    improved = []
    still_present = []
    for point in points:
        if point.id is None:
            continue
        outcomes = []
        for event in events.get(point.id, []):
            outcomes.append(_outcome(_aware(event.created_at), event.quiz_score >= 60, _event_evidence(event)))
        for review in reviews:
            if review.knowledge_point_id != point.id:
                continue
            marker = _review_marker(review)
            if marker is None:
                continue
            success, evidence = marker
            outcomes.append(_outcome(_aware(review.reviewed_at), success, evidence))
        item = _change_item("knowledge", point.id, None, point.name, outcomes)
        if item is not None:
            (improved if item["status"] == "improved" else still_present).append(item)
    titles = {problem.id: problem.title for problem in problems}
    by_problem: dict[int, list[ProblemJudgeResult]] = {}
    for judge in judges:
        by_problem.setdefault(judge.problem_id, []).append(judge)
    for problem_id, rows in sorted(by_problem.items()):
        outcomes = []
        for judge in sorted(rows, key=lambda item: (_judge_time(item), item.id or 0)):
            if judge.status == "accepted":
                success = True
            elif judge.status in USER_ERRORS:
                success = False
            else:
                continue
            outcomes.append(_outcome(_judge_time(judge), success, _judge_evidence(judge)))
        item = _change_item("problem", None, problem_id, titles.get(problem_id, ""), outcomes)
        if item is not None:
            (improved if item["status"] == "improved" else still_present).append(item)
    return {"improved": improved, "still_present": still_present, "note": WEAKNESS_NOTE}


def _change_item(subject: str, knowledge_point_id: int | None, problem_id: int | None, name: str, outcomes: list[dict]) -> dict | None:
    ordered = sorted(outcomes, key=lambda item: (item["at"], item["id"]))
    if not ordered:
        return None
    latest = ordered[-1]
    failures = [item for item in ordered if not item["success"]]

    def before(item: dict) -> bool:
        return (item["at"], item["id"]) < (latest["at"], latest["id"])

    if latest["success"]:
        earlier = None
        for item in ordered:
            if before(item) and not item["success"]:
                earlier = item
        if earlier is None:
            return None
        status = "improved"
    else:
        earlier = failures[0]
        status = "still_present"
    return {
        "subject": subject,
        "status": status,
        "knowledge_point_id": knowledge_point_id,
        "problem_id": problem_id,
        "name": name,
        "earlier": earlier["evidence"],
        "later": latest["evidence"],
    }


def _outcome(moment: datetime, success: bool, evidence: dict) -> dict:
    return {"at": moment, "id": evidence.get("id") or 0, "success": success, "evidence": evidence}


def _event_evidence(event: KnowledgeMasteryEvent) -> dict:
    return {
        "id": event.id,
        "source": "quiz",
        "date": _local_day(event.created_at).isoformat(),
        "quiz_score": event.quiz_score,
        "mastery_level": event.new_level,
    }


def _review_marker(review: ReviewRecord) -> tuple[bool, dict] | None:
    evidence = {
        "id": review.id,
        "source": "review",
        "date": _local_day(review.reviewed_at).isoformat(),
        "review_result": review.result,
        "score": review.score,
    }
    if review.result == "fail":
        return False, evidence
    if review.result == "pass" and review.score is not None and review.score >= 60:
        return True, evidence
    return None


def _judge_evidence(judge: ProblemJudgeResult) -> dict:
    moment = judge.judged_at or judge.created_at
    return {
        "id": judge.id,
        "source": "judge",
        "date": _local_day(moment).isoformat(),
        "judge_status": judge.status,
        "submission_id": judge.submission_id,
        "problem_id": judge.problem_id,
    }


def _judge_time(judge: ProblemJudgeResult) -> datetime:
    return _aware(judge.judged_at or judge.created_at)


def _duration_seconds(practice: ProblemPracticeRecord) -> int | None:
    if practice.completed_at is None:
        return None
    start = _aware(practice.started_at)
    end = _aware(practice.completed_at)
    if end < start:
        return None
    return int((end - start).total_seconds())


def _window(today: date, days: int) -> list[date]:
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def _blank_day(day: date) -> dict:
    return {
        "date": day.isoformat(),
        "has_activity": False,
        "completed_task_count": 0,
        "completed_quiz_count": 0,
        "review_count": 0,
        "practice_count": 0,
        "submission_count": 0,
        "has_duration_record": False,
        "actual_practice_seconds": None,
    }


def _in_recent(today: date, moment: datetime | None, days: int) -> bool:
    if moment is None:
        return False
    day = _local_day(moment)
    return today - timedelta(days=days - 1) <= day <= today


def _local_day(value: datetime | None) -> date:
    if value is None:
        raise ValueError("缺少时间")
    return _aware(value).astimezone().date()


def _aware(value: datetime) -> datetime:
    """SQLite 不保存偏移。写入时 SQLModel 先换成 UTC，读出时无偏移的值也按 UTC 理解。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
