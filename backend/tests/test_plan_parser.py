"""计划校验不访问网络。"""

import json

import pytest

from app.services.ai.errors import AIError
from app.services.ai.response_parser import parse_plan


def sample_plan() -> dict:
    return {
        "plan_title": "用下山理解梯度方向",
        "plan_description": "今天只用一个很小的数字例子，看参数为什么要朝梯度反方向更新。",
        "total_minutes": 25,
        "tasks": [
            {
                "title": "用走山路理解梯度",
                "description": "先看每一步为什么要朝更低的方向走，再对应到参数更新。",
                "task_type": "learn",
                "estimated_minutes": 10,
                "knowledge_point": "梯度",
            },
            {
                "title": "手算一次参数更新",
                "description": "用 w = w - 学习率 × 梯度，计算一组很小的数字。",
                "task_type": "practice",
                "estimated_minutes": 10,
                "knowledge_point": "参数更新",
            },
            {
                "title": "合上笔记复述例子",
                "description": "不看公式，说出学习率和梯度分别改变了哪一个数。",
                "task_type": "quiz",
                "estimated_minutes": 5,
                "knowledge_point": "梯度",
            },
        ],
    }


def test_parse_plan_accepts_consistent_minutes() -> None:
    draft = parse_plan(json.dumps(sample_plan()), daily_limit=25, mastered_names=set())

    assert draft.total_minutes == 25
    assert len(draft.tasks) == 3


def test_parse_plan_rejects_minute_mismatch() -> None:
    payload = sample_plan()
    payload["total_minutes"] = 20
    with pytest.raises(AIError, match="之和"):
        parse_plan(json.dumps(payload), daily_limit=25, mastered_names=set())


def test_parse_plan_rejects_over_daily_limit() -> None:
    payload = sample_plan()
    payload["total_minutes"] = 30
    payload["tasks"][0]["estimated_minutes"] = 15
    with pytest.raises(AIError, match="不能超过"):
        parse_plan(json.dumps(payload), daily_limit=25, mastered_names=set())


def test_parse_plan_rejects_mastered_point() -> None:
    with pytest.raises(AIError, match="已经掌握"):
        parse_plan(json.dumps(sample_plan()), daily_limit=25, mastered_names={"梯度"})


def test_parse_plan_rejects_vague_description() -> None:
    payload = sample_plan()
    payload["tasks"][0]["description"] = "学习"
    with pytest.raises(AIError, match="任务说明"):
        parse_plan(json.dumps(payload), daily_limit=25, mastered_names=set())
