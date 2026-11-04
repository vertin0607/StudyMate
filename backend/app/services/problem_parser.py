"""校验题目分析 JSON。未知分类不会被当成正式知识点。"""

import json

from app.services.problem_catalog import CATALOG_NAMES

DIFFICULTIES = {"easy", "medium", "hard"}


def parse_problem_analysis(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("分析结果不是 JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("分析结果不是 JSON 对象")
    difficulty = data.get("difficulty")
    if difficulty not in DIFFICULTIES:
        raise ValueError("难度必须是 easy、medium 或 hard")
    main, main_suggestions = _points(data.get("main_knowledge_points"), "primary")
    secondary, secondary_suggestions = _points(data.get("secondary_knowledge_points"), "secondary")
    if not main:
        raise ValueError("至少需要一个已有分类中的主要考点")
    suggestions = main_suggestions + secondary_suggestions + _suggestions(data.get("suggested_new_topics"))
    return {
        "course": _text(data.get("course"), "课程", 80),
        "difficulty": difficulty,
        "main_knowledge_points": main,
        "secondary_knowledge_points": secondary,
        "suggested_new_topics": suggestions[:5],
        "algorithm_types": _strings(data.get("algorithm_types"), 5),
        "core_abilities": _strings(data.get("core_abilities"), 5),
        "solution_idea": _text(data.get("solution_idea"), "解题思路", 2000),
        "algorithm_steps": _strings(data.get("algorithm_steps"), 8),
        "time_complexity": _text(data.get("time_complexity"), "时间复杂度", 40),
        "space_complexity": _text(data.get("space_complexity"), "空间复杂度", 40),
        "complexity_reason": _text(data.get("complexity_reason"), "复杂度依据", 1000),
        "common_mistakes": _strings(data.get("common_mistakes"), 6),
        "review_suggestions": _strings(data.get("review_suggestions"), 6),
    }


def _points(value: object, relevance: str) -> tuple[list[dict], list[dict]]:
    if not isinstance(value, list):
        raise ValueError("知识点必须是列表")
    accepted: list[dict] = []
    suggested: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("知识点格式不正确")
        name = str(item.get("name", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if not name or not reason:
            raise ValueError("知识点需要名称和依据")
        payload = {"name": name[:40], "reason": reason[:500], "relevance": relevance}
        if name in CATALOG_NAMES:
            accepted.append(payload)
        else:
            suggested.append(payload)
    return accepted[:3], suggested


def _suggestions(value: object) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("新知识点建议必须是列表")
    rows = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        reason = str(item.get("reason", "")).strip()
        relevance = item.get("relevance", "secondary")
        if name and reason and relevance in {"primary", "secondary"} and name not in CATALOG_NAMES:
            rows.append({"name": name[:40], "reason": reason[:500], "relevance": relevance})
    return rows


def _strings(value: object, limit: int) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("列表字段不能为空")
    rows = []
    for item in value:
        text = str(item).strip()
        if text:
            rows.append(text[:200])
    if not rows:
        raise ValueError("列表字段不能为空")
    return rows[:limit]


def _text(value: object, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"缺少{label}")
    return value.strip()[:limit]
