"""整理导师回复里的公式写法。不判断推导对错，也不改动掌握度。"""

import re

_FENCE = re.compile(r"```[\s\S]*?```")
_DISPLAY = re.compile(r"\\\[([\s\S]+?)\\\]")
_INLINE = re.compile(r"\\\(([\s\S]+?)\\\)")
_MATH = re.compile(r"\$\$[\s\S]+?\$\$|\$[^$\n]+?\$")


def normalize_tutor_math(text: str) -> str:
    """把公式定界符收成 $ 和 $$，并去掉紧挨着的重复公式。代码块保持原样。"""
    pieces: list[str] = []
    last = 0
    for match in _FENCE.finditer(text):
        pieces.append(_normalize_prose(text[last : match.start()]))
        pieces.append(match.group(0))
        last = match.end()
    pieces.append(_normalize_prose(text[last:]))
    return "".join(pieces)


def _normalize_prose(text: str) -> str:
    text = _DISPLAY.sub(lambda match: "$$" + match.group(1).strip() + "$$", text)
    text = _INLINE.sub(lambda match: "$" + match.group(1).strip() + "$", text)
    return _collapse_repeats(_trim_math(text))


def _trim_math(text: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(text):
        if text.startswith("$$", index):
            end = text.find("$$", index + 2)
            if end == -1:
                result.append(text[index:])
                break
            result.append("\n\n$$\n" + text[index + 2 : end].strip() + "\n$$\n\n")
            index = end + 2
            continue
        if text[index] == "$":
            end = text.find("$", index + 1)
            if end == -1 or "\n" in text[index + 1 : end]:
                result.append("$")
                index += 1
                continue
            inner = text[index + 1 : end].strip()
            if not inner:
                result.append("$")
                index += 1
                continue
            result.append("$" + inner + "$")
            index = end + 1
            continue
        result.append(text[index])
        index += 1
    return "".join(result)


def _collapse_repeats(text: str) -> str:
    matches = list(_MATH.finditer(text))
    if not matches:
        return text
    pieces: list[str] = []
    last = 0
    previous: str | None = None
    for match in matches:
        gap = text[last : match.start()]
        body = _body(match.group(0))
        if previous is not None and previous == body and gap.strip() == "":
            last = match.end()
            continue
        pieces.append(gap)
        pieces.append(match.group(0))
        previous = body
        last = match.end()
    pieces.append(text[last:])
    return "".join(pieces)


def _body(formula: str) -> str:
    if formula.startswith("$$"):
        return formula[2:-2].strip()
    return formula[1:-1].strip()
