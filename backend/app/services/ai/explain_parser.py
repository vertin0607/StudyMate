"""校验题目讲解和知识点讲解。未通过校验的内容不能入库。"""

from app.services.ai.errors import AIError
from app.services.ai.quiz_parser import _object, _text
from app.services.tutor_math import normalize_tutor_math


def parse_question_explain(raw: str) -> str:
    data = _object(raw)
    sections = [
        ("考查知识点", _text(data.get("focus"), "考查知识点", 8, 800)),
        ("正确答案", _text(data.get("correct_answer"), "正确答案", 1, 800)),
        ("详细解析", _text(data.get("walkthrough"), "详细解析", 8, 2500)),
        ("错误分析", _text(data.get("error_analysis"), "错误分析", 4, 2000)),
        ("知识拓展", _text(data.get("extension"), "知识拓展", 8, 1500)),
    ]
    return _markdown(sections)


def parse_knowledge_explain(raw: str) -> str:
    data = _object(raw)
    sections = [
        ("这个知识点是什么", _text(data.get("definition"), "定义", 8, 1500)),
        ("为什么需要学习它", _text(data.get("why"), "学习原因", 8, 1200)),
        ("核心概念和原理", _text(data.get("principles"), "原理", 8, 2000)),
        ("关键步骤或执行过程", _text(data.get("process"), "过程", 8, 2000)),
        ("示例", _text(data.get("examples"), "示例", 8, 2000)),
        ("常见错误和容易混淆的地方", _text(data.get("pitfalls"), "易错点", 8, 1500)),
        ("重点总结", _text(data.get("summary"), "总结", 8, 800)),
    ]
    return _markdown(sections)


def parse_followup(raw: str) -> str:
    data = _object(raw)
    reply = _text(data.get("reply"), "追问回复", 8, 8000)
    text = normalize_tutor_math(reply)
    if not text.strip():
        raise AIError("追问回复缺少正文", status_code=502)
    return text


def _markdown(sections: list[tuple[str, str]]) -> str:
    parts = [f"**{title}**\n\n{normalize_tutor_math(body)}" for title, body in sections]
    text = "\n\n".join(parts)
    if len(text) > 8000:
        text = text[:8000].rstrip()
    return text
