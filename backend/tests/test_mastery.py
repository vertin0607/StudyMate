"""掌握度算法不访问模型和数据库。"""

from app.services.mastery import next_mastery, result_label


def test_first_high_score_is_not_proficient() -> None:
    level, status, reason = next_mastery(None, [], 95)

    assert level == 74
    assert status == "improving"
    assert "首次" in reason


def test_second_stable_high_score_becomes_proficient() -> None:
    level, status, reason = next_mastery(74, [95], 96)

    assert level == 90
    assert status == "proficient"
    assert "连续" in reason


def test_recent_low_score_lowers_mastery() -> None:
    level, status, _reason = next_mastery(80, [85], 40)

    assert level < 60
    assert status == "needs_review"


def test_result_label_is_separate_from_mastery() -> None:
    assert result_label(95) == "掌握良好"
    assert result_label(64) == "需要巩固"
    assert result_label(40) == "建议重新学习"
