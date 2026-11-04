"""间隔复习和遗忘风险。只根据检测记录计算，不调用模型。"""

from dataclasses import dataclass
from datetime import date, timedelta

# 第 1 到第 4 次复习通过后的间隔。第一次检测本身不走这张表。
PASS_INTERVALS = (3, 7, 14, 30)


@dataclass
class ReviewDecision:
    successful_passes: int
    consecutive_high: int
    interval_days: int
    result: str
    reason: str


def decide_review(
    *,
    is_first_assessment: bool,
    successful_passes: int,
    previous_interval: int,
    latest_score: int,
    consecutive_high: int,
) -> ReviewDecision:
    """根据一次真实检测成绩决定下一次复习间隔。"""
    score = max(0, min(100, int(latest_score)))
    high = consecutive_high + 1 if score >= 90 else 0
    if is_first_assessment:
        if score < 60:
            return ReviewDecision(0, high, 1, "fail", "首次检测低于 60 分，1 天后复习")
        if score < 75:
            return ReviewDecision(0, high, 2, "partial", "首次检测为 60–74 分，2 天后复习")
        return ReviewDecision(0, high, 1, "initial", "首次检测后 1 天复习。一次高分不拉长间隔")

    if score < 60:
        return ReviewDecision(successful_passes, 0, 1, "fail", "本次复习低于 60 分，间隔缩短为 1 天")
    if score < 75:
        return ReviewDecision(successful_passes, high, 2, "partial", "本次复习为 60–74 分，2 天后再复习，间隔不延长")

    passes = successful_passes + 1
    if passes <= len(PASS_INTERVALS):
        interval = PASS_INTERVALS[passes - 1]
        reason = f"第 {passes} 次复习通过，下次间隔 {interval} 天"
    else:
        interval = min(90, max(30, round(max(previous_interval, 30) * 1.5)))
        reason = f"已连续通过，间隔延长到 {interval} 天，之后仍会安排巩固"
    if score >= 90 and high >= 3 and passes >= 5:
        boosted = min(90, max(interval, round(interval * 1.5)))
        if boosted != interval:
            interval = boosted
            reason = f"连续 {high} 次达到 90 分以上，间隔延长到 {interval} 天，不会永久标记为掌握"
    elif score < 90:
        reason = f"本次 {score} 分，适度延长到 {interval} 天后复习"
    return ReviewDecision(passes, high, interval, "pass", reason)


def next_review_day(reviewed_on: date, interval_days: int) -> date:
    return reviewed_on + timedelta(days=max(1, interval_days))


def forgetting_risk(
    *,
    mastery: int | None,
    latest_score: int | None,
    days_since_quiz: int | None,
    overdue_days: int,
    recent_low_count: int,
) -> tuple[str, str]:
    """返回 low、medium 或 high，以及一句可核对的原因。"""
    reasons: list[str] = []
    if mastery is not None and mastery < 60:
        reasons.append(f"掌握度 {mastery} 较低")
    if latest_score is not None and latest_score < 60:
        reasons.append(f"最近检测 {latest_score} 分，不足 60 分")
    if overdue_days > 0:
        reasons.append(f"已超过计划复习日 {overdue_days} 天")
    if recent_low_count >= 2:
        reasons.append("最近多次检测低于 60 分")
    if mastery is not None and 60 <= mastery < 85:
        reasons.append(f"掌握度 {mastery} 还未稳定")
    if latest_score is not None and 60 <= latest_score < 85:
        reasons.append(f"最近检测 {latest_score} 分")
    if days_since_quiz is not None and days_since_quiz >= 7:
        reasons.append(f"距离上次检测已有 {days_since_quiz} 天")

    high = bool(
        overdue_days > 0
        or (mastery is not None and mastery < 60)
        or (latest_score is not None and latest_score < 60)
        or recent_low_count >= 2
    )
    medium = bool(
        (days_since_quiz is not None and days_since_quiz >= 7)
        or (mastery is not None and mastery < 85)
        or (latest_score is not None and 60 <= latest_score < 85)
    )
    if high:
        detail = "，".join(reasons) if reasons else "需要尽快复习"
        return "high", detail + "，建议尽快复习"
    if medium:
        detail = "，".join(reasons) if reasons else "距离上次检测已有一段时间或掌握度还未稳定"
        return "medium", detail + "，适合在间隔内巩固"
    if not reasons:
        reasons.append("仍在计划间隔内，最近表现稳定")
    return "low", "，".join(reasons)
