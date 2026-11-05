"""把校验错误整理成前端可以直接展示的中文说明。"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

FIELD_LABELS = {
    "title": "学习目标名称",
    "description": "目标描述",
    "target_date": "预计完成日期",
    "daily_minutes": "每日学习时间",
    "status": "状态",
    "username": "用户名",
    "email": "邮箱",
    "password": "密码",
    "nickname": "昵称",
    "avatar": "头像",
}


def _message(error: dict) -> str:
    field = ""
    for item in reversed(error.get("loc", [])):
        if item != "body":
            field = str(item)
            break
    label = FIELD_LABELS.get(field, "请求内容")
    error_type = error.get("type", "")
    fixed = {
        "missing": f"{label}不能为空",
        "int_parsing": f"{label}需要填写整数",
        "int_type": f"{label}需要填写整数",
        "greater_than_equal": f"{label}需要在 1 到 720 分钟之间",
        "less_than_equal": f"{label}需要在 1 到 720 分钟之间",
        "literal_error": "状态只能是 active、paused 或 completed",
    }
    if error_type in fixed:
        return fixed[error_type]
    if error_type.startswith("date"):
        return f"{label}格式应为 YYYY-MM-DD"

    msg = str(error.get("msg", "填写内容不正确"))
    prefix = "Value error, "
    if msg.startswith(prefix):
        msg = msg.removeprefix(prefix)
    return f"{label}：{msg}"


async def validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    detail = "；".join(_message(error) for error in exc.errors())
    return JSONResponse(status_code=422, content={"detail": detail or "填写内容不正确"})
