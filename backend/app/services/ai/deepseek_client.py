"""通过 OpenAI SDK 调用 DeepSeek。前端不能直接使用这里的配置。"""

import logging

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from app.config import settings
from app.services.ai.errors import AIError, redact

logger = logging.getLogger(__name__)


def complete_json(messages: list[dict[str, str]], *, max_tokens: int = 1200) -> str:
    """发送一次对话，返回模型原文。调用方负责校验 JSON。"""
    secret = settings.deepseek_api_key
    if not secret:
        raise AIError("未配置 DEEPSEEK_API_KEY", status_code=503)
    if not settings.deepseek_model:
        raise AIError("未配置 DEEPSEEK_MODEL", status_code=503)

    client = OpenAI(
        api_key=secret,
        base_url=settings.deepseek_base_url,
        timeout=settings.deepseek_timeout,
    )
    # 只记录模型名称，不记录密钥和完整提示词。
    logger.info("调用 DeepSeek，模型 %s", settings.deepseek_model)
    try:
        completion = client.chat.completions.create(
            model=settings.deepseek_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=max_tokens,
        )
    except APITimeoutError as exc:
        raise AIError("DeepSeek 请求超时，请稍后重试", status_code=504) from exc
    except APIConnectionError as exc:
        raise AIError("无法连接 DeepSeek，请检查网络后重试", status_code=502) from exc
    except APIStatusError as exc:
        if exc.status_code in {401, 403}:
            raise AIError("DeepSeek 密钥无效或没有权限", status_code=502) from exc
        if exc.status_code in {402, 429}:
            raise AIError("DeepSeek 额度不足或请求过于频繁", status_code=429) from exc
        logger.warning("DeepSeek 返回状态 %s", exc.status_code)
        raise AIError("DeepSeek 调用失败，请稍后重试", status_code=502) from exc
    except Exception as exc:
        logger.exception("DeepSeek 调用出现未预期错误：%s", redact(str(exc), secret))
        raise AIError("DeepSeek 调用失败，请稍后重试", status_code=502) from exc

    content = completion.choices[0].message.content if completion.choices else None
    if not content or not content.strip():
        raise AIError("DeepSeek 没有返回内容", status_code=502)
    return content


def ping() -> None:
    """用一次很短的请求确认密钥和模型可用。"""
    complete_json(
        [
            {"role": "system", "content": "只返回 JSON。"},
            {"role": "user", "content": '{"ping": true}'},
        ]
    )
