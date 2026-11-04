"""DeepSeek 调用和计划校验的错误。消息可以返回给用户，不能包含密钥。"""


class AIError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def redact(text: str, secret: str) -> str:
    """日志和接口说明里都不能出现完整密钥。"""
    if secret and secret in text:
        return text.replace(secret, "***")
    return text
