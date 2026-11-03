"""读取运行配置。密钥只来自环境变量，不写进代码。"""

import os
from pathlib import Path

from dotenv import load_dotenv

# backend 目录。无论从哪个工作目录启动，都读取这一份配置。
BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


class Settings:
    """第一阶段只需要服务名称、端口和允许访问的前端地址。"""

    app_name: str = "StudyMate"
    app_version: str = "0.1.0"
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


settings = Settings()
