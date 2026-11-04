"""DeCLIP 的长路线只加给这个目标，其他目标仍用通用计划规则。"""

from datetime import date

from app.models.goal import LearningGoal
from app.services.ai.prompt_builder import build_messages


def _goal(title: str) -> LearningGoal:
    return LearningGoal(
        user_id=1,
        title=title,
        description="用于检查提示词",
        target_date=date(2026, 11, 30),
        daily_minutes=25,
    )


def _messages(title: str) -> str:
    context = {"knowledge_points": [], "recent_plans": [], "quiz_results": [], "due_reviews": []}
    messages = build_messages(_goal(title), date(2026, 11, 3), context)
    return messages[0]["content"]


def test_declip_prompt_is_added_only_for_that_goal() -> None:
    declip = _messages("DeCLIP研究学习")
    other = _messages("数据结构")
    assert "Class-specific Prompt" in declip
    assert "learning_band" in declip
    assert "Class-specific Prompt" not in other
    assert "每天只解决一个主要知识点" in other
