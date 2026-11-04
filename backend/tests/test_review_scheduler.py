"""间隔和遗忘风险不访问数据库，也不调用模型。"""

from datetime import date

from app.services.review_scheduler import decide_review, forgetting_risk, next_review_day


def test_first_assessment_stays_short_even_with_high_score() -> None:
    decision = decide_review(
        is_first_assessment=True,
        successful_passes=0,
        previous_interval=1,
        latest_score=95,
        consecutive_high=0,
    )

    assert decision.interval_days == 1
    assert decision.successful_passes == 0
    assert decision.consecutive_high == 1
    assert "一次高分" in decision.reason


def test_passing_reviews_extend_step_by_step() -> None:
    passes = 0
    high = 1
    interval = 1
    expected = [3, 7, 14, 30]
    for score, days in zip((82, 94, 96, 95), expected, strict=True):
        decision = decide_review(
            is_first_assessment=False,
            successful_passes=passes,
            previous_interval=interval,
            latest_score=score,
            consecutive_high=high,
        )
        assert decision.interval_days == days
        assert decision.result == "pass"
        passes = decision.successful_passes
        high = decision.consecutive_high
        interval = decision.interval_days


def test_later_high_scores_grow_but_do_not_stop() -> None:
    decision = decide_review(
        is_first_assessment=False,
        successful_passes=4,
        previous_interval=30,
        latest_score=93,
        consecutive_high=4,
    )

    assert decision.interval_days > 30
    assert decision.interval_days <= 90
    assert "不会永久" in decision.reason


def test_low_score_shrinks_interval() -> None:
    decision = decide_review(
        is_first_assessment=False,
        successful_passes=3,
        previous_interval=14,
        latest_score=45,
        consecutive_high=2,
    )

    assert decision.interval_days == 1
    assert decision.successful_passes == 3
    assert decision.consecutive_high == 0
    assert decision.result == "fail"


def test_mid_score_uses_two_days() -> None:
    decision = decide_review(
        is_first_assessment=False,
        successful_passes=2,
        previous_interval=7,
        latest_score=68,
        consecutive_high=0,
    )

    assert decision.interval_days == 2
    assert decision.successful_passes == 2
    assert decision.result == "partial"


def test_next_day_uses_calendar_days() -> None:
    assert next_review_day(date(2026, 11, 3), 1) == date(2026, 11, 4)


def test_overdue_low_mastery_is_high_risk_with_reason() -> None:
    level, reason = forgetting_risk(
        mastery=45,
        latest_score=58,
        days_since_quiz=1,
        overdue_days=2,
        recent_low_count=2,
    )

    assert level == "high"
    assert "45" in reason
    assert "58" in reason
    assert "尽快复习" in reason


def test_stable_recent_point_is_low_risk() -> None:
    level, reason = forgetting_risk(
        mastery=95,
        latest_score=96,
        days_since_quiz=2,
        overdue_days=0,
        recent_low_count=0,
    )

    assert level == "low"
    assert reason
