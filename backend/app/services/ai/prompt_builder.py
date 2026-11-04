"""把学习目标和历史记录整理成规划提示词。"""

import json
from datetime import date
from pathlib import Path

from app.models.goal import LearningGoal

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "planner.txt"
DECLIP_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "declip_plan.txt"
MAX_ATTEMPTS = 2


def load_planner_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def load_goal_prompt(goal: LearningGoal) -> str:
    prompt = load_planner_prompt()
    if "declip" in goal.title.casefold():
        prompt += "\n\n" + DECLIP_PROMPT_PATH.read_text(encoding="utf-8")
    return prompt


def build_messages(
    goal: LearningGoal,
    plan_date: date,
    context: dict,
    instruction: str = "",
    previous_plan: dict | None = None,
) -> list[dict[str, str]]:
    payload = {
        "plan_date": plan_date.isoformat(),
        "goal": {
            "title": goal.title,
            "description": goal.description,
            "daily_minutes": goal.daily_minutes,
            "target_date": goal.target_date.isoformat(),
        },
        "knowledge_points": context["knowledge_points"],
        "recent_plans": context["recent_plans"],
        "quiz_results": context["quiz_results"],
        "due_reviews": context.get("due_reviews", []),
        "instruction": instruction,
        "previous_plan": previous_plan,
    }
    return [
        {"role": "system", "content": load_goal_prompt(goal)},
        {
            "role": "user",
            "content": "请根据下面的学习档案生成今天的计划：\n" + json.dumps(payload, ensure_ascii=False),
        },
    ]


def build_repair_messages(original: list[dict[str, str]], raw: str, error: str) -> list[dict[str, str]]:
    """只再请求一次，把校验错误交回模型。"""
    return [
        *original,
        {"role": "assistant", "content": raw},
        {"role": "user", "content": f"上次的 JSON 没有通过校验：{error}。请只重新返回修正后的 JSON。"},
    ]
