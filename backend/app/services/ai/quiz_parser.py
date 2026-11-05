"""校验试卷和简答评分。未通过校验的内容不能入库。"""

import json
import re
from dataclasses import dataclass, field

from app.services.ai.errors import AIError

QUESTION_TYPES = {"single", "multiple", "true_false", "short", "scenario"}
DIFFICULTIES = {"basic", "medium", "advanced"}
SUBJECTIVE = {"short", "scenario"}


@dataclass
class QuestionDraft:
    question_type: str
    difficulty: str
    stem: str
    options: list[dict[str, str]]
    correct_answer: str
    explanation: str
    knowledge_point_id: int


@dataclass
class QuizDraft:
    title: str
    questions: list[QuestionDraft] = field(default_factory=list)


@dataclass
class GradeDraft:
    question_id: int
    score: int
    correct: bool
    error_reason: str
    suggestion: str
    reference_answer: str


def parse_quiz(raw: str, allowed_ids: set[int], focus_id: int | None) -> QuizDraft:
    data = _object(raw)
    title = _text(data.get("title"), "检测标题", 4, 120)
    raw_questions = data.get("questions")
    if not isinstance(raw_questions, list) or len(raw_questions) != 5:
        raise AIError("一次检测需要正好 5 道题", status_code=502)

    questions: list[QuestionDraft] = []
    stems: set[str] = set()
    for item in raw_questions:
        if not isinstance(item, dict):
            raise AIError("题目格式不正确", status_code=502)
        question_type = item.get("question_type")
        difficulty = item.get("difficulty")
        if question_type not in QUESTION_TYPES:
            raise AIError("题目类型不受支持", status_code=502)
        if difficulty not in DIFFICULTIES:
            raise AIError("题目难度不受支持", status_code=502)
        point_id = _point_id(item.get("knowledge_point_id"), allowed_ids)
        stem = _text(item.get("stem"), "题干", 8, 2000)
        if stem in stems:
            raise AIError("检测里有重复题目", status_code=502)
        stems.add(stem)
        options = _options(item.get("options"), question_type)
        raw_answer = _raw_answer(item.get("correct_answer"))
        question_type = _effective_type(question_type, raw_answer, options)
        answer = _answer(raw_answer, question_type, options)
        explanation = _text(item.get("explanation"), "答案解析", 8, 2000)
        questions.append(
            QuestionDraft(question_type, difficulty, stem, options, answer, explanation, point_id)
        )

    advanced = sum(1 for item in questions if item.difficulty == "advanced")
    approachable = sum(1 for item in questions if item.difficulty in {"basic", "medium"})
    if advanced > 1 or approachable < 3:
        raise AIError("检测应以基础和中等题为主，提高题最多 1 道", status_code=502)
    if focus_id is not None and sum(1 for item in questions if item.knowledge_point_id == focus_id) < 3:
        raise AIError("检测应主要覆盖当前学习任务的知识点", status_code=502)
    return QuizDraft(title, questions)


def parse_grades(raw: str, expected_ids: set[int]) -> list[GradeDraft]:
    data = _object(raw)
    raw_grades = data.get("grades")
    if not isinstance(raw_grades, list):
        raise AIError("评分结果格式不正确", status_code=502)
    grades: list[GradeDraft] = []
    seen: set[int] = set()
    for item in raw_grades:
        if not isinstance(item, dict):
            raise AIError("评分结果格式不正确", status_code=502)
        question_id = item.get("question_id")
        if isinstance(question_id, bool) or not isinstance(question_id, int) or question_id not in expected_ids:
            raise AIError("评分结果包含未知题目", status_code=502)
        if question_id in seen:
            raise AIError("评分结果有重复题目", status_code=502)
        seen.add(question_id)
        score = _score(item.get("score"))
        if item.get("max_score") not in {100, 100.0}:
            raise AIError("简答题满分必须是 100", status_code=502)
        correct = item.get("correct")
        if not isinstance(correct, bool) or correct != (score >= 60):
            raise AIError("评分的正误判断和分数不一致", status_code=502)
        error_reason = item.get("error_reason", "")
        if not isinstance(error_reason, str):
            raise AIError("错误原因格式不正确", status_code=502)
        error_reason = error_reason.strip()
        if not correct and len(error_reason) < 4:
            raise AIError("答错时需要说明错误原因", status_code=502)
        suggestion = _text(item.get("suggestion"), "改进建议", 4, 2000)
        reference = _text(item.get("reference_answer"), "参考答案", 8, 2000)
        grades.append(GradeDraft(question_id, score, correct, error_reason, suggestion, reference))
    if seen != expected_ids:
        raise AIError("还有简答题没有评分", status_code=502)
    return grades


def normalize_answer(question_type: str, value: str) -> str:
    text = value.strip()
    if question_type == "multiple":
        text = text.replace("，", ",").replace("、", ",").replace(" ", ",")
        keys = [part.strip().upper() for part in text.split(",") if part.strip()]
        if len(keys) == 1 and keys[0].isalpha() and 2 <= len(keys[0]) <= 6:
            keys = list(keys[0])
        return ",".join(sorted(set(keys)))
    if question_type in {"single", "true_false"}:
        return text.upper()
    return text


def answers_match(question_type: str, expected: str, actual: str) -> bool:
    if question_type in SUBJECTIVE:
        return False
    return normalize_answer(question_type, expected) == normalize_answer(question_type, actual) and bool(actual.strip())


def _options(value: object, question_type: str) -> list[dict[str, str]]:
    if question_type in SUBJECTIVE:
        return []
    if question_type == "true_false":
        return [{"key": "T", "text": "正确"}, {"key": "F", "text": "错误"}]
    if not isinstance(value, list) or not 2 <= len(value) <= 6:
        raise AIError("选择题需要提供选项", status_code=502)
    options: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise AIError("选项格式不正确", status_code=502)
        key = str(item.get("key", "")).strip().upper()
        text = str(item.get("text", "")).strip()
        if not key or len(text) < 1 or key in seen:
            raise AIError("选项需要有不重复的编号和内容", status_code=502)
        seen.add(key)
        options.append({"key": key, "text": text[:500]})
    if question_type == "single" and len(options) < 3:
        raise AIError("单选题至少需要 3 个选项", status_code=502)
    return options


def _raw_answer(value: object) -> object:
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return ",".join(parts)
    return value


def _effective_type(question_type: str, correct_answer: object, options: list[dict[str, str]]) -> str:
    if question_type != "multiple" or not isinstance(correct_answer, str):
        return question_type
    selected = [key for key in normalize_answer("multiple", correct_answer).split(",") if key]
    keys = {item["key"] for item in options}
    if len(selected) == 1 and selected[0] in keys:
        return "single"
    return question_type


def _point_id(value: object, allowed_ids: set[int]) -> int:
    if isinstance(value, bool):
        raise AIError("题目必须对应本次学习中的知识点", status_code=502)
    if isinstance(value, int):
        point_id = value
    elif isinstance(value, float) and value.is_integer():
        point_id = int(value)
    elif isinstance(value, str) and value.strip().isdigit():
        point_id = int(value.strip())
    else:
        raise AIError("题目必须对应本次学习中的知识点", status_code=502)
    if point_id not in allowed_ids:
        raise AIError("题目必须对应本次学习中的知识点", status_code=502)
    return point_id


def _answer(value: object, question_type: str, options: list[dict[str, str]]) -> str:
    if not isinstance(value, str):
        raise AIError("正确答案不能为空", status_code=502)
    answer = normalize_answer(question_type, value)
    if question_type == "true_false":
        lowered = answer.casefold()
        if lowered in {"t", "true", "正确", "对"}:
            answer = "T"
        elif lowered in {"f", "false", "错误", "错"}:
            answer = "F"
    keys = {item["key"] for item in options}
    if question_type == "true_false" and answer not in {"T", "F"}:
        raise AIError("判断题答案只能是 T 或 F", status_code=502)
    if question_type == "single" and answer not in keys:
        raise AIError("单选题答案必须是其中一个选项", status_code=502)
    if question_type == "multiple":
        selected = [key for key in answer.split(",") if key]
        if len(selected) < 2 or any(key not in keys for key in selected):
            raise AIError("多选题至少要有两个正确选项", status_code=502)
    if question_type in SUBJECTIVE and len(answer) < 8:
        raise AIError("简答题需要写出参考要点", status_code=502)
    return answer


def _object(raw: str) -> dict:
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


def _score(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AIError("分数必须是整数", status_code=502)
    if isinstance(value, float) and not value.is_integer():
        raise AIError("分数必须是整数", status_code=502)
    score = int(value)
    if score < 0 or score > 100:
        raise AIError("分数需要在 0 到 100 之间", status_code=502)
    return score
