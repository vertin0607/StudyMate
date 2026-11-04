"""DeepSeek 连通性检查。响应里不会包含密钥。"""

from fastapi import APIRouter

from app.config import settings
from app.services.ai.deepseek_client import ping
from app.services.ai.errors import AIError

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/test-connection")
def test_connection() -> dict:
    model = settings.deepseek_model
    try:
        ping()
    except AIError as exc:
        return {"ok": False, "model": model, "error": exc.message}
    return {"ok": True, "model": model, "error": None}
