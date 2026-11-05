"""复习队列、复习出题和学习记忆。首页查询不会调用模型。"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.goal import LearningGoal
from app.models.knowledge import KnowledgePoint
from app.models.plan import StudyTask
from app.models.quiz import KnowledgeMasteryEvent, Quiz, QuizAnswer, QuizQuestion
from app.models.review import ReviewRecord, ReviewSchedule
from app.services import goal_service
from app.services.ai.deepseek_client import complete_json
from app.services.ai.errors import AIError
from app.services.ai.prompt_builder import MAX_ATTEMPTS, build_repair_messages
from app.services.ai.quiz_parser import parse_quiz
from app.services.mastery import status_label
from app.services.review_scheduler import decide_review, forgetting_risk, next_review_day

logger = logging.getLogger(__name__)
REVIEW_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "review.txt"
RISK_LABELS = {"low": "低风险", "medium": "中风险", "high": "高风险"}


def local_today():
    return datetime.now().astimezone().date()


def apply_after_quiz(session: Session, quiz: Quiz, point_scores: dict[int, list[int]], errors: dict[int, list[str]], now: datetime) -> list[dict]:
    """检测提交成功后更新复习间隔。调用方负责提交事务。"""
    summaries = []
    today = now.astimezone().date()
    for point_id, scores in point_scores.items():
        point = session.get(KnowledgePoint, point_id)
        if point is None:
            continue
        latest = round(sum(scores) / len(scores))
        schedule = session.exec(select(ReviewSchedule).where(ReviewSchedule.knowledge_point_id == point.id)).first()
        is_first = schedule is None
        passes = 0 if schedule is None else schedule.successful_passes
        interval = 1 if schedule is None else schedule.interval_days
        high = 0 if schedule is None else schedule.consecutive_high
        review_count = 0 if schedule is None else schedule.review_count
        due_date = None if schedule is None else schedule.next_review_date
        decision = decide_review(
            is_first_assessment=is_first,
            successful_passes=passes,
            previous_interval=interval,
            latest_score=latest,
            consecutive_high=high,
        )
        event = session.exec(
            select(KnowledgeMasteryEvent)
            .where(KnowledgeMasteryEvent.knowledge_point_id == point.id, KnowledgeMasteryEvent.quiz_id == quiz.id)
            .order_by(KnowledgeMasteryEvent.created_at.desc())
        ).first()
        previous_mastery = None if event is None else event.previous_level
        next_day = next_review_day(today, decision.interval_days)
        if schedule is None:
            schedule = ReviewSchedule(
                goal_id=point.goal_id,
                knowledge_point_id=point.id,
                next_review_date=next_day,
            )
            session.add(schedule)
            session.flush()
        schedule.successful_passes = decision.successful_passes
        schedule.consecutive_high = decision.consecutive_high
        schedule.review_count = review_count if is_first else review_count + 1
        schedule.interval_days = decision.interval_days
        schedule.last_reviewed_at = now
        schedule.last_score = latest
        schedule.next_review_date = next_day
        schedule.reason = decision.reason[:500]
        schedule.open_quiz_id = None
        schedule.updated_at = now
        session.add(schedule)
        session.add(
            ReviewRecord(
                schedule_id=schedule.id,
                knowledge_point_id=point.id,
                quiz_id=quiz.id,
                reviewed_at=now,
                due_date=due_date,
                score=latest,
                result=decision.result,
                error_summary="；".join(errors.get(point_id, []))[:500],
                previous_mastery=previous_mastery,
                new_mastery=point.mastery_level,
                next_interval=decision.interval_days,
                next_review_date=next_day,
                reason=decision.reason[:500],
            )
        )
        summaries.append(_summary(schedule, point, decision.reason))
    return summaries


def today_queue(session: Session) -> dict:
    today = local_today()
    _backfill(session, today)
    cards = [_card(session, item, today) for item in _active_schedules(session)]
    due = [item for item in cards if item["queue"] == "due"]
    overdue = [item for item in cards if item["queue"] == "overdue"]
    upcoming = [item for item in cards if item["queue"] == "upcoming"]
    completed = _completed_on(session, today)
    high = [item for item in overdue + due if item["risk"] == "high"]
    return {
        "review_date": today,
        "due": _prioritize(due),
        "overdue": _prioritize(overdue),
        "upcoming": sorted(upcoming, key=lambda item: item["next_review_date"]),
        "due_count": len(due),
        "overdue_count": len(overdue),
        "upcoming_count": len(upcoming),
        "completed_today": len(completed),
        "high_risk": [{"id": item["id"], "name": item["name"], "risk_reason": item["risk_reason"]} for item in _prioritize(high)],
    }


def list_by_queue(session: Session, queue: str) -> dict:
    payload = today_queue(session)
    return {"review_date": payload["review_date"], "items": payload[queue]}


def get_review(session: Session, schedule_id: int) -> dict:
    schedule = _owned_schedule(session, schedule_id)
    point = session.get(KnowledgePoint, schedule.knowledge_point_id)
    card = _card(session, schedule, local_today())
    card["memory"] = None if point is None else memory_profile(session, point)
    return card


def postpone(session: Session, schedule_id: int, days: int) -> dict:
    schedule = _owned_schedule(session, schedule_id)
    goal = goal_service.get_goal(session, schedule.goal_id)
    if goal.status != "active":
        raise HTTPException(status_code=400, detail="暂停或已完成的目标不再安排复习")
    today = local_today()
    now = datetime.now(timezone.utc)
    next_day = today + timedelta(days=days)
    point = session.get(KnowledgePoint, schedule.knowledge_point_id)
    schedule.postpone_count += 1
    schedule.next_review_date = next_day
    schedule.reason = f"用户推迟 {days} 天，下次复习改到 {next_day.isoformat()}"
    schedule.updated_at = now
    session.add(schedule)
    session.add(
        ReviewRecord(
            schedule_id=schedule.id,
            knowledge_point_id=schedule.knowledge_point_id,
            reviewed_at=now,
            due_date=today,
            score=None,
            result="postponed",
            previous_mastery=None if point is None else point.mastery_level,
            new_mastery=None if point is None else point.mastery_level,
            next_interval=schedule.interval_days,
            next_review_date=next_day,
            reason=schedule.reason,
        )
    )
    goal_service.commit_or_raise(session)
    session.refresh(schedule)
    return _card(session, schedule, today)


def start_review(session: Session, schedule_id: int) -> dict:
    schedule = _owned_schedule(session, schedule_id)
    goal = goal_service.get_goal(session, schedule.goal_id)
    if goal.status != "active":
        raise HTTPException(status_code=400, detail="暂停或已完成的目标不能开始复习")
    if schedule.next_review_date > local_today():
        raise HTTPException(status_code=400, detail="还没到复习日期")
    if schedule.open_quiz_id is not None:
        existing = session.get(Quiz, schedule.open_quiz_id)
        if existing is not None and existing.status == "ready":
            from app.services.quiz_service import _public_quiz

            return _public_quiz(session, existing)
    point = session.get(KnowledgePoint, schedule.knowledge_point_id)
    if point is None or point.id is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    draft = _request_review_quiz(session, goal, point)
    now = datetime.now(timezone.utc)
    quiz = Quiz(goal_id=goal.id, title=draft.title, status="ready", created_at=now)
    session.add(quiz)
    session.flush()
    for index, item in enumerate(draft.questions):
        session.add(
            QuizQuestion(
                quiz_id=quiz.id,
                knowledge_point_id=item.knowledge_point_id,
                sort_order=index,
                question_type=item.question_type,
                difficulty=item.difficulty,
                stem=item.stem,
                options_json=json.dumps(item.options, ensure_ascii=False),
                correct_answer=item.correct_answer,
                explanation=item.explanation,
                created_at=now,
            )
        )
    schedule.open_quiz_id = quiz.id
    schedule.updated_at = now
    session.add(schedule)
    goal_service.commit_or_raise(session)
    session.refresh(quiz)
    logger.info("已保存复习检测 %s", quiz.id)
    from app.services.quiz_service import _public_quiz

    return _public_quiz(session, quiz)


def history(session: Session) -> dict:
    goal_ids = _active_goal_ids(session, include_inactive=True)
    if not goal_ids:
        return {"records": []}
    point_ids = [point.id for point in session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id.in_(goal_ids))).all() if point.id is not None]
    if not point_ids:
        return {"records": []}
    records = session.exec(
        select(ReviewRecord).where(ReviewRecord.knowledge_point_id.in_(point_ids)).order_by(ReviewRecord.reviewed_at.desc())
    ).all()
    names = {point.id: point.name for point in session.exec(select(KnowledgePoint).where(KnowledgePoint.id.in_(point_ids))).all()}
    return {
        "records": [
            {
                "id": item.id,
                "knowledge_point_id": item.knowledge_point_id,
                "name": names.get(item.knowledge_point_id, "知识点"),
                "quiz_id": item.quiz_id,
                "reviewed_at": item.reviewed_at,
                "due_date": item.due_date,
                "score": item.score,
                "result": item.result,
                "error_summary": item.error_summary,
                "previous_mastery": item.previous_mastery,
                "new_mastery": item.new_mastery,
                "next_interval": item.next_interval,
                "next_review_date": item.next_review_date,
                "reason": item.reason,
            }
            for item in records
        ]
    }


def due_for_planning(session: Session, goal_id: int) -> list[dict]:
    today = local_today()
    _backfill(session, today)
    schedules = session.exec(select(ReviewSchedule).where(ReviewSchedule.goal_id == goal_id, ReviewSchedule.next_review_date <= today)).all()
    cards = [_card(session, item, today) for item in schedules]
    return [
        {
            "name": item["name"],
            "mastery_level": item["mastery_level"],
            "risk": item["risk"],
            "overdue_days": item["overdue_days"],
            "reason": item["risk_reason"],
        }
        for item in _prioritize(cards)
    ]


def memory_profile(session: Session, point: KnowledgePoint) -> dict:
    tasks = session.exec(select(StudyTask).where(StudyTask.knowledge_point_id == point.id, StudyTask.status == "completed")).all()
    events = session.exec(
        select(KnowledgeMasteryEvent).where(KnowledgeMasteryEvent.knowledge_point_id == point.id).order_by(KnowledgeMasteryEvent.created_at)
    ).all()
    schedule = session.exec(select(ReviewSchedule).where(ReviewSchedule.knowledge_point_id == point.id)).first()
    scores = [event.quiz_score for event in events]
    streak = 0
    for score in reversed(scores):
        if score < 60:
            break
        streak += 1
    wrongs = _weak_reasons(session, point.id)
    assessed = bool(events) or point.status == "mastered"
    return {
        "first_seen_at": point.created_at,
        "last_studied_at": max((task.completed_at for task in tasks if task.completed_at is not None), default=None),
        "last_quiz_at": None if not events else events[-1].created_at,
        "study_count": len(tasks),
        "quiz_count": len(events),
        "average_score": round(sum(scores) / len(scores)) if scores else None,
        "latest_score": None if not scores else scores[-1],
        "mastery_level": None if not assessed else point.mastery_level,
        "mastery_assessed": assessed,
        "status_label": status_label(point.status, assessed),
        "correct_streak": streak,
        "weak_points": wrongs,
        "next_review_date": None if schedule is None else schedule.next_review_date,
        "interval_days": None if schedule is None else schedule.interval_days,
        "stage_label": "未安排" if schedule is None else _stage_label(schedule.successful_passes),
        "review_reason": "" if schedule is None else schedule.reason,
    }


def trends(session: Session, knowledge_id: int | None) -> dict:
    points = _points_for_user(session, knowledge_id)
    series = []
    for point in points:
        events = session.exec(
            select(KnowledgeMasteryEvent).where(KnowledgeMasteryEvent.knowledge_point_id == point.id).order_by(KnowledgeMasteryEvent.created_at)
        ).all()
        series.append(
            {
                "knowledge_point_id": point.id,
                "name": point.name,
                "sufficient": len(events) >= 2,
                "points": [
                    {"date": event.created_at, "mastery_level": event.new_level, "quiz_score": event.quiz_score}
                    for event in events
                ],
            }
        )
    return {"sufficient": any(item["sufficient"] for item in series), "series": series}


def risk_report(session: Session) -> dict:
    today = local_today()
    _backfill(session, today)
    items = [_card(session, schedule, today) for schedule in _active_schedules(session, include_inactive=True)]
    return {"items": items}


def review_statistics(session: Session) -> dict:
    today = local_today()
    queue = today_queue(session)
    records = history(session)["records"]
    graded = [item for item in records if item["result"] in {"pass", "partial", "fail", "initial"} and item["score"] is not None]
    week_start = today - timedelta(days=today.weekday())
    week_count = 0
    on_time = 0
    scheduled = 0
    for item in graded:
        reviewed_on = item["reviewed_at"].astimezone().date()
        if reviewed_on >= week_start:
            week_count += 1
        if item["due_date"] is not None and item["result"] != "initial":
            scheduled += 1
            if reviewed_on <= item["due_date"]:
                on_time += 1
    weak = [item for item in queue_all_cards(session) if item["mastery_level"] is not None and item["mastery_level"] < 60]
    improved = _progress(session)
    return {
        "sufficient": bool(graded),
        "review_count": len(graded),
        "week_count": week_count,
        "due_count": queue["due_count"],
        "overdue_count": queue["overdue_count"],
        "completed_today": queue["completed_today"],
        "average_score": round(sum(item["score"] for item in graded) / len(graded)) if graded else None,
        "on_time_ratio": None if scheduled == 0 else round(on_time / scheduled, 2),
        "weak_points": weak[:5],
        "most_improved": improved["most_improved"],
        "recent_improved": improved["recent_improved"],
        "still_weak": improved["still_weak"],
    }


def queue_all_cards(session: Session) -> list[dict]:
    today = local_today()
    return [_card(session, item, today) for item in _active_schedules(session, include_inactive=True)]


def summaries_for_quiz(session: Session, quiz: Quiz) -> list[dict]:
    questions = session.exec(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id)).all()
    point_ids = {question.knowledge_point_id for question in questions}
    if not point_ids:
        return []
    schedules = session.exec(select(ReviewSchedule).where(ReviewSchedule.knowledge_point_id.in_(point_ids))).all()
    today = local_today()
    return [_card(session, item, today) for item in schedules]


def _backfill(session: Session, today) -> None:
    goal_ids = _active_goal_ids(session, include_inactive=True)
    if not goal_ids:
        return
    points = session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id.in_(goal_ids))).all()
    created = False
    for point in points:
        if point.id is None:
            continue
        exists = session.exec(select(ReviewSchedule).where(ReviewSchedule.knowledge_point_id == point.id)).first()
        if exists is not None:
            continue
        events = session.exec(
            select(KnowledgeMasteryEvent).where(KnowledgeMasteryEvent.knowledge_point_id == point.id).order_by(KnowledgeMasteryEvent.created_at)
        ).all()
        if not events:
            continue
        scores = [(event.created_at.astimezone().date(), event.quiz_score) for event in events]
        passes = 0
        high = 0
        interval = 1
        decision = None
        last_day = scores[0][0]
        for index, (day, score) in enumerate(scores):
            decision = decide_review(
                is_first_assessment=index == 0,
                successful_passes=passes,
                previous_interval=interval,
                latest_score=score,
                consecutive_high=high,
            )
            passes = decision.successful_passes
            high = decision.consecutive_high
            interval = decision.interval_days
            last_day = day
        if decision is None:
            continue
        session.add(
            ReviewSchedule(
                goal_id=point.goal_id,
                knowledge_point_id=point.id,
                successful_passes=decision.successful_passes,
                consecutive_high=decision.consecutive_high,
                review_count=max(0, len(events) - 1),
                interval_days=decision.interval_days,
                last_reviewed_at=events[-1].created_at,
                last_score=events[-1].quiz_score,
                next_review_date=next_review_day(last_day, decision.interval_days),
                reason=decision.reason[:500],
                updated_at=datetime.now(timezone.utc),
            )
        )
        created = True
    if created:
        goal_service.commit_or_raise(session)
    _ = today


def _request_review_quiz(session: Session, goal: LearningGoal, point: KnowledgePoint):
    wrongs = _weak_reasons(session, point.id)
    payload = {
        "goal": {"title": goal.title, "description": goal.description},
        "knowledge_point": {
            "id": point.id,
            "name": point.name,
            "description": point.description,
            "difficulty": point.difficulty,
            "status": point.status,
            "mastery_level": point.mastery_level,
        },
        "past_mistakes": wrongs,
        "instruction": "先判断知识点类型并列出五个考查维度，再出题。围绕过去的错误出题。没有错题时，检查这个知识点里容易混淆的地方。不要默认五道单选。",
    }
    messages = [
        {"role": "system", "content": REVIEW_PROMPT.read_text(encoding="utf-8")},
        {"role": "user", "content": "请生成复习题：\n" + json.dumps(payload, ensure_ascii=False)},
    ]
    allowed = {point.id} if point.id is not None else set()
    last_error = "复习题目未通过校验"
    raw = ""
    for attempt in range(MAX_ATTEMPTS):
        try:
            raw = complete_json(messages, max_tokens=2500)
            return parse_quiz(raw, allowed, point.id)
        except AIError as exc:
            last_error = exc.message
            logger.warning("复习出题未通过：%s", last_error)
            if attempt + 1 >= MAX_ATTEMPTS:
                break
            if raw:
                messages = build_repair_messages(messages, raw, exc.message)
    raise AIError(last_error, status_code=502)


def _weak_reasons(session: Session, point_id: int | None) -> list[str]:
    if point_id is None:
        return []
    questions = session.exec(select(QuizQuestion).where(QuizQuestion.knowledge_point_id == point_id)).all()
    question_ids = [question.id for question in questions if question.id is not None]
    if not question_ids:
        return []
    answers = session.exec(select(QuizAnswer).where(QuizAnswer.question_id.in_(question_ids), QuizAnswer.is_correct == False)).all()  # noqa: E712
    reasons = []
    for answer in answers:
        text = answer.error_reason.strip()
        if text and text not in reasons:
            reasons.append(text)
    return reasons[:5]


def _active_schedules(session: Session, include_inactive: bool = False) -> list[ReviewSchedule]:
    goal_ids = _active_goal_ids(session, include_inactive=include_inactive)
    if not goal_ids:
        return []
    return list(session.exec(select(ReviewSchedule).where(ReviewSchedule.goal_id.in_(goal_ids))).all())


def _active_goal_ids(session: Session, include_inactive: bool) -> list[int]:
    goals = goal_service.list_goals(session)
    if not include_inactive:
        goals = [goal for goal in goals if goal.status == "active"]
    return [goal.id for goal in goals if goal.id is not None]


def _owned_schedule(session: Session, schedule_id: int) -> ReviewSchedule:
    schedule = session.get(ReviewSchedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="复习计划不存在")
    goal_service.get_goal(session, schedule.goal_id)
    return schedule


def _card(session: Session, schedule: ReviewSchedule, today) -> dict:
    point = session.get(KnowledgePoint, schedule.knowledge_point_id)
    assessed = point is not None and (point.mastery_level > 0 or point.status == "mastered" or schedule.last_score is not None)
    mastery = None if point is None or not assessed else point.mastery_level
    if schedule.last_score == 0:
        assessed = True
        mastery = 0 if point is None else point.mastery_level
    days_since = None
    if schedule.last_reviewed_at is not None:
        days_since = (today - schedule.last_reviewed_at.astimezone().date()).days
    overdue_days = max(0, (today - schedule.next_review_date).days)
    recent_low = 0
    if point is not None:
        events = session.exec(
            select(KnowledgeMasteryEvent).where(KnowledgeMasteryEvent.knowledge_point_id == point.id).order_by(KnowledgeMasteryEvent.created_at.desc())
        ).all()
        for event in events[:3]:
            if event.quiz_score < 60:
                recent_low += 1
            else:
                break
    risk, risk_reason = forgetting_risk(
        mastery=mastery,
        latest_score=schedule.last_score,
        days_since_quiz=days_since,
        overdue_days=overdue_days,
        recent_low_count=recent_low,
    )
    if schedule.next_review_date < today:
        queue = "overdue"
    elif schedule.next_review_date == today:
        queue = "due"
    elif schedule.next_review_date <= today + timedelta(days=3):
        queue = "upcoming"
    else:
        queue = "later"
    goal = session.get(LearningGoal, schedule.goal_id)
    return {
        "id": schedule.id,
        "goal_id": schedule.goal_id,
        "goal_title": None if goal is None else goal.title,
        "knowledge_point_id": schedule.knowledge_point_id,
        "name": "知识点" if point is None else point.name,
        "last_reviewed_at": schedule.last_reviewed_at,
        "mastery_level": mastery,
        "mastery_assessed": assessed and mastery is not None or schedule.last_score is not None,
        "status_label": "尚未评估" if point is None else status_label(point.status, bool(assessed)),
        "last_score": schedule.last_score,
        "next_review_date": schedule.next_review_date,
        "interval_days": schedule.interval_days,
        "stage_label": _stage_label(schedule.successful_passes),
        "risk": risk,
        "risk_label": RISK_LABELS[risk],
        "risk_reason": risk_reason,
        "reason": schedule.reason,
        "postpone_count": schedule.postpone_count,
        "overdue_days": overdue_days,
        "queue": queue,
        "open_quiz_id": schedule.open_quiz_id,
    }


def _summary(schedule: ReviewSchedule, point: KnowledgePoint, reason: str) -> dict:
    return {
        "schedule_id": schedule.id,
        "name": point.name,
        "interval_days": schedule.interval_days,
        "next_review_date": schedule.next_review_date,
        "reason": reason,
    }


def _prioritize(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda item: (item["overdue_days"] * -1, item["mastery_level"] if item["mastery_level"] is not None else -1))


def _completed_on(session: Session, today) -> list[ReviewRecord]:
    goal_ids = _active_goal_ids(session, include_inactive=True)
    if not goal_ids:
        return []
    point_ids = [
        point.id
        for point in session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id.in_(goal_ids))).all()
        if point.id is not None
    ]
    if not point_ids:
        return []
    records = session.exec(select(ReviewRecord).where(ReviewRecord.knowledge_point_id.in_(point_ids))).all()
    return [
        item
        for item in records
        if item.result in {"pass", "partial", "fail", "initial"} and item.reviewed_at.astimezone().date() == today
    ]


def _stage_label(passes: int) -> str:
    labels = {0: "等待第一次复习", 1: "第一次复习后", 2: "第二次复习后", 3: "第三次复习后", 4: "第四次复习后"}
    return labels.get(passes, "长期巩固")


def _points_for_user(session: Session, knowledge_id: int | None) -> list[KnowledgePoint]:
    if knowledge_id is not None:
        point = session.get(KnowledgePoint, knowledge_id)
        if point is None:
            raise HTTPException(status_code=404, detail="知识点不存在")
        goal_service.get_goal(session, point.goal_id)
        return [point]
    goal_ids = _active_goal_ids(session, include_inactive=True)
    if not goal_ids:
        return []
    return list(session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id.in_(goal_ids)).order_by(KnowledgePoint.id)).all())


def _progress(session: Session) -> dict:
    points = _points_for_user(session, None)
    improved = []
    recent = []
    weak = []
    for point in points:
        events = session.exec(
            select(KnowledgeMasteryEvent).where(KnowledgeMasteryEvent.knowledge_point_id == point.id).order_by(KnowledgeMasteryEvent.created_at)
        ).all()
        if len(events) < 2:
            if events and events[-1].new_level < 60:
                weak.append({"name": point.name, "mastery_level": events[-1].new_level})
            continue
        delta = events[-1].new_level - events[0].new_level
        recent_delta = events[-1].new_level - events[-2].new_level
        if delta > 0:
            improved.append({"name": point.name, "from_level": events[0].new_level, "to_level": events[-1].new_level, "delta": delta})
        if recent_delta > 0:
            recent.append({"name": point.name, "delta": recent_delta, "mastery_level": events[-1].new_level})
        if events[-1].new_level < 60:
            weak.append({"name": point.name, "mastery_level": events[-1].new_level})
    improved.sort(key=lambda item: item["delta"], reverse=True)
    recent.sort(key=lambda item: item["delta"], reverse=True)
    return {
        "most_improved": improved[:3],
        "recent_improved": recent[:3],
        "still_weak": weak[:3],
    }
