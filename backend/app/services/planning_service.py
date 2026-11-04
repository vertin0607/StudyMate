"""读取或保存每日计划。模型输出通过校验后才会入库。"""

import json
import logging
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.goal import LearningGoal
from app.models.knowledge import KnowledgePoint
from app.models.plan import PlanRevision, StudyPlan, StudyTask
from app.services import goal_service
from app.services.ai.deepseek_client import complete_json
from app.services.ai.errors import AIError
from app.services.ai.prompt_builder import MAX_ATTEMPTS, build_messages, build_repair_messages
from app.services.ai.response_parser import PlanDraft, parse_plan

logger = logging.getLogger(__name__)


def server_today() -> date:
    """计划日期使用服务器本地日期，不让模型自己决定。"""
    return datetime.now().astimezone().date()


def get_today(session: Session, goal_id: int, generate: bool) -> dict:
    goal = goal_service.get_goal(session, goal_id)
    plan_date = server_today()
    plan = _current_plan(session, goal.id, plan_date)
    if plan is None and generate:
        if goal.status != "active":
            raise HTTPException(status_code=400, detail="只有进行中的目标才能生成新计划")
        plan = create_plan(session, goal, plan_date, "")
    return _today_payload(goal, plan_date, plan, session)


def create_for_goal(session: Session, goal_id: int) -> dict:
    goal = goal_service.get_goal(session, goal_id)
    if goal.status != "active":
        raise HTTPException(status_code=400, detail="只有进行中的目标才能生成新计划")
    plan_date = server_today()
    if _current_plan(session, goal.id, plan_date) is not None:
        raise HTTPException(status_code=409, detail="今天已经有计划。刷新页面即可查看，不需要再次生成")
    plan = create_plan(session, goal, plan_date, "")
    return _today_payload(goal, plan_date, plan, session)


def regenerate(session: Session, plan_id: int, instruction: str) -> dict:
    current = _get_plan(session, plan_id)
    if current.status != "active":
        raise HTTPException(status_code=409, detail="只能在当前计划上重新生成")
    goal = goal_service.get_goal(session, current.goal_id)
    if goal.status != "active":
        raise HTTPException(status_code=400, detail="只有进行中的目标才能调整计划")
    reason = instruction or "用户要求重新生成今日计划"
    plan = create_plan(session, goal, current.plan_date, reason, previous=current)
    return _today_payload(goal, current.plan_date, plan, session)


def get_plan_detail(session: Session, plan_id: int) -> dict:
    plan = _get_plan(session, plan_id)
    goal = goal_service.get_goal(session, plan.goal_id)
    return _plan_dict(session, plan, goal)


def get_history(session: Session, plan_id: int) -> dict:
    plan = _get_plan(session, plan_id)
    versions = session.exec(
        select(StudyPlan)
        .where(StudyPlan.goal_id == plan.goal_id, StudyPlan.plan_date == plan.plan_date)
        .order_by(StudyPlan.version.desc())
    ).all()
    version_ids = [item.id for item in versions if item.id is not None]
    revisions = []
    if version_ids:
        revisions = session.exec(
            select(PlanRevision)
            .where(PlanRevision.plan_id.in_(version_ids))
            .order_by(PlanRevision.created_at.desc())
        ).all()
    return {
        "versions": [
            {
                "id": item.id,
                "version": item.version,
                "title": item.title,
                "status": item.status,
                "total_minutes": item.total_minutes,
                "created_at": item.created_at,
            }
            for item in versions
        ],
        "revisions": [
            {
                "id": item.id,
                "plan_id": item.plan_id,
                "reason": item.reason,
                "created_at": item.created_at,
            }
            for item in revisions
        ],
    }


def update_task_status(session: Session, task_id: int, status: str) -> dict:
    task = session.get(StudyTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="学习任务不存在")
    plan = session.get(StudyPlan, task.plan_id)
    if plan is None or goal_service.get_goal(session, plan.goal_id) is None:
        raise HTTPException(status_code=404, detail="学习任务不存在")
    if plan.status != "active":
        raise HTTPException(status_code=409, detail="历史计划不能修改任务状态")

    now = datetime.now(timezone.utc)
    task.status = status
    task.updated_at = now
    task.completed_at = now if status in {"completed", "skipped"} else None
    _touch_knowledge_progress(session, task)
    session.add(task)
    goal_service.commit_or_raise(session)
    session.refresh(task)
    point = session.get(KnowledgePoint, task.knowledge_point_id) if task.knowledge_point_id else None
    return _task_dict(task, point)


def dashboard(session: Session) -> dict:
    """只读取已保存的计划，不调用模型。"""
    user = goal_service.ensure_local_user(session)
    goals = list(
        session.exec(
            select(LearningGoal)
            .where(LearningGoal.user_id == user.id)
            .order_by(LearningGoal.updated_at.desc())
        ).all()
    )
    recent = next((item for item in goals if item.status == "active"), goals[0] if goals else None)
    plan_date = server_today()
    payload = {
        "plan_date": plan_date,
        "recent_goal": None
        if recent is None
        else {"id": recent.id, "title": recent.title, "status": recent.status},
        "has_plan": False,
        "plan_id": None,
        "plan_title": None,
        "plan_version": None,
        "total_tasks": 0,
        "completed_tasks": 0,
        "progress": 0,
        "plan_state": "none",
    }
    if recent is None or recent.id is None:
        return payload
    plan = _current_plan(session, recent.id, plan_date)
    if plan is None:
        return payload
    tasks = _tasks_for(session, plan.id)
    completed = sum(1 for task in tasks if task.status == "completed")
    total = len(tasks)
    payload.update(
        {
            "has_plan": True,
            "plan_id": plan.id,
            "plan_title": plan.title,
            "plan_version": plan.version,
            "total_tasks": total,
            "completed_tasks": completed,
            "progress": round(completed / total, 2) if total else 0,
            "plan_state": _plan_state(tasks),
        }
    )
    return payload


def create_plan(
    session: Session,
    goal: LearningGoal,
    plan_date: date,
    instruction: str,
    previous: StudyPlan | None = None,
) -> StudyPlan:
    draft = _request_plan(session, goal, plan_date, instruction, previous)
    now = datetime.now(timezone.utc)
    old_snapshot = _snapshot(session, previous) if previous is not None else None
    if previous is not None:
        previous.status = "archived"
        previous.updated_at = now
        session.add(previous)
        session.flush()

    plan = StudyPlan(
        goal_id=goal.id,
        plan_date=plan_date,
        title=draft.title,
        description=draft.description,
        total_minutes=draft.total_minutes,
        status="active",
        version=(previous.version + 1) if previous is not None else 1,
        created_at=now,
        updated_at=now,
    )
    session.add(plan)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="今天已经有计划，没有重复创建") from exc

    for index, item in enumerate(draft.tasks):
        point = _ensure_point(session, goal.id, item.knowledge_point, item.description, now)
        session.add(
            StudyTask(
                plan_id=plan.id,
                knowledge_point_id=point.id,
                title=item.title,
                description=item.description,
                task_type=item.task_type,
                estimated_minutes=item.estimated_minutes,
                sort_order=index,
                status="pending",
                created_at=now,
                updated_at=now,
            )
        )
    session.flush()
    if previous is not None and old_snapshot is not None:
        session.add(
            PlanRevision(
                plan_id=plan.id,
                old_content=old_snapshot,
                new_content=_snapshot(session, plan),
                reason=instruction[:500],
                created_at=now,
            )
        )
    goal_service.commit_or_raise(session)
    session.refresh(plan)
    logger.info("已保存学习计划 %s，版本 %s", plan.id, plan.version)
    return plan


def _request_plan(
    session: Session,
    goal: LearningGoal,
    plan_date: date,
    instruction: str,
    previous: StudyPlan | None,
) -> PlanDraft:
    context = _context(session, goal)
    messages = build_messages(
        goal,
        plan_date,
        context,
        instruction,
        _snapshot_dict(session, previous) if previous is not None else None,
    )
    raw = ""
    last_error = "计划内容未通过校验"
    for attempt in range(MAX_ATTEMPTS):
        raw = complete_json(messages)
        try:
            return parse_plan(raw, goal.daily_minutes, set(context["mastered_names"]))
        except AIError as exc:
            last_error = exc.message
            if attempt + 1 >= MAX_ATTEMPTS:
                break
            messages = build_repair_messages(messages, raw, exc.message)
    raise AIError(last_error, status_code=502)


def _context(session: Session, goal: LearningGoal) -> dict:
    points = session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id == goal.id)).all()
    recent = session.exec(
        select(StudyPlan)
        .where(StudyPlan.goal_id == goal.id)
        .order_by(StudyPlan.plan_date.desc(), StudyPlan.version.desc())
        .limit(5)
    ).all()
    point_ids = [point.id for point in points if point.id is not None]
    events = _mastery_events(session, point_ids)
    schedules = _review_schedules(session, point_ids)
    today = datetime.now().astimezone().date()
    return {
        "knowledge_points": [
            _point_context(point, events.get(point.id, []), schedules.get(point.id), today) for point in points
        ],
        "mastered_names": [point.name for point in points if point.status == "mastered"],
        "recent_plans": [_snapshot_dict(session, plan) for plan in recent],
        "completed_task_titles": _completed_task_titles(session, goal.id),
        "quiz_results": _recent_quizzes(session, goal.id),
        "due_reviews": _due_reviews(session, goal.id),
    }


def _point_context(point: KnowledgePoint, events: list, schedule: object, today: date) -> dict:
    scores = [event.quiz_score for event in events]
    assessed = point.mastery_level > 0 or point.status == "mastered"
    streak = _low_streak(scores)
    review = None
    if schedule is not None:
        review = {
            "next_review_date": schedule.next_review_date.isoformat(),
            "due": schedule.next_review_date == today,
            "overdue": schedule.next_review_date < today,
            "last_score": schedule.last_score,
        }
    return {
        "name": point.name,
        "status": point.status,
        "mastery_level": point.mastery_level,
        "mastery_assessed": assessed,
        "recent_scores": scores[-5:],
        "consecutive_low_scores": streak,
        "learning_band": _learning_band(assessed, point.mastery_level, streak),
        "needs_prerequisite": streak >= 2,
        "review": review,
    }


def _learning_band(assessed: bool, mastery: int, streak: int) -> str:
    if streak >= 2 or not assessed or mastery < 60:
        return "foundation"
    if mastery < 85:
        return "principle"
    return "application"


def _low_streak(scores: list[int]) -> int:
    streak = 0
    for score in reversed(scores):
        if score >= 60:
            break
        streak += 1
    return streak


def _mastery_events(session: Session, point_ids: list[int]) -> dict:
    from app.models.quiz import KnowledgeMasteryEvent

    grouped: dict[int, list] = {point_id: [] for point_id in point_ids}
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


def _review_schedules(session: Session, point_ids: list[int]) -> dict:
    from app.models.review import ReviewSchedule

    if not point_ids:
        return {}
    rows = session.exec(select(ReviewSchedule).where(ReviewSchedule.knowledge_point_id.in_(point_ids))).all()
    return {row.knowledge_point_id: row for row in rows}


def _completed_task_titles(session: Session, goal_id: int | None) -> list[str]:
    if goal_id is None:
        return []
    rows = session.exec(
        select(StudyTask.title)
        .join(StudyPlan, StudyPlan.id == StudyTask.plan_id)
        .where(StudyPlan.goal_id == goal_id, StudyTask.status == "completed")
        .order_by(StudyTask.completed_at.desc())
        .limit(8)
    ).all()
    return [row if isinstance(row, str) else row[0] for row in rows]


def _due_reviews(session: Session, goal_id: int | None) -> list[dict]:
    if goal_id is None:
        return []
    from app.services.review_service import due_for_planning

    return due_for_planning(session, goal_id)


def _recent_quizzes(session: Session, goal_id: int | None) -> list[dict]:
    if goal_id is None:
        return []
    from app.services.quiz_service import recent_quiz_results

    return recent_quiz_results(session, goal_id)


def _ensure_point(session: Session, goal_id: int, name: str, description: str, now: datetime) -> KnowledgePoint:
    point = session.exec(
        select(KnowledgePoint).where(KnowledgePoint.goal_id == goal_id, KnowledgePoint.name == name)
    ).first()
    if point is not None:
        return point
    point = KnowledgePoint(
        goal_id=goal_id,
        name=name,
        description=description,
        difficulty="unknown",
        status="not_started",
        mastery_level=0,
        created_at=now,
        updated_at=now,
    )
    session.add(point)
    session.flush()
    return point


def _touch_knowledge_progress(session: Session, task: StudyTask) -> None:
    """任务状态只反映学习进度。没有测试成绩时不提高掌握分。"""
    if task.knowledge_point_id is None:
        return
    point = session.get(KnowledgePoint, task.knowledge_point_id)
    if point is None or point.status == "mastered":
        return
    if task.status == "in_progress" and point.status == "not_started":
        point.status = "learning"
    elif task.status == "completed" and task.task_type == "review" and point.status in {"not_started", "learning"}:
        point.status = "reviewing"
    elif task.status == "completed" and point.status == "not_started":
        point.status = "learning"
    else:
        return
    point.updated_at = datetime.now(timezone.utc)
    session.add(point)


def _current_plan(session: Session, goal_id: int, plan_date: date) -> StudyPlan | None:
    return session.exec(
        select(StudyPlan).where(
            StudyPlan.goal_id == goal_id,
            StudyPlan.plan_date == plan_date,
            StudyPlan.status == "active",
        )
    ).first()


def _get_plan(session: Session, plan_id: int) -> StudyPlan:
    plan = session.get(StudyPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="学习计划不存在")
    goal_service.get_goal(session, plan.goal_id)
    return plan


def _tasks_for(session: Session, plan_id: int | None) -> list[StudyTask]:
    if plan_id is None:
        return []
    return list(
        session.exec(select(StudyTask).where(StudyTask.plan_id == plan_id).order_by(StudyTask.sort_order)).all()
    )


def _today_payload(goal: LearningGoal, plan_date: date, plan: StudyPlan | None, session: Session) -> dict:
    return {
        "goal_id": goal.id,
        "goal_title": goal.title,
        "goal_status": goal.status,
        "daily_minutes": goal.daily_minutes,
        "plan_date": plan_date,
        "server_time": datetime.now().astimezone(),
        "plan": None if plan is None else _plan_dict(session, plan, goal),
    }


def _plan_dict(session: Session, plan: StudyPlan, goal: LearningGoal) -> dict:
    tasks = _tasks_for(session, plan.id)
    points = {
        point.id: point
        for point in session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id == goal.id)).all()
    }
    return {
        "id": plan.id,
        "goal_id": plan.goal_id,
        "plan_date": plan.plan_date,
        "title": plan.title,
        "description": plan.description,
        "total_minutes": plan.total_minutes,
        "status": plan.status,
        "version": plan.version,
        "tasks": [_task_dict(task, points.get(task.knowledge_point_id)) for task in tasks],
    }


def _task_dict(task: StudyTask, point: KnowledgePoint | None) -> dict:
    assessed = bool(point and (point.mastery_level > 0 or point.status == "mastered"))
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "task_type": task.task_type,
        "estimated_minutes": task.estimated_minutes,
        "sort_order": task.sort_order,
        "status": task.status,
        "knowledge_point_name": None if point is None else point.name,
        "knowledge_status": None if point is None else point.status,
        "mastery_level": None if point is None or not assessed else point.mastery_level,
        "mastery_assessed": assessed,
        "completed_at": task.completed_at,
    }


def _plan_state(tasks: list[StudyTask]) -> str:
    if not tasks or all(task.status == "pending" for task in tasks):
        return "not_started"
    if all(task.status in {"completed", "skipped"} for task in tasks):
        return "completed"
    return "in_progress"


def _snapshot(session: Session, plan: StudyPlan | None) -> str:
    return json.dumps(_snapshot_dict(session, plan), ensure_ascii=False)


def _snapshot_dict(session: Session, plan: StudyPlan | None) -> dict | None:
    if plan is None:
        return None
    tasks = _tasks_for(session, plan.id)
    return {
        "title": plan.title,
        "description": plan.description,
        "total_minutes": plan.total_minutes,
        "version": plan.version,
        "tasks": [
            {
                "title": task.title,
                "description": task.description,
                "task_type": task.task_type,
                "estimated_minutes": task.estimated_minutes,
                "status": task.status,
            }
            for task in tasks
        ],
    }
