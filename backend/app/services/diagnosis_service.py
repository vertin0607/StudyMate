"""只读汇总已有学习记录。不写库，不调用模型，也不把两套知识点连在一起。"""

import json
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.goal import LearningGoal
from app.models.judge import ProblemJudgeResult
from app.models.knowledge import KnowledgePoint
from app.models.plan import StudyPlan, StudyTask
from app.models.practice import ProblemLearningStatus, ProblemPracticeRecord, ProblemWrongRecord
from app.models.problem import Problem
from app.models.quiz import KnowledgeMasteryEvent, Quiz
from app.models.review import ReviewRecord, ReviewSchedule
from app.models.submission import ProblemSubmission
from app.models.tutor import TutorMessage, TutorSession
from app.services.goal_service import LOCAL_USERNAME, ensure_local_user
from app.models.user import User

JUDGE_STATUSES = (
    "accepted",
    "wrong_answer",
    "compile_error",
    "time_limit_exceeded",
    "runtime_error",
    "system_error",
    "judging",
)
LEARNING_STATUSES = (
    "todo",
    "attempting",
    "self_completed",
    "accepted",
    "wrong_answer",
    "compile_error",
    "time_limit_exceeded",
    "runtime_error",
)


def snapshot(session: Session) -> dict:
    user = _user(session)
    goals = list(session.exec(select(LearningGoal).where(LearningGoal.user_id == user.id).order_by(LearningGoal.id)).all())
    goal_ids = [goal.id for goal in goals if goal.id is not None]
    points = _points(session, goal_ids)
    point_ids = [point.id for point in points if point.id is not None]
    problems = list(session.exec(select(Problem).where(Problem.user_id == user.id).order_by(Problem.id)).all())
    problem_ids = [problem.id for problem in problems if problem.id is not None]
    return {
        "knowledge": _knowledge(session, goals, points, point_ids),
        "practice": _practice(session, user.id, problems, problem_ids),
        "tutor": _tutor(session, user.id, points),
        "behavior": _behavior(session, goal_ids, point_ids),
        "meanings": {
            "accepted": "本地判题通过，不是官方 OJ 的 AC",
            "self_completed": "用户自评完成，不是系统判题通过",
            "system_error": "判题环境异常，不是用户答案错误",
        },
    }


def _user(session: Session) -> User:
    found = session.exec(select(User).where(User.username == LOCAL_USERNAME)).first()
    if found is not None:
        return found
    return ensure_local_user(session)


def _points(session: Session, goal_ids: list[int]) -> list[KnowledgePoint]:
    if not goal_ids:
        return []
    return list(session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id.in_(goal_ids)).order_by(KnowledgePoint.id)).all())


def _knowledge(session: Session, goals: list[LearningGoal], points: list[KnowledgePoint], point_ids: list[int]) -> dict:
    events = _events(session, point_ids)
    schedules = _schedules(session, point_ids)
    today = datetime.now().astimezone().date()
    rows = []
    for point in points:
        history = events.get(point.id, [])
        scores = [item.quiz_score for item in history]
        schedule = schedules.get(point.id)
        assessed = bool(history) or point.status == "mastered"
        review = None
        if schedule is not None:
            review = {
                "next_review_date": schedule.next_review_date.isoformat(),
                "last_reviewed_at": schedule.last_reviewed_at,
                "last_score": schedule.last_score,
                "due": schedule.next_review_date == today,
                "overdue": schedule.next_review_date < today,
            }
        rows.append(
            {
                "id": point.id,
                "goal_id": point.goal_id,
                "name": point.name,
                "status": point.status,
                "mastery_level": None if not assessed else point.mastery_level,
                "assessed": assessed,
                "quiz_count": len(history),
                "latest_score": None if not scores else scores[-1],
                "recent_scores": scores[-3:],
                "consecutive_low_scores": _low_streak(scores),
                "last_quiz_at": None if not history else history[-1].created_at,
                "review": review,
            }
        )
    return {"goal_count": len(goals), "point_count": len(points), "points": rows}


def _practice(session: Session, user_id: int | None, problems: list[Problem], problem_ids: list[int]) -> dict:
    statuses = {
        row.problem_id: row.status
        for row in session.exec(select(ProblemLearningStatus).where(ProblemLearningStatus.user_id == user_id)).all()
        if row.problem_id in set(problem_ids)
    }
    submissions = list(session.exec(select(ProblemSubmission).where(ProblemSubmission.user_id == user_id)).all()) if problem_ids else []
    submissions = [item for item in submissions if item.problem_id in set(problem_ids)]
    judges = list(session.exec(select(ProblemJudgeResult).where(ProblemJudgeResult.user_id == user_id)).all()) if problem_ids else []
    judges = [item for item in judges if item.problem_id in set(problem_ids)]
    practices = list(session.exec(select(ProblemPracticeRecord).where(ProblemPracticeRecord.user_id == user_id)).all()) if problem_ids else []
    practices = [item for item in practices if item.problem_id in set(problem_ids)]
    wrongs = {
        row.problem_id: row
        for row in session.exec(select(ProblemWrongRecord).where(ProblemWrongRecord.user_id == user_id)).all()
        if row.problem_id in set(problem_ids)
    }
    learning_counts = {name: 0 for name in LEARNING_STATUSES}
    judge_counts = {name: 0 for name in JUDGE_STATUSES}
    last_submit: dict[int, datetime] = {}
    practice_counts: dict[int, int] = {}
    judge_by_problem: dict[int, dict[str, int]] = {}
    for problem in problems:
        learning_counts[statuses.get(problem.id, "todo")] = learning_counts.get(statuses.get(problem.id, "todo"), 0) + 1
    for item in judges:
        judge_counts[item.status] = judge_counts.get(item.status, 0) + 1
        bucket = judge_by_problem.setdefault(item.problem_id, {name: 0 for name in JUDGE_STATUSES})
        bucket[item.status] = bucket.get(item.status, 0) + 1
    for item in submissions:
        current = last_submit.get(item.problem_id)
        if current is None or item.submitted_at > current:
            last_submit[item.problem_id] = item.submitted_at
    for item in practices:
        practice_counts[item.problem_id] = practice_counts.get(item.problem_id, 0) + 1
    rows = []
    for problem in problems:
        wrong = wrongs.get(problem.id)
        rows.append(
            {
                "id": problem.id,
                "title": problem.title,
                "difficulty": problem.difficulty,
                "learning_status": statuses.get(problem.id, "todo"),
                "practice_count": practice_counts.get(problem.id, 0),
                "last_submitted_at": last_submit.get(problem.id),
                "judge_counts": judge_by_problem.get(problem.id, {name: 0 for name in JUDGE_STATUSES}),
                "wrong_reason_type": None if wrong is None else wrong.reason_type,
                "wrong_reason_detail": "" if wrong is None else wrong.reason_detail,
            }
        )
    return {
        "problem_count": len(problems),
        "submission_count": len(submissions),
        "learning_status_counts": learning_counts,
        "judge_result_counts": judge_counts,
        "problems": rows,
    }


def _tutor(session: Session, user_id: int | None, points: list[KnowledgePoint]) -> dict:
    owned = {point.id: point.name for point in points if point.id is not None}
    counts = {point_id: 0 for point_id in owned}
    if user_id is not None and owned:
        messages = session.exec(
            select(TutorMessage)
            .join(TutorSession, TutorSession.id == TutorMessage.session_id)
            .where(TutorSession.user_id == user_id, TutorMessage.role == "user")
        ).all()
        for message in messages:
            for point_id in _message_points(message.knowledge_point_ids_json):
                if point_id in counts:
                    counts[point_id] += 1
    asked = [
        {"knowledge_point_id": point_id, "name": name, "user_message_count": counts[point_id]}
        for point_id, name in owned.items()
        if counts[point_id] > 0
    ]
    return {
        "asked": asked,
        "note": "询问次数只说明用户提过这个问题，不能据此认定未掌握",
    }


def _behavior(session: Session, goal_ids: list[int], point_ids: list[int]) -> dict:
    tasks = []
    quizzes = []
    reviews = []
    if goal_ids:
        tasks = list(
            session.exec(
                select(StudyTask)
                .join(StudyPlan, StudyPlan.id == StudyTask.plan_id)
                .where(StudyPlan.goal_id.in_(goal_ids), StudyTask.status == "completed")
            ).all()
        )
        quizzes = list(session.exec(select(Quiz).where(Quiz.goal_id.in_(goal_ids), Quiz.status == "completed")).all())
    if point_ids:
        reviews = list(session.exec(select(ReviewRecord).where(ReviewRecord.knowledge_point_id.in_(point_ids))).all())
    dates: set[str] = set()
    for task in tasks:
        if task.completed_at is not None:
            dates.add(_day(task.completed_at))
    for quiz in quizzes:
        if quiz.submitted_at is not None:
            dates.add(_day(quiz.submitted_at))
    for record in reviews:
        dates.add(_day(record.reviewed_at))
    return {
        "completed_task_count": len(tasks),
        "completed_quiz_count": len(quizzes),
        "review_record_count": len(reviews),
        "active_dates": sorted(dates),
    }


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


def _schedules(session: Session, point_ids: list[int]) -> dict[int, ReviewSchedule]:
    if not point_ids:
        return {}
    rows = session.exec(select(ReviewSchedule).where(ReviewSchedule.knowledge_point_id.in_(point_ids))).all()
    return {row.knowledge_point_id: row for row in rows}


def _low_streak(scores: list[int]) -> int:
    streak = 0
    for score in reversed(scores):
        if score >= 60:
            break
        streak += 1
    return streak


def _message_points(raw: str) -> list[int]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, int)]


def _day(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().date().isoformat()
