"""把一次检测成绩折算成可解释的掌握度。一次高分不会直接变成熟练掌握。"""

def result_label(score: int) -> str:
    """这次试卷的等级。它只描述这一次检测，不是长期掌握度。"""
    if score >= 90:
        return "掌握良好"
    if score >= 75:
        return "基本掌握"
    if score >= 60:
        return "需要巩固"
    return "建议重新学习"


def status_label(status: str, assessed: bool) -> str:
    if not assessed and status not in {"proficient", "basic", "needs_review", "improving", "mastered"}:
        return "尚未评估"
    labels = {
        "not_started": "未学习",
        "learning": "学习中",
        "reviewing": "复习中",
        "improving": "逐步提高",
        "needs_review": "需要巩固",
        "basic": "基本掌握",
        "proficient": "熟练掌握",
        "mastered": "熟练掌握",
    }
    return labels.get(status, "学习中")


def next_mastery(previous: int | None, history_scores: list[int], latest: int) -> tuple[int, str, str]:
    """返回新的掌握度、状态和一句原因。history_scores 不含本次成绩。"""
    latest = max(0, min(100, int(latest)))
    if previous is None:
        if latest >= 90:
            return 74, "improving", "首次检测达到 90 分以上，先记为逐步提高，连续稳定后再升为熟练掌握"
        if latest >= 75:
            return latest, "basic", "首次检测进入基本掌握区间，尚未记为熟练掌握"
        if latest >= 60:
            return latest, "improving", "首次检测及格，掌握度按本次成绩逐步提高"
        return latest, "needs_review", "首次检测低于 60 分，标记为需要巩固"

    if latest < 60:
        blended = round(previous * 0.5 + latest * 0.5)
        level = min(blended, 59)
        return level, "needs_review", "最近一次检测低于 60 分，掌握度下调并标记为需要巩固"

    blended = round(previous * 0.4 + latest * 0.6)
    previous_score = history_scores[-1] if history_scores else None
    stable_high = previous_score is not None and previous_score >= 90 and latest >= 90 and previous >= 74
    if stable_high:
        level = max(blended, 90)
        return min(level, 100), "proficient", "连续检测都在 90 分以上，掌握度升为熟练掌握"
    if latest >= 90:
        level = min(blended, 89)
        status = "basic" if level >= 75 else "improving"
        return level, status, "本次成绩较高，但还没有连续稳定，暂不记为熟练掌握"
    level = max(0, min(100, blended))
    if level >= 75:
        return level, "basic", "按最近成绩与原掌握度加权后，保持在基本掌握"
    return level, "improving", "按最近成绩与原掌握度加权，掌握度逐步调整"
