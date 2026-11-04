"""根据规则诊断安排训练。不调用模型，也不改掌握度、复习、练习或计划。"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.goal import LearningGoal
from app.models.knowledge import KnowledgePoint
from app.models.practice import ProblemLearningStatus
from app.models.problem import Problem, ProblemTopic, ProblemTopicLink
from app.models.recommendation import TrainingRecommendation
from app.schemas.recommendation import RecommendationStatusUpdate
from app.services import goal_service
from app.services.diagnosis_rules import diagnose
from app.services.diagnosis_service import _user

SKILLED = {"proficient", "mastered"}
PROBLEM_CATEGORIES = {"algorithm", "implementation", "boundary"}
CATEGORY_LABELS = {
    "knowledge_understanding": "知识理解",
    "algorithm": "算法思路",
    "implementation": "代码实现",
    "boundary": "边界处理",
    "forgetting": "遗忘风险",
}


def list_recommendations(session: Session, goal_id: int | None = None, status: str | None = None) -> dict:
    user = _user(session)
    if goal_id is not None:
        _owned_goal(session, user.id, goal_id)
    rows = _rows(session, user.id, goal_id, status)
    return {"recommendations": [_payload(session, row) for row in rows]}


def get_recommendation(session: Session, recommendation_id: int) -> dict:
    user = _user(session)
    row = _owned_row(session, user.id, recommendation_id)
    return _payload(session, row)


def update_status(session: Session, recommendation_id: int, payload: RecommendationStatusUpdate) -> dict:
    user = _user(session)
    row = _owned_row(session, user.id, recommendation_id)
    if row.status == payload.status:
        return _payload(session, row)
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="只能对待做建议标记完成或忽略")
    row.status = payload.status
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    goal_service.commit_or_raise(session)
    session.refresh(row)
    return _payload(session, row)


def generate(session: Session, goal_id: int | None = None) -> dict:
    user = _user(session)
    if goal_id is not None:
        goal = _owned_goal(session, user.id, goal_id)
        if goal.status != "active":
            message = "目标已暂停，不生成新的训练建议" if goal.status == "paused" else "目标已完成，不生成新的训练建议"
            budget = [{"goal_id": goal.id, "daily_minutes": goal.daily_minutes, "used_minutes": 0, "status": goal.status}]
            return _result(goal_id, message, budget, [], [], [], [])
        return _generate_active(session, user.id, [goal], shared=True)
    goals = [goal for goal in _user_goals(session, user.id) if goal.status == "active"]
    if not goals:
        return _result(None, "没有进行中的学习目标，不生成训练建议", [], [], [], [], [])
    return _generate_active(session, user.id, goals, shared=len(goals) == 1)


def _generate_active(session: Session, user_id: int, goals: list[LearningGoal], shared: bool) -> dict:
    diagnosis = diagnose(session, goals[0].id if shared else None)
    points = {row.id: row for row in _points_for(session, [goal.id for goal in goals if goal.id is not None]) if row.id is not None}
    catalog = _problem_catalog(session, user_id)
    existing = _rows(session, user_id, None, None)
    created: list[TrainingRecommendation] = []
    reused: list[TrainingRecommendation] = []
    skipped: list[dict] = []
    budgets: list[dict] = []
    if shared:
        goal = goals[0]
        candidates = _knowledge_candidates(diagnosis["knowledge_points"], points, catalog)
        candidates.extend(_topic_candidates(diagnosis["problem_topics"], catalog))
        created, reused, skipped, used = _pack(session, user_id, candidates, goal.daily_minutes, existing, goal.id, True)
        budgets.append({"goal_id": goal.id, "daily_minutes": goal.daily_minutes, "used_minutes": used, "status": goal.status})
    else:
        for goal in goals:
            rows = [row for row in diagnosis["knowledge_points"] if row["goal_id"] == goal.id]
            candidates = _knowledge_candidates(rows, points, catalog)
            goal_created, goal_reused, goal_skipped, used = _pack(session, user_id, candidates, goal.daily_minutes, existing, goal.id, False)
            created.extend(goal_created)
            reused.extend(goal_reused)
            skipped.extend(goal_skipped)
            budgets.append({"goal_id": goal.id, "daily_minutes": goal.daily_minutes, "used_minutes": used, "status": goal.status})
        shortest = min(goal.daily_minutes for goal in goals)
        topic_created, topic_reused, topic_skipped, topic_used = _pack(
            session, user_id, _topic_candidates(diagnosis["problem_topics"], catalog), shortest, existing, None, False
        )
        created.extend(topic_created)
        reused.extend(topic_reused)
        skipped.extend(topic_skipped)
        budgets.append({"goal_id": None, "daily_minutes": shortest, "used_minutes": topic_used, "status": "active"})
    if created:
        goal_service.commit_or_raise(session)
        for row in created:
            session.refresh(row)
    if created or reused:
        message = "已按每日学习时间安排训练建议"
    elif skipped:
        message = "没有新增训练建议"
    else:
        message = "当前没有已确认或初步发现的诊断，不生成针对性补救训练"
    selected = [_payload(session, row) for row in _selected(session, user_id, goals, shared)]
    return _result(goals[0].id if shared else None, message, budgets, created, reused, skipped, selected)


def _pack(
    session: Session,
    user_id: int,
    candidates: list[dict],
    daily_minutes: int,
    existing: list[TrainingRecommendation],
    pool_goal_id: int | None,
    include_unscoped: bool,
) -> tuple[list[TrainingRecommendation], list[TrainingRecommendation], list[dict], int]:
    pool = [row for row in existing if row.status == "pending" and _in_pool(row, pool_goal_id, include_unscoped)]
    remaining = daily_minutes - sum(row.estimated_minutes for row in pool)
    if remaining < 0:
        remaining = 0
    created: list[TrainingRecommendation] = []
    reused: list[TrainingRecommendation] = []
    skipped: list[dict] = []
    for candidate in _ordered(candidates):
        match = _same(existing, candidate)
        if match is not None:
            if match.status == "pending":
                reused.append(match)
            else:
                skipped.append({"title": match.title, "category": match.category, "reason": "已有相同建议，不重复生成"})
            continue
        minutes = min(candidate["estimated_minutes"], daily_minutes)
        if minutes > remaining:
            skipped.append({"title": candidate["title"], "category": candidate["category"], "reason": "超出每日学习时间，已保留更高优先级的建议"})
            continue
        row = TrainingRecommendation(
            user_id=user_id,
            diagnosis_report_id=None,
            goal_id=candidate["goal_id"],
            knowledge_point_id=candidate["knowledge_point_id"],
            problem_topic_id=candidate["problem_topic_id"],
            problem_id=candidate["problem_id"],
            category=candidate["category"],
            title=candidate["title"],
            description=candidate["description"],
            reason=candidate["reason"],
            estimated_minutes=minutes,
            priority=candidate["priority"],
            completion_criteria=candidate["completion_criteria"],
            status="pending",
        )
        session.add(row)
        created.append(row)
        existing.append(row)
        remaining -= minutes
    used = sum(row.estimated_minutes for row in pool) + sum(row.estimated_minutes for row in created)
    return created, reused, skipped, used


def _knowledge_candidates(rows: list[dict], points: dict[int, KnowledgePoint], catalog: dict) -> list[dict]:
    candidates = []
    for row in rows:
        point = points.get(row["knowledge_point_id"])
        if point is None:
            continue
        forgetting = next((item for item in row["diagnoses"] if item["category"] == "forgetting"), None)
        due = _review_due(forgetting)
        skilled = point.status in SKILLED
        if skilled and not due:
            continue
        for diagnosis in row["diagnoses"]:
            if diagnosis["status"] == "insufficient_data":
                continue
            if skilled and diagnosis["category"] != "forgetting":
                continue
            topic_ids = [topic["id"] for topic in diagnosis["problem_topics"]]
            if not topic_ids:
                topic_ids = [topic["id"] for topic in row["linked_topics"]]
            candidates.append(_candidate(diagnosis, topic_ids, catalog, point.goal_id))
    return candidates


def _topic_candidates(rows: list[dict], catalog: dict) -> list[dict]:
    candidates = []
    for row in rows:
        for diagnosis in row["diagnoses"]:
            if diagnosis["status"] == "insufficient_data":
                continue
            candidates.append(_candidate(diagnosis, [row["problem_topic_id"]], catalog, None))
    return candidates


def _candidate(diagnosis: dict, topic_ids: list[int], catalog: dict, goal_id: int | None) -> dict:
    category = diagnosis["category"]
    if category == "forgetting":
        problem, topic_id = None, None
    else:
        problem, topic_id = _choose_problem(topic_ids, catalog)
    has_problem = problem is not None
    subject = diagnosis["knowledge_point_name"] or (diagnosis["problem_topics"][0]["name"] if diagnosis["problem_topics"] else "未命名")
    if category == "forgetting":
        title = f"复习：{subject}"
        description = f"优先复习「{subject}」。这次只安排复习，不会自动创建检测或改动复习间隔。"
        criteria = "完成该知识点的一轮复习。系统不会自动写入复习记录。"
    elif category == "knowledge_understanding":
        title = f"重学：{subject}"
        description = f"按最近的连续低分，重新学习「{subject}」。"
        if has_problem:
            description += f" 可以配合已有题目 #{problem.id} {problem.title}。"
        elif topic_ids:
            description += " 题库暂无合适题目。"
        else:
            description += " 当前没有已确认关联的题目。"
        criteria = "重新学习后完成一次该知识点的检测。系统不会自动创建检测。"
    else:
        label = CATEGORY_LABELS[category]
        title = f"{label}：{problem.title if has_problem else subject}"
        if has_problem:
            description = f"针对{label}练习已有题目 #{problem.id} {problem.title}。"
            criteria = "提交这道题并完成本地判题。自评完成不算正式通过。"
        else:
            description = f"针对{label}需要练习，但题库暂无合适题目。"
            criteria = "先加入一道真实题目后再练习。不能用编造的题目代替。"
    if category == "forgetting":
        minutes = 15
    elif category == "knowledge_understanding":
        minutes = 15
    elif has_problem:
        minutes = 20
    else:
        minutes = 10
    return {
        "goal_id": goal_id,
        "knowledge_point_id": diagnosis["knowledge_point_id"],
        "problem_topic_id": topic_id,
        "problem_id": None if problem is None else problem.id,
        "category": category,
        "title": _clip(title, 120),
        "description": _clip(description, 2000),
        "reason": _clip(_reason_text(diagnosis), 2000),
        "estimated_minutes": minutes,
        "priority": _priority(diagnosis["status"], category),
        "completion_criteria": _clip(criteria, 500),
        "evidence_count": diagnosis["evidence_count"],
        "sort_name": subject,
    }


def _choose_problem(topic_ids: list[int], catalog: dict) -> tuple[Problem | None, int | None]:
    chosen: tuple[int, int, Problem] | None = None
    for topic_id in topic_ids:
        for problem in catalog["by_topic"].get(topic_id, []):
            if catalog["statuses"].get(problem.id) == "accepted":
                continue
            if chosen is None or (problem.id or 0) < chosen[0]:
                chosen = (problem.id or 0, topic_id, problem)
    if chosen is None:
        return None, topic_ids[0] if topic_ids else None
    return chosen[2], chosen[1]


def _reason_text(diagnosis: dict) -> str:
    parts = [diagnosis["reason"], f"证据 {diagnosis['evidence_count']} 条"]
    for item in diagnosis["evidence"]:
        if not item.get("counts"):
            continue
        if item["type"] == "quiz_score":
            parts.append(f"检测 {item['score']} 分")
        elif item["type"] == "wrong_reason":
            parts.append(f"错题原因 {item['reason_type']}，题目 {item['problem_title']}")
        elif item["type"] == "judge_result":
            parts.append(f"判题 {item['status']}，题目 {item['problem_title']}")
        elif item["type"] == "sample_passed_other_failed":
            parts.append(f"样例通过但其他用例未通过，题目 {item['problem_title']}")
        elif item["type"] == "mastery_history":
            parts.append(f"掌握度 {item['mastery_level']}，历史高点 {item['historical_high']}")
        elif item["type"] == "review_schedule":
            state = "逾期" if item["overdue"] else "到期"
            parts.append(f"复习{state} {item['next_review_date']}")
    return "；".join(parts)


def _priority(status: str, category: str) -> int:
    if status == "confirmed" and category == "forgetting":
        return 1
    if status == "confirmed":
        return 2
    if category == "forgetting":
        return 3
    return 4


def _ordered(candidates: list[dict]) -> list[dict]:
    return sorted(candidates, key=lambda item: (item["priority"], -item["evidence_count"], item["sort_name"], item["category"]))


def _review_due(diagnosis: dict | None) -> bool:
    if diagnosis is None:
        return False
    for item in diagnosis["evidence"]:
        if item["type"] == "review_schedule" and (item["due"] or item["overdue"]):
            return True
    return False


def _same(existing: list[TrainingRecommendation], candidate: dict) -> TrainingRecommendation | None:
    for row in existing:
        if (
            row.goal_id == candidate["goal_id"]
            and row.knowledge_point_id == candidate["knowledge_point_id"]
            and row.problem_topic_id == candidate["problem_topic_id"]
            and row.category == candidate["category"]
        ):
            return row
    return None


def _in_pool(row: TrainingRecommendation, pool_goal_id: int | None, include_unscoped: bool) -> bool:
    if pool_goal_id is None:
        return row.goal_id is None
    if row.goal_id == pool_goal_id:
        return True
    return include_unscoped and row.goal_id is None


def _selected(session: Session, user_id: int, goals: list[LearningGoal], shared: bool) -> list[TrainingRecommendation]:
    goal_ids = {goal.id for goal in goals}
    rows = []
    for row in _rows(session, user_id, None, "pending"):
        if shared or len(goals) == 1:
            if row.goal_id in goal_ids or row.goal_id is None:
                rows.append(row)
        elif row.goal_id in goal_ids or row.goal_id is None:
            rows.append(row)
    return rows


def _problem_catalog(session: Session, user_id: int) -> dict:
    problems = list(session.exec(select(Problem).where(Problem.user_id == user_id).order_by(Problem.id)).all())
    problem_ids = [problem.id for problem in problems if problem.id is not None]
    by_topic: dict[int, list[Problem]] = {}
    if problem_ids:
        links = session.exec(select(ProblemTopicLink).where(ProblemTopicLink.problem_id.in_(problem_ids)).order_by(ProblemTopicLink.id)).all()
        problems_by_id = {problem.id: problem for problem in problems}
        for link in links:
            problem = problems_by_id.get(link.problem_id)
            if problem is not None:
                by_topic.setdefault(link.topic_id, []).append(problem)
    statuses = {
        row.problem_id: row.status
        for row in session.exec(select(ProblemLearningStatus).where(ProblemLearningStatus.user_id == user_id)).all()
        if row.problem_id in set(problem_ids)
    }
    return {"by_topic": by_topic, "statuses": statuses}


def _points_for(session: Session, goal_ids: list[int]) -> list[KnowledgePoint]:
    if not goal_ids:
        return []
    return list(session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id.in_(goal_ids))).all())


def _rows(session: Session, user_id: int, goal_id: int | None, status: str | None) -> list[TrainingRecommendation]:
    statement = select(TrainingRecommendation).where(TrainingRecommendation.user_id == user_id)
    if goal_id is not None:
        statement = statement.where(TrainingRecommendation.goal_id == goal_id)
    if status is not None:
        statement = statement.where(TrainingRecommendation.status == status)
    statement = statement.order_by(TrainingRecommendation.priority, TrainingRecommendation.id)
    return list(session.exec(statement).all())


def _owned_goal(session: Session, user_id: int | None, goal_id: int) -> LearningGoal:
    goal = session.get(LearningGoal, goal_id)
    if goal is None or goal.user_id != user_id:
        raise HTTPException(status_code=404, detail="学习目标不存在")
    return goal


def _owned_row(session: Session, user_id: int | None, recommendation_id: int) -> TrainingRecommendation:
    row = session.get(TrainingRecommendation, recommendation_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status_code=404, detail="训练建议不存在")
    return row


def _user_goals(session: Session, user_id: int | None) -> list[LearningGoal]:
    return list(session.exec(select(LearningGoal).where(LearningGoal.user_id == user_id).order_by(LearningGoal.id)).all())


def _payload(session: Session, row: TrainingRecommendation) -> dict:
    point = None if row.knowledge_point_id is None else session.get(KnowledgePoint, row.knowledge_point_id)
    topic = None if row.problem_topic_id is None else session.get(ProblemTopic, row.problem_topic_id)
    problem = None if row.problem_id is None else session.get(Problem, row.problem_id)
    return {
        "id": row.id,
        "user_id": row.user_id,
        "diagnosis_report_id": row.diagnosis_report_id,
        "goal_id": row.goal_id,
        "knowledge_point_id": row.knowledge_point_id,
        "knowledge_point_name": None if point is None else point.name,
        "problem_topic_id": row.problem_topic_id,
        "problem_topic_name": None if topic is None else topic.name,
        "problem_id": row.problem_id,
        "problem_title": None if problem is None else problem.title,
        "category": row.category,
        "title": row.title,
        "description": row.description,
        "reason": row.reason,
        "estimated_minutes": row.estimated_minutes,
        "priority": row.priority,
        "completion_criteria": row.completion_criteria,
        "status": row.status,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _result(
    goal_id: int | None,
    message: str,
    budgets: list[dict],
    created: list[TrainingRecommendation],
    reused: list[TrainingRecommendation],
    skipped: list[dict],
    selected: list[dict],
) -> dict:
    return {
        "goal_id": goal_id,
        "message": message,
        "budgets": budgets,
        "created_count": len(created),
        "created_ids": [row.id for row in created],
        "reused_ids": [row.id for row in reused],
        "skipped": skipped,
        "recommendations": selected,
    }


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
