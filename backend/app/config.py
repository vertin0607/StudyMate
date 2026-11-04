"""读取运行配置。密钥只来自环境变量，不写进代码。"""

import os
from pathlib import Path

from dotenv import load_dotenv

# backend 目录。无论从哪个工作目录启动，都读取这一份配置。
BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def resolve_database_path(raw: str | None = None) -> Path:
    """把数据库路径固定到 backend 目录下，避免写到系统临时目录。"""
    value = raw if raw is not None else os.getenv("DATABASE_PATH", "data/studymate.db")
    path = Path(value)
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return path.resolve()


class Settings:
    """服务名称、端口、跨域来源和 SQLite 文件位置。"""

    app_name: str = "StudyMate"
    app_version: str = "0.9.0"
    host: str = os.getenv("APP_HOST", "127.0.0.1")
    port: int = int(os.getenv("APP_PORT", "8000"))
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]
    database_path: Path = resolve_database_path()
    # 模型名称和密钥只从环境变量读取，调用处不再写死。
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "").strip()
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()
    deepseek_timeout: float = float(os.getenv("DEEPSEEK_TIMEOUT", "45"))


settings = Settings()
