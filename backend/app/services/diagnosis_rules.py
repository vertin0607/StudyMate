"""按已有记录判断薄弱点。只读，不写库，不调用模型。"""

from datetime import datetime

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.goal import LearningGoal
from app.models.judge import ProblemJudgeCaseResult, ProblemJudgeResult
from app.models.practice import ProblemLearningStatus, ProblemPracticeRecord, ProblemWrongRecord
from app.models.problem import Problem, ProblemTestCase, ProblemTopic, ProblemTopicLink
from app.models.quiz import KnowledgeMasteryEvent
from app.models.submission import ProblemSubmission
from app.models.topic_link import TopicKnowledgeLink
from app.services.diagnosis_service import snapshot

CATEGORIES = (
    "knowledge_understanding",
    "algorithm",
    "implementation",
    "boundary",
    "forgetting",
)
PROBLEM_CATEGORIES = ("algorithm", "implementation", "boundary")
EXCLUDED_JUDGE = {"compile_error", "runtime_error", "time_limit_exceeded", "system_error"}


def diagnose(session: Session, goal_id: int | None = None) -> dict:
    if goal_id is not None:
        _owned_goal(session, goal_id)
    source = snapshot(session)
    points = list(source["knowledge"]["points"])
    if goal_id is not None:
        points = [point for point in points if point["goal_id"] == goal_id]
    point_ids = {point["id"] for point in points}
    user_id = _user_id(session)
    events = _events(session, list(point_ids))
    all_links = _user_links(session, user_id)
    links = [link for link in all_links if link.knowledge_point_id in point_ids]
    topics = _topics(session, user_id)
    problems = _problems(session, user_id)
    facts = _facts(session, user_id, problems)
    topic_problems = _topic_problems(session, [problem.id for problem in problems])
    linked_topic_ids = {link.problem_topic_id for link in all_links}
    topics_by_point: dict[int, list[dict]] = {point_id: [] for point_id in point_ids}
    for link in links:
        topic = topics.get(link.problem_topic_id)
        if topic is None:
            continue
        topics_by_point.setdefault(link.knowledge_point_id, []).append(_topic_ref(topic))

    knowledge_rows = []
    flat: list[dict] = []
    for point in points:
        linked = topics_by_point.get(point["id"], [])
        diagnoses = [
            _knowledge_diagnosis(point, events.get(point["id"], [])),
            _forgetting_diagnosis(point, events.get(point["id"], [])),
        ]
        if linked:
            problem_ids = _problems_for_topics(linked, topic_problems)
            diagnoses.extend(_problem_diagnoses(point, linked, problem_ids, facts))
        flat.extend(diagnoses)
        knowledge_rows.append(
            {
                "knowledge_point_id": point["id"],
                "name": point["name"],
                "goal_id": point["goal_id"],
                "linked_topics": linked,
                "diagnoses": diagnoses,
            }
        )

    topic_rows = []
    for topic_id, topic in topics.items():
        if topic_id in linked_topic_ids:
            continue
        problem_ids = topic_problems.get(topic_id, [])
        if not problem_ids:
            continue
        diagnoses = _problem_diagnoses(None, [_topic_ref(topic)], problem_ids, facts)
        flat.extend(diagnoses)
        topic_rows.append(
            {
                "problem_topic_id": topic.id,
                "name": topic.name,
                "topic_category": topic.category,
                "diagnoses": diagnoses,
            }
        )
    return _payload(goal_id, flat, knowledge_rows, topic_rows, links, topics, points)


def _owned_goal(session: Session, goal_id: int) -> None:
    from app.services.diagnosis_service import _user

    user = _user(session)
    goal = session.get(LearningGoal, goal_id)
    if goal is None or goal.user_id != user.id:
        raise HTTPException(status_code=404, detail="学习目标不存在")


def _user_id(session: Session) -> int:
    from app.services.diagnosis_service import _user

    user = _user(session)
    if user.id is None:
        raise HTTPException(status_code=404, detail="学习目标不存在")
    return user.id


def _payload(goal_id: int | None, flat: list[dict], knowledge_rows: list[dict], topic_rows: list[dict], links: list[TopicKnowledgeLink], topics: dict[int, ProblemTopic], points: list[dict]) -> dict:
    point_names = {point["id"]: point["name"] for point in points}
    point_goals = {point["id"]: point["goal_id"] for point in points}
    grouped = {category: [] for category in CATEGORIES}
    counts = {"confirmed": 0, "suspected": 0, "insufficient_data": 0}
    for item in flat:
        grouped[item["category"]].append(item)
        counts[item["status"]] += 1
    return {
        "goal_id": goal_id,
        "summary": {"total": len(flat), **counts},
        "by_category": grouped,
        "knowledge_points": knowledge_rows,
        "problem_topics": topic_rows,
        "links": [
            {
                "id": link.id,
                "problem_topic_id": link.problem_topic_id,
                "problem_topic_name": "" if topics.get(link.problem_topic_id) is None else topics[link.problem_topic_id].name,
                "knowledge_point_id": link.knowledge_point_id,
                "knowledge_point_name": point_names.get(link.knowledge_point_id, ""),
                "goal_id": point_goals.get(link.knowledge_point_id),
            }
            for link in links
        ],
    }


def _knowledge_diagnosis(point: dict, events: list[KnowledgeMasteryEvent]) -> dict:
    scores = [event.quiz_score for event in events]
    streak = _low_streak(scores)
    evidence = []
    for index, event in enumerate(events):
        in_streak = streak > 0 and index >= len(events) - streak
        evidence.append(
            {
                "type": "quiz_score",
                "knowledge_point_id": point["id"],
                "score": event.quiz_score,
                "at": _iso(event.created_at),
                "below_60": event.quiz_score < 60,
                "in_current_streak": in_streak,
                "counts": in_streak,
            }
        )
    if streak >= 2:
        status = "confirmed"
        reason = f"按检测时间排序后，最近连续 {streak} 次低于 60 分。"
    elif streak == 1:
        status = "suspected"
        reason = "按检测时间排序后，最近只有连续 1 次低于 60 分，还不能确认。"
    elif scores:
        status = "insufficient_data"
        reason = "最近连续低于 60 分的次数是 0。出现 60 分及以上后，连续次数已重新计算。"
    else:
        status = "insufficient_data"
        reason = "还没有检测记录，不能判断知识理解是否不足。"
    return _item("knowledge_understanding", status, point, [], streak, evidence, reason)


def _forgetting_diagnosis(point: dict, events: list[KnowledgeMasteryEvent]) -> dict:
    past: list[int] = []
    for index, event in enumerate(events):
        if event.previous_level is not None:
            past.append(event.previous_level)
        if index < len(events) - 1:
            past.append(event.new_level)
    levels = [event.new_level for event in events]
    if events and events[-1].previous_level is not None:
        levels.append(events[-1].previous_level)
    historical_high = None if not levels and not past else max([*past, *levels])
    current = point["mastery_level"]
    if current is None and events:
        current = events[-1].new_level
    drop = bool(past) and current is not None and historical_high is not None and current < historical_high
    review = point["review"]
    due = bool(review and review["due"])
    overdue = bool(review and review["overdue"])
    evidence = [
        {
            "type": "mastery_history",
            "mastery_level": point["mastery_level"],
            "historical_high": historical_high,
            "mastery_drop": drop,
            "has_historical_evidence": bool(past),
            "scores": [{"score": event.quiz_score, "mastery": event.new_level, "at": _iso(event.created_at)} for event in events],
            "counts": drop,
        },
        {
            "type": "review_schedule",
            "next_review_date": None if review is None else review["next_review_date"],
            "due": due,
            "overdue": overdue,
            "counts": overdue or due,
        },
    ]
    if drop or overdue:
        status = "confirmed"
    elif due:
        status = "suspected"
    else:
        status = "insufficient_data"
    reason = _forgetting_reason(drop, due, overdue, current, historical_high, bool(past), review)
    return _item("forgetting", status, point, [], sum(1 for item in evidence if item["counts"]), evidence, reason)


def _forgetting_reason(drop: bool, due: bool, overdue: bool, current: int | None, historical_high: int | None, has_past: bool, review: dict | None) -> str:
    parts = []
    if drop:
        parts.append(f"当前掌握度 {current} 低于历史高点 {historical_high}")
    elif not has_past:
        parts.append("没有更早的检测成绩或掌握度记录，不能把当前掌握度直接当成遗忘")
    if overdue and review is not None:
        parts.append(f"复习已逾期，日期是 {review['next_review_date']}")
    elif due and review is not None:
        parts.append(f"复习今天到期，尚未逾期，日期是 {review['next_review_date']}")
    elif review is not None:
        parts.append(f"下次复习日期是 {review['next_review_date']}，还没到期")
    else:
        parts.append("还没有复习计划")
    if not parts:
        return "没有掌握度下降或逾期复习的证据。"
    return "。".join(parts) + "。"


def _problem_diagnoses(point: dict | None, topics: list[dict], problem_ids: list[int], facts: dict[int, dict]) -> list[dict]:
    selected = [facts[problem_id] for problem_id in problem_ids if problem_id in facts]
    return [
        _algorithm_diagnosis(point, topics, selected),
        _implementation_diagnosis(point, topics, selected),
        _boundary_diagnosis(point, topics, selected),
    ]


def _algorithm_diagnosis(point: dict | None, topics: list[dict], facts: list[dict]) -> dict:
    evidence = []
    reason_count = 0
    wrong_answers: list[tuple[dict, ProblemJudgeResult]] = []
    for fact in facts:
        evidence.extend(_common_exclusions(fact))
        wrong = fact["wrong"]
        if wrong is not None and wrong.reason_type == "algorithm":
            reason_count += 1
            evidence.append(_reason_evidence(fact, wrong, True))
        elif wrong is not None:
            evidence.append(_reason_evidence(fact, wrong, False))
        for judge in fact["judges"]:
            if judge.status == "wrong_answer":
                wrong_answers.append((fact, judge))
            elif judge.status in {"compile_error", "system_error", "accepted"}:
                evidence.append(_judge_evidence(fact, judge, False, _judge_note(judge.status)))
    wrong_answer_count = len(wrong_answers)
    wa_counts = wrong_answer_count >= 2
    for fact, judge in wrong_answers:
        note = "答案错误只作为算法问题的辅助证据，不能单独确认" if wa_counts else "单次答案错误不能形成算法结论"
        evidence.append(_judge_evidence(fact, judge, wa_counts, note))
    if reason_count >= 2:
        status = "confirmed"
        reason = f"有 {reason_count} 次错题原因是算法。"
    elif reason_count == 1:
        status = "suspected"
        reason = "只有 1 次错题原因是算法，先记为初步发现。"
    elif wrong_answer_count >= 2:
        status = "suspected"
        reason = f"没有算法类错题原因。排除编译错误和系统错误后有 {wrong_answer_count} 次答案错误，只能作为辅助证据。"
    else:
        status = "insufficient_data"
        reason = "还没有足够的算法错题记录。编译错误、系统异常、自评完成和未判题都不计入。"
    evidence_count = sum(1 for item in evidence if item["counts"])
    return _item("algorithm", status, point, topics, evidence_count, evidence, reason)


def _implementation_diagnosis(point: dict | None, topics: list[dict], facts: list[dict]) -> dict:
    evidence = []
    compile_count = 0
    reason_count = 0
    for fact in facts:
        evidence.extend(_common_exclusions(fact))
        wrong = fact["wrong"]
        counts = wrong is not None and wrong.reason_type in {"implementation", "syntax"}
        if wrong is not None:
            if counts:
                reason_count += 1
            evidence.append(_reason_evidence(fact, wrong, counts))
        for judge in fact["judges"]:
            counts = judge.status == "compile_error"
            if counts:
                compile_count += 1
            if judge.status in {"compile_error", "wrong_answer", "system_error", "accepted"}:
                note = "编译失败计入代码实现问题" if counts else "答案错误不直接认定为代码实现问题" if judge.status == "wrong_answer" else _judge_note(judge.status)
                evidence.append(_judge_evidence(fact, judge, counts, note))
    total = compile_count + reason_count
    status = _status(total)
    if total >= 2:
        reason = f"编译失败 {compile_count} 次，实现或语法类错题 {reason_count} 次。"
    elif total == 1:
        reason = f"编译失败 {compile_count} 次，实现或语法类错题 {reason_count} 次，还不能确认。"
    else:
        reason = "还没有足够的编译失败或实现、语法类错题。答案错误不直接算作代码实现问题。"
    return _item("implementation", status, point, topics, total, evidence, reason)


def _boundary_diagnosis(point: dict | None, topics: list[dict], facts: list[dict]) -> dict:
    evidence = []
    reason_count = 0
    sample_count = 0
    for fact in facts:
        evidence.extend(_common_exclusions(fact))
        wrong = fact["wrong"]
        counts = wrong is not None and wrong.reason_type == "boundary"
        if wrong is not None:
            if counts:
                reason_count += 1
            evidence.append(_reason_evidence(fact, wrong, counts))
        for judge in fact["judges"]:
            mismatch = _sample_other_wrong(judge, fact)
            if mismatch:
                sample_count += 1
                evidence.append(
                    {
                        "type": "sample_passed_other_failed",
                        "submission_id": judge.submission_id,
                        "problem_id": fact["problem"].id,
                        "problem_title": fact["problem"].title,
                        "judge_status": judge.status,
                        "failed_case_count": mismatch,
                        "counts": True,
                        "note": "样例通过，其他测试用例答案错误。同一次提交只计 1 次。",
                    }
                )
            elif judge.status in EXCLUDED_JUDGE or judge.status == "wrong_answer":
                evidence.append(_judge_evidence(fact, judge, False, _boundary_note(judge.status)))
    total = reason_count + sample_count
    status = _status(total)
    if total >= 2:
        reason = f"边界类错题 {reason_count} 次，样例通过但其他用例未通过 {sample_count} 次。"
    elif total == 1:
        reason = f"边界类证据只有 {total} 次，还不能确认。"
    else:
        reason = "还没有足够的边界证据。普通答案错误、编译错误、运行错误、超时和系统异常都不算边界问题。"
    return _item("boundary", status, point, topics, total, evidence, reason)


def _sample_other_wrong(judge: ProblemJudgeResult, fact: dict) -> int:
    if judge.status != "wrong_answer":
        return 0
    cases = fact["cases"].get(judge.id, [])
    if not cases:
        return 0
    sample = [case for case in cases if fact["case_types"].get(case.test_case_id) == "sample"]
    other = [case for case in cases if fact["case_types"].get(case.test_case_id) != "sample"]
    if not sample or not other:
        return 0
    if any(case.status != "accepted" for case in sample):
        return 0
    if any(case.status in EXCLUDED_JUDGE for case in other):
        return 0
    failed = [case for case in other if case.status == "wrong_answer"]
    if len(failed) != len([case for case in other if case.status != "accepted"]):
        return 0
    return len(failed)


def _common_exclusions(fact: dict) -> list[dict]:
    rows = []
    if fact["learning_status"] == "self_completed":
        rows.append(
            {
                "type": "learning_status",
                "problem_id": fact["problem"].id,
                "problem_title": fact["problem"].title,
                "status": "self_completed",
                "counts": False,
                "note": "用户自评完成，不是系统判题通过",
            }
        )
    for submission in fact["submissions"]:
        if submission.status == "unjudged" and submission.id not in fact["judged_submission_ids"]:
            rows.append(
                {
                    "type": "submission",
                    "submission_id": submission.id,
                    "problem_id": fact["problem"].id,
                    "status": "unjudged",
                    "counts": False,
                    "note": "尚未判题，不形成判题结论",
                }
            )
    for record in fact["practice"]:
        rows.append(
            {
                "type": "practice_record",
                "problem_id": fact["problem"].id,
                "completion_type": record.completion_type,
                "counts": False,
                "note": "练习记录不是判题结果，也不代表正式通过",
            }
        )
    return rows


def _reason_evidence(fact: dict, wrong: ProblemWrongRecord, counts: bool) -> dict:
    return {
        "type": "wrong_reason",
        "problem_id": fact["problem"].id,
        "problem_title": fact["problem"].title,
        "reason_type": wrong.reason_type,
        "submission_id": wrong.related_submission_id,
        "counts": counts,
        "note": "错题原因按题目记录计 1 次，不按测试用例重复计算",
    }


def _judge_evidence(fact: dict, judge: ProblemJudgeResult, counts: bool, note: str) -> dict:
    return {
        "type": "judge_result",
        "submission_id": judge.submission_id,
        "problem_id": fact["problem"].id,
        "problem_title": fact["problem"].title,
        "status": judge.status,
        "counts": counts,
        "note": note,
    }


def _judge_note(status: str) -> str:
    if status == "system_error":
        return "判题环境异常，不是用户答案错误"
    if status == "accepted":
        return "本地测试数据通过，不是官方 OJ 的 AC，也不作为薄弱证据"
    if status == "compile_error":
        return "编译失败不计入这一类"
    return "这次判题不计入这一类"


def _boundary_note(status: str) -> str:
    if status == "wrong_answer":
        return "普通答案错误不归类为边界问题"
    if status == "system_error":
        return "判题环境异常，不是用户答案错误"
    if status == "compile_error":
        return "编译失败不计入边界问题"
    if status == "runtime_error":
        return "运行错误不计入边界问题"
    if status == "time_limit_exceeded":
        return "超时不计入边界问题"
    return _judge_note(status)


def _item(category: str, status: str, point: dict | None, topics: list[dict], evidence_count: int, evidence: list[dict], reason: str) -> dict:
    return {
        "category": category,
        "status": status,
        "knowledge_point_id": None if point is None else point["id"],
        "knowledge_point_name": None if point is None else point["name"],
        "goal_id": None if point is None else point["goal_id"],
        "problem_topics": topics,
        "evidence_count": evidence_count,
        "evidence": evidence,
        "reason": reason,
    }


def _status(count: int) -> str:
    if count >= 2:
        return "confirmed"
    if count == 1:
        return "suspected"
    return "insufficient_data"


def _low_streak(scores: list[int]) -> int:
    streak = 0
    for score in reversed(scores):
        if score >= 60:
            break
        streak += 1
    return streak


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


def _user_links(session: Session, user_id: int) -> list[TopicKnowledgeLink]:
    return list(session.exec(select(TopicKnowledgeLink).where(TopicKnowledgeLink.user_id == user_id).order_by(TopicKnowledgeLink.id)).all())


def _topics(session: Session, user_id: int) -> dict[int, ProblemTopic]:
    rows = session.exec(select(ProblemTopic).where(ProblemTopic.user_id == user_id).order_by(ProblemTopic.id)).all()
    return {row.id: row for row in rows if row.id is not None}


def _problems(session: Session, user_id: int) -> list[Problem]:
    return list(session.exec(select(Problem).where(Problem.user_id == user_id).order_by(Problem.id)).all())


def _topic_problems(session: Session, problem_ids: list[int]) -> dict[int, list[int]]:
    grouped: dict[int, list[int]] = {}
    if not problem_ids:
        return grouped
    rows = session.exec(select(ProblemTopicLink).where(ProblemTopicLink.problem_id.in_(problem_ids)).order_by(ProblemTopicLink.id)).all()
    for row in rows:
        bucket = grouped.setdefault(row.topic_id, [])
        if row.problem_id not in bucket:
            bucket.append(row.problem_id)
    return grouped


def _problems_for_topics(topics: list[dict], topic_problems: dict[int, list[int]]) -> list[int]:
    found: list[int] = []
    for topic in topics:
        for problem_id in topic_problems.get(topic["id"], []):
            if problem_id not in found:
                found.append(problem_id)
    return found


def _facts(session: Session, user_id: int, problems: list[Problem]) -> dict[int, dict]:
    problem_ids = [problem.id for problem in problems if problem.id is not None]
    if not problem_ids:
        return {}
    statuses = {
        row.problem_id: row.status
        for row in session.exec(select(ProblemLearningStatus).where(ProblemLearningStatus.user_id == user_id)).all()
        if row.problem_id in set(problem_ids)
    }
    wrongs = {
        row.problem_id: row
        for row in session.exec(select(ProblemWrongRecord).where(ProblemWrongRecord.user_id == user_id)).all()
        if row.problem_id in set(problem_ids)
    }
    submissions = [
        row
        for row in session.exec(select(ProblemSubmission).where(ProblemSubmission.user_id == user_id).order_by(ProblemSubmission.submitted_at, ProblemSubmission.id)).all()
        if row.problem_id in set(problem_ids)
    ]
    judges = [
        row
        for row in session.exec(select(ProblemJudgeResult).where(ProblemJudgeResult.user_id == user_id).order_by(ProblemJudgeResult.id)).all()
        if row.problem_id in set(problem_ids)
    ]
    judge_ids = [row.id for row in judges if row.id is not None]
    cases: dict[int, list[ProblemJudgeCaseResult]] = {}
    if judge_ids:
        for row in session.exec(select(ProblemJudgeCaseResult).where(ProblemJudgeCaseResult.judge_result_id.in_(judge_ids)).order_by(ProblemJudgeCaseResult.id)).all():
            cases.setdefault(row.judge_result_id, []).append(row)
    case_ids = [row.test_case_id for group in cases.values() for row in group]
    case_types = {}
    if case_ids:
        for row in session.exec(select(ProblemTestCase).where(ProblemTestCase.id.in_(case_ids))).all():
            case_types[row.id] = row.case_type
    practice: dict[int, list[ProblemPracticeRecord]] = {}
    for row in session.exec(select(ProblemPracticeRecord).where(ProblemPracticeRecord.user_id == user_id).order_by(ProblemPracticeRecord.id)).all():
        if row.problem_id in set(problem_ids):
            practice.setdefault(row.problem_id, []).append(row)
    judges_by_problem: dict[int, list[ProblemJudgeResult]] = {}
    for row in judges:
        judges_by_problem.setdefault(row.problem_id, []).append(row)
    submissions_by_problem: dict[int, list[ProblemSubmission]] = {}
    for row in submissions:
        submissions_by_problem.setdefault(row.problem_id, []).append(row)
    facts = {}
    for problem in problems:
        if problem.id is None:
            continue
        problem_judges = judges_by_problem.get(problem.id, [])
        facts[problem.id] = {
            "problem": problem,
            "learning_status": statuses.get(problem.id, "todo"),
            "wrong": wrongs.get(problem.id),
            "submissions": submissions_by_problem.get(problem.id, []),
            "judges": problem_judges,
            "judged_submission_ids": {row.submission_id for row in problem_judges},
            "cases": cases,
            "case_types": case_types,
            "practice": practice.get(problem.id, []),
        }
    return facts


def _topic_ref(topic: ProblemTopic) -> dict:
    return {"id": topic.id, "name": topic.name}


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
