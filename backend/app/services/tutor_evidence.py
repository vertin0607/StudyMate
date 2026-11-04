"""从已有学习记录里收集这次提问需要的证据。不调用模型，也不写库。"""

import logging
import re

from sqlmodel import Session, select

from app.models.goal import LearningGoal
from app.models.judge import ProblemJudgeCaseResult, ProblemJudgeResult
from app.models.knowledge import KnowledgePoint
from app.models.practice import ProblemLearningStatus, ProblemWrongRecord
from app.models.problem import Problem, ProblemTopicLink
from app.models.quiz import KnowledgeMasteryEvent, QuizAnswer, QuizQuestion
from app.models.review import ReviewRecord
from app.models.submission import ProblemSubmission
from app.models.topic_link import TopicKnowledgeLink

logger = logging.getLogger(__name__)

CATEGORIES = ("concept", "formula", "reasoning", "algorithm", "implementation", "boundary", "none")
EVIDENCE_STATUSES = ("confirmed", "suspected", "insufficient_data")
STRATEGIES = ("basic", "intermediate", "advanced", "code_debugging", "forgetting_recovery")
MEMORY_STATUSES = ("active", "improving", "resolved", "uncertain")
USER_ERROR_JUDGEMENTS = {"wrong_answer", "compile_error", "runtime_error", "time_limit_exceeded"}
IGNORED_JUDGEMENTS = {"system_error", "unjudged", "judging"}
ENVIRONMENT_MARKERS = ("系统异常", "docker", "sandbox", "内部错误", "judge environment")
REASON_CATEGORY = {
    "algorithm": "algorithm",
    "implementation": "implementation",
    "syntax": "implementation",
    "boundary": "boundary",
}
CODE_LIMIT = 2000


def is_formal_pass(judge_status: str | None, learning_status: str | None = None) -> bool:
    """本地 accepted 才是正式通过。自评完成、未判题和系统异常都不是。"""
    del learning_status
    return judge_status == "accepted"


def memory_dedup_key(category: str, knowledge_point_id: int | None, problem_id: int | None) -> str:
    """后续记忆表用这个非空键，配合 (user_id, dedup_key) 做唯一约束。"""
    return f"{category}|kp:{knowledge_point_id or 0}|problem:{problem_id or 0}"


def next_memory_status(current: str, event: str, independent_successes: int = 0) -> str:
    """普通聊天和完成任务使用 event='none'，不会改变状态。"""
    if current not in MEMORY_STATUSES:
        current = "uncertain"
    if event == "none":
        return current
    if event == "error":
        return "active"
    if event == "contradiction":
        return "uncertain"
    if event == "success":
        if current == "resolved":
            return "resolved"
        if independent_successes >= 2:
            return "resolved"
        if current in {"active", "uncertain"}:
            return "improving"
        return current
    return current


def dedupe_evidence(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result = []
    for item in items:
        key = item["source_key"]
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def public_diagnosis(analysis: dict) -> dict | None:
    """没有明确错误，或证据不足时，不给前端返回诊断。"""
    if analysis["category"] == "none" or analysis["evidence_status"] == "insufficient_data":
        return None
    return {
        "category": analysis["category"],
        "evidence_status": analysis["evidence_status"],
        "knowledge_point_id": analysis["knowledge_point_id"],
        "knowledge_point_name": analysis["knowledge_point_name"],
        "prerequisite_candidates": analysis["prerequisite_candidates"],
        "teaching_strategy": analysis["teaching_strategy"],
        "evidence_summary": analysis["evidence_summary"],
    }


def analyze_message(session: Session, *, user_id: int, goal_id: int | None, question: str) -> dict:
    points = _goal_points(session, user_id, goal_id)
    named_points = _match_by_full_name(points, question)
    problem = _match_problem(session, user_id, question)
    linked_points = [] if problem is None else _linked_points(session, user_id, problem, points)
    if named_points:
        discussed = named_points
    elif len(linked_points) == 1:
        discussed = linked_points
    else:
        discussed = []
    primary = _primary_point(discussed, question) if named_points else (discussed[0] if len(discussed) == 1 else None)
    point_ids = [point.id for point in discussed if point.id is not None]
    evidences = _collect_evidences(session, question, primary, point_ids, problem)
    evidences = dedupe_evidence(evidences)
    statement_category = classify_statement(question)
    category = _choose_category(statement_category, evidences)
    contradictory = _contradicts(statement_category, evidences)
    if contradictory:
        category = "none"
    formula_written = statement_category == "formula"
    code_located = _code_located(question, evidences)
    same_count = _same_category_count(category, evidences)
    status = _evidence_status(category, formula_written, code_located, same_count)
    if contradictory:
        status = "insufficient_data"
    assessed, mastery = _mastery(session, primary)
    forgetting = _forgetting(session, primary)
    strategy = _strategy(category, mastery, assessed, forgetting, evidences)
    candidates = _prerequisites(points, primary, question, evidences)
    summary = _summary(category, status, primary, problem, contradictory)
    submission_code = _latest_submission_code(session, problem) if strategy == "code_debugging" else None
    context = _model_context(strategy, primary, assessed, mastery, evidences, question, candidates, problem, submission_code)
    return {
        "category": category,
        "evidence_status": status,
        "knowledge_point_id": None if primary is None else primary.id,
        "knowledge_point_name": None if primary is None else primary.name,
        "prerequisite_candidates": candidates,
        "teaching_strategy": strategy,
        "evidence_summary": summary,
        "model_context": context,
        "direct_event_count": len([item for item in evidences if item["counts"]]),
        "evidence_keys": [item["source_key"] for item in evidences],
        "formal_pass": _formal_pass_for(session, user_id, problem),
        "vague": _is_vague(question),
        "reserved_dedup_key": memory_dedup_key(
            category,
            None if primary is None else primary.id,
            None if problem is None else problem.id,
        ),
    }


def classify_statement(text: str) -> str:
    """只识别明确表述。单纯提问返回 none。"""
    if _boundary_claim(text):
        return "boundary"
    if _formula_claim(text):
        return "formula"
    if _algorithm_claim(text):
        return "algorithm"
    if _reasoning_claim(text):
        return "reasoning"
    if _implementation_claim(text):
        return "implementation"
    if _concept_claim(text):
        return "concept"
    return "none"


def _goal_points(session: Session, user_id: int, goal_id: int | None) -> list[KnowledgePoint]:
    if goal_id is None:
        return []
    goal = session.get(LearningGoal, goal_id)
    if goal is None or goal.user_id != user_id:
        return []
    return list(session.exec(select(KnowledgePoint).where(KnowledgePoint.goal_id == goal.id).order_by(KnowledgePoint.id)).all())


def _label(item: object) -> str:
    title = getattr(item, "title", None)
    if isinstance(title, str) and title.strip():
        return title.strip()
    return str(getattr(item, "name", "")).strip()


def _match_by_full_name(items: list, text: str) -> list:
    """只用完整名称。被更长名称包含的短名称不算单独命中。"""
    matched = []
    folded = text.casefold()
    ordered = sorted(items, key=lambda item: len(_label(item)), reverse=True)
    for item in ordered:
        name = _label(item)
        if len(name) < 2 or name.casefold() not in folded:
            continue
        covered = any(name.casefold() != _label(other).casefold() and name.casefold() in _label(other).casefold() for other in matched)
        if covered:
            continue
        matched.append(item)
    return matched


def _match_problem(session: Session, user_id: int, text: str) -> Problem | None:
    problems = list(session.exec(select(Problem).where(Problem.user_id == user_id)).all())
    matched = _match_by_full_name(problems, text)
    return None if not matched else matched[0]


def _linked_points(session: Session, user_id: int, problem: Problem, allowed: list[KnowledgePoint]) -> list[KnowledgePoint]:
    allowed_by_id = {point.id: point for point in allowed if point.id is not None}
    topic_ids = [
        row.topic_id
        for row in session.exec(select(ProblemTopicLink).where(ProblemTopicLink.problem_id == problem.id)).all()
    ]
    if not topic_ids:
        return []
    links = session.exec(
        select(TopicKnowledgeLink).where(
            TopicKnowledgeLink.user_id == user_id,
            TopicKnowledgeLink.problem_topic_id.in_(topic_ids),
        )
    ).all()
    points = []
    for link in links:
        point = allowed_by_id.get(link.knowledge_point_id)
        if point is not None and point not in points:
            points.append(point)
    return points


def _primary_point(points: list[KnowledgePoint], text: str) -> KnowledgePoint | None:
    if not points:
        return None
    if len(points) == 1:
        return points[0]
    folded = text.casefold()
    anchors = [word for word in ("相加", "最优", "输出层", "next", "编译", "空数组", "越界") if word.casefold() in folded]
    best = points[0]
    best_distance = None
    for point in points:
        name_at = folded.find(point.name.casefold())
        if anchors:
            distance = min(abs(name_at - folded.find(anchor.casefold())) for anchor in anchors)
        else:
            distance = name_at
        if best_distance is None or distance < best_distance:
            best = point
            best_distance = distance
    return best


def _collect_evidences(session: Session, question: str, primary: KnowledgePoint | None, point_ids: list[int], problem: Problem | None) -> list[dict]:
    items: list[dict] = []
    statement = classify_statement(question)
    if statement != "none":
        items.append(_evidence("current_statement", None, statement, True, "这次发言里有明确的错误表述。", None if primary is None else primary.id, None if problem is None else problem.id))
    if point_ids:
        answers = session.exec(
            select(QuizAnswer, QuizQuestion)
            .join(QuizQuestion, QuizAnswer.question_id == QuizQuestion.id)
            .where(QuizQuestion.knowledge_point_id.in_(point_ids), QuizAnswer.is_correct == False)  # noqa: E712
        ).all()
        for answer, question_row in answers:
            hint = _hint_from_text(answer.error_reason)
            counts = hint is not None
            reason = answer.error_reason.strip() or "没有具体错因"
            items.append(
                _evidence(
                    "quiz_answer",
                    answer.id,
                    hint,
                    counts,
                    f"检测作答错误：{reason[:120]}",
                    question_row.knowledge_point_id,
                    None,
                )
            )
        items.extend(_diagnosis_notes(session, primary, point_ids))
    if problem is not None and problem.id is not None:
        items.extend(_problem_evidences(session, problem))
    return items


def _problem_evidences(session: Session, problem: Problem) -> list[dict]:
    items = []
    wrong = session.exec(
        select(ProblemWrongRecord).where(
            ProblemWrongRecord.user_id == problem.user_id,
            ProblemWrongRecord.problem_id == problem.id,
        )
    ).first()
    if wrong is not None:
        hint = REASON_CATEGORY.get(wrong.reason_type)
        detail = wrong.reason_detail.strip()
        items.append(
            _evidence(
                "problem_wrong_record",
                wrong.id,
                hint,
                hint is not None,
                f"用户填写的错题原因是{wrong.reason_type}" + (f"：{detail[:80]}" if detail else ""),
                None,
                problem.id,
            )
        )
    judges = list(
        session.exec(
            select(ProblemJudgeResult).where(
                ProblemJudgeResult.user_id == problem.user_id,
                ProblemJudgeResult.problem_id == problem.id,
            )
        ).all()
    )
    for judge in judges:
        if judge.status in IGNORED_JUDGEMENTS or _environment_compile(judge):
            continue
        if judge.status not in USER_ERROR_JUDGEMENTS:
            continue
        hint = "implementation" if judge.status == "compile_error" and not _environment_compile(judge) else None
        failed_cases = session.exec(
            select(ProblemJudgeCaseResult).where(ProblemJudgeCaseResult.judge_result_id == judge.id)
        ).all()
        failed_count = len([item for item in failed_cases if item.status != "accepted"])
        note = f"本地判题结果是 {judge.status}"
        if failed_count:
            note += f"，{failed_count} 个测试点未通过"
        items.append(_evidence("judge_result", judge.id, hint, hint is not None, note, None, problem.id))
    return items


def _diagnosis_notes(session: Session, primary: KnowledgePoint | None, point_ids: list[int]) -> list[dict]:
    if primary is None or primary.goal_id is None:
        return []
    try:
        from app.services.diagnosis_rules import diagnose

        report = diagnose(session, primary.goal_id)
    except Exception:
        logger.warning("读取已有诊断失败，本次不使用诊断辅助说明", exc_info=True)
        return []
    found = False
    for rows in report.get("by_category", {}).values():
        for item in rows:
            if item.get("knowledge_point_id") in point_ids and item.get("status") in {"confirmed", "suspected"}:
                found = True
                break
        if found:
            break
    if not found:
        return []
    return [
        _evidence(
            "diagnosis",
            primary.id,
            None,
            False,
            "已有诊断只作为辅助，不单独计为新的错误证据。",
            primary.id,
            None,
        )
    ]


def _evidence(source: str, source_id: int | None, hint: str | None, counts: bool, summary: str, point_id: int | None, problem_id: int | None) -> dict:
    key = source if source_id is None else f"{source}:{source_id}"
    return {
        "source_key": key,
        "source": source,
        "source_id": source_id,
        "category_hint": hint,
        "counts": counts,
        "summary": summary,
        "knowledge_point_id": point_id,
        "problem_id": problem_id,
    }


def _choose_category(statement_category: str, evidences: list[dict]) -> str:
    if statement_category != "none":
        return statement_category
    hints = [item["category_hint"] for item in evidences if item["counts"] and item["category_hint"]]
    unique = set(hints)
    if len(unique) == 1:
        return unique.pop()
    return "none"


def _contradicts(statement_category: str, evidences: list[dict]) -> bool:
    if statement_category == "none":
        return False
    hints = {item["category_hint"] for item in evidences if item["counts"] and item["category_hint"] and item["source"] != "current_statement"}
    return any(hint != statement_category for hint in hints)


def _same_category_count(category: str, evidences: list[dict]) -> int:
    if category == "none":
        return 0
    return len([item for item in evidences if item["counts"] and item["category_hint"] == category])


def _evidence_status(category: str, formula_written: bool, code_located: bool, same_count: int) -> str:
    if category == "none":
        return "insufficient_data"
    if formula_written or (category in {"implementation", "boundary"} and code_located):
        return "confirmed"
    if same_count >= 2:
        return "confirmed"
    if same_count >= 1:
        return "suspected"
    return "insufficient_data"


def _code_located(question: str, evidences: list[dict]) -> bool:
    if _pasted_code(question) is not None:
        return True
    return any(item["source"] == "judge_result" and item["category_hint"] == "implementation" for item in evidences)


def _strategy(category: str, mastery: int | None, assessed: bool, forgetting: bool, evidences: list[dict]) -> str:
    compile_or_runtime = any(
        item["source"] == "judge_result" and ("结果是 compile_error" in item["summary"] or "结果是 runtime_error" in item["summary"])
        for item in evidences
    )
    if category in {"implementation", "boundary"} or compile_or_runtime:
        return "code_debugging"
    if forgetting:
        return "forgetting_recovery"
    if category in {"concept", "formula"}:
        return "basic"
    if category == "reasoning" or (assessed and mastery is not None and 60 <= mastery < 85):
        return "intermediate"
    if assessed and mastery is not None and mastery >= 85:
        return "advanced"
    if category == "algorithm":
        return "intermediate"
    return "basic"


def _forgetting(session: Session, point: KnowledgePoint | None) -> bool:
    if point is None or point.id is None:
        return False
    events = list(
        session.exec(select(KnowledgeMasteryEvent).where(KnowledgeMasteryEvent.knowledge_point_id == point.id)).all()
    )
    ordered = sorted(events, key=lambda item: (item.created_at, item.id or 0))
    dropped = len(ordered) >= 2 and ordered[-1].new_level < ordered[-2].new_level
    records = list(session.exec(select(ReviewRecord).where(ReviewRecord.knowledge_point_id == point.id)).all())
    failed = len([item for item in records if item.result == "fail"]) >= 2
    return dropped or failed


def _mastery(session: Session, point: KnowledgePoint | None) -> tuple[bool, int | None]:
    if point is None:
        return False, None
    events = list(
        session.exec(select(KnowledgeMasteryEvent).where(KnowledgeMasteryEvent.knowledge_point_id == point.id)).all()
    )
    assessed = bool(events) or point.status == "mastered"
    if not assessed:
        return False, None
    return True, point.mastery_level


def _prerequisites(points: list[KnowledgePoint], primary: KnowledgePoint | None, question: str, evidences: list[dict]) -> list[dict]:
    """只有发言或检测错因写出了另一个已有知识点的全名，才列为候选。"""
    corpus = question + "\n" + " ".join(item["summary"] for item in evidences if item["source"] == "quiz_answer")
    candidates = []
    for point in _match_by_full_name(points, corpus):
        if primary is not None and point.id == primary.id:
            continue
        candidates.append(
            {
                "knowledge_point_id": point.id,
                "name": point.name,
                "evidence_status": "suspected",
                "basis": "这次发言或检测错因写出了该知识点的完整名称，只作为前置候选，没有建立正式关系。",
            }
        )
    return candidates


def _summary(category: str, status: str, point: KnowledgePoint | None, problem: Problem | None, contradictory: bool) -> str:
    if contradictory:
        return "现有直接证据指向的错误类别不一致，这次不作出判断。"
    if category == "none" or status == "insufficient_data":
        return ""
    subject = point.name if point is not None else (problem.title if problem is not None else "这次发言")
    label = {
        "concept": "概念理解",
        "formula": "数学公式",
        "reasoning": "推理过程",
        "algorithm": "算法思路",
        "implementation": "代码实现",
        "boundary": "边界条件",
    }[category]
    level = "已有明确的直接证据" if status == "confirmed" else "有一些依据，但还不能当成长期问题"
    return f"{subject}：{label}。{level}。"


def _model_context(
    strategy: str,
    point: KnowledgePoint | None,
    assessed: bool,
    mastery: int | None,
    evidences: list[dict],
    question: str,
    candidates: list[dict],
    problem: Problem | None,
    submission_code: str | None,
) -> dict:
    summaries = [item["summary"] for item in evidences if item["source"] != "current_statement"][:5]
    auxiliary = next((item["summary"] for item in evidences if item["source"] == "diagnosis"), None)
    code = None
    title = None
    if strategy == "code_debugging":
        code = _pasted_code(question) or submission_code
        title = None if problem is None else problem.title
    return {
        "knowledge_point": None
        if point is None
        else {
            "id": point.id,
            "name": point.name,
            "mastery_level": mastery,
            "mastery_assessed": assessed,
        },
        "problem_title": title,
        "evidence_summaries": summaries,
        "auxiliary_note": auxiliary,
        "latest_code": code,
        "prerequisite_candidates": [{"name": item["name"], "basis": item["basis"]} for item in candidates],
    }


def _latest_submission_code(session: Session, problem: Problem | None) -> str | None:
    if problem is None or problem.id is None:
        return None
    rows = list(
        session.exec(
            select(ProblemSubmission).where(
                ProblemSubmission.user_id == problem.user_id,
                ProblemSubmission.problem_id == problem.id,
            )
        ).all()
    )
    if not rows:
        return None
    latest = sorted(rows, key=lambda item: (item.submitted_at, item.id or 0))[-1]
    return latest.source_code[:CODE_LIMIT]


def _formal_pass_for(session: Session, user_id: int, problem: Problem | None) -> bool:
    if problem is None or problem.id is None:
        return False
    judges = list(
        session.exec(
            select(ProblemJudgeResult).where(
                ProblemJudgeResult.user_id == user_id,
                ProblemJudgeResult.problem_id == problem.id,
            )
        ).all()
    )
    if not judges:
        return False
    latest = sorted(judges, key=lambda item: (item.id or 0))[-1]
    return is_formal_pass(latest.status)


def _pasted_code(text: str) -> str | None:
    if "```" not in text:
        return None
    body = text.split("```", 2)[1]
    if "\n" in body:
        first, rest = body.split("\n", 1)
        if first.strip().casefold() in {"cpp", "c++", "c"}:
            body = rest
    body = body.strip()
    return body[:CODE_LIMIT] or None


def _environment_compile(judge: ProblemJudgeResult) -> bool:
    if judge.status != "compile_error":
        return False
    blob = f"{judge.compile_output}\n{judge.error_message}".casefold()
    return any(marker.casefold() in blob for marker in ENVIRONMENT_MARKERS)


def _hint_from_text(text: str) -> str | None:
    if any(word in text for word in ("相加", "公式", "偏导", "导数")):
        return "formula"
    if any(word in text for word in ("概念", "定义", "最优")):
        return "concept"
    if "推理" in text or "输出层" in text:
        return "reasoning"
    if "算法" in text or "next" in text.casefold():
        return "algorithm"
    if any(word in text for word in ("编译", "实现", "越界", "语法")):
        return "implementation"
    if any(word in text for word in ("边界", "空数组")):
        return "boundary"
    return None


def _is_unchecked_question(text: str) -> bool:
    asked = any(mark in text for mark in ("吗", "？", "?"))
    asserted = any(word in text for word in ("就是", "我认为", "我觉得", "应该是", "写成"))
    return asked and not asserted


def _is_vague(text: str) -> bool:
    return any(phrase in text for phrase in ("有点乱", "说不清楚", "好像不太懂", "有点模糊"))


def _formula_claim(text: str) -> bool:
    if _is_unchecked_question(text):
        return False
    if re.search(r"(?:\\partial|∂|\\frac\{).{0,160}\+.{0,160}(?:\\partial|∂|\\frac\{)", text, re.S):
        return True
    if ("相加" in text or "加上" in text) and any(word in text for word in ("导数", "偏导", "链式", "梯度")):
        if "还是" in text and not any(word in text for word in ("就是", "我认为", "我觉得")):
            return False
        return True
    return False


def _concept_claim(text: str) -> bool:
    if _is_unchecked_question(text):
        return False
    if any(phrase in text for phrase in ("直接得到最优", "直接得到全局最优", "把损失函数一直往回传", "把损失一直往回传", "反向传播就是把损失")):
        return True
    return "梯度下降就是" in text and "最优" in text and "局部" not in text


def _reasoning_claim(text: str) -> bool:
    if _is_unchecked_question(text):
        return False
    return any(phrase in text for phrase in ("不需要从输出层", "可以从输入层开始", "每一层可以同时求", "从前往后反传"))


def _algorithm_claim(text: str) -> bool:
    if _is_unchecked_question(text):
        return False
    compact = re.sub(r"\s+", "", text)
    mixes = ("next[0]=-1" in compact or "next[0]＝-1" in compact) and ("前缀函数" in text or "最长真前缀" in text)
    stores_character = any(phrase in compact for phrase in ("next数组就是下一个字符", "next存的是字符", "next数组存的是字符"))
    return mixes or stores_character


def _implementation_claim(text: str) -> bool:
    if _is_unchecked_question(text):
        return False
    return any(phrase in text for phrase in ("数组越界", "循环边界写错", "没有初始化", "递归没有终止", "编译错误", "编译失败", "编译不过"))


def _boundary_claim(text: str) -> bool:
    if _is_unchecked_question(text):
        return False
    return any(phrase in text for phrase in ("空数组", "只有一个元素", "边界条件", "下标临界"))
