"""校验模型返回的计划。未通过校验的内容不能写入数据库。"""

import json
import re
from dataclasses import dataclass

from app.services.ai.errors import AIError

TASK_TYPES = {"learn", "practice", "review", "quiz"}


@dataclass
class TaskDraft:
    title: str
    description: str
    task_type: str
    estimated_minutes: int
    knowledge_point: str


@dataclass
class PlanDraft:
    title: str
    description: str
    total_minutes: int
    tasks: list[TaskDraft]


def parse_plan(raw: str, daily_limit: int, mastered_names: set[str]) -> PlanDraft:
    data = _load_json(raw)
    title = _text(data.get("plan_title"), "计划标题", 4, 120)
    description = _text(data.get("plan_description"), "计划说明", 8, 2000)
    total_minutes = _minutes(data.get("total_minutes"), "总时长")
    if total_minutes > daily_limit:
        raise AIError(f"计划总时长不能超过每天 {daily_limit} 分钟", status_code=502)

    raw_tasks = data.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise AIError("计划里至少要有一项具体任务", status_code=502)

    tasks: list[TaskDraft] = []
    for item in raw_tasks:
        if not isinstance(item, dict):
            raise AIError("任务格式不正确", status_code=502)
        task_type = item.get("task_type")
        if task_type not in TASK_TYPES:
            raise AIError("任务类型只能是 learn、practice、review 或 quiz", status_code=502)
        point = _text(item.get("knowledge_point"), "知识点", 1, 80)
        if point in mastered_names:
            raise AIError(f"知识点「{point}」已经掌握，不应再次安排", status_code=502)
        tasks.append(
            TaskDraft(
                title=_text(item.get("title"), "任务标题", 2, 120),
                description=_text(item.get("description"), "任务说明", 8, 2000),
                task_type=task_type,
                estimated_minutes=_minutes(item.get("estimated_minutes"), "任务时长"),
                knowledge_point=point,
            )
        )

    if sum(task.estimated_minutes for task in tasks) != total_minutes:
        raise AIError("各项任务时长之和必须等于计划总时长", status_code=502)
    return PlanDraft(title=title, description=description, total_minutes=total_minutes, tasks=tasks)


def _load_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIError("DeepSeek 返回的不是合法 JSON", status_code=502) from exc
    if not isinstance(data, dict):
        raise AIError("DeepSeek 返回的 JSON 必须是对象", status_code=502)
    return data


def _text(value: object, label: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise AIError(f"{label}不能为空", status_code=502)
    text = value.strip()
    if len(text) < minimum:
        raise AIError(f"{label}需要写清楚具体内容", status_code=502)
    return text[:maximum]


def _minutes(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AIError(f"{label}必须是整数", status_code=502)
    if isinstance(value, float) and not value.is_integer():
        raise AIError(f"{label}必须是整数", status_code=502)
    minutes = int(value)
    if minutes < 1 or minutes > 720:
        raise AIError(f"{label}需要在 1 到 720 分钟之间", status_code=502)
    return minutes
