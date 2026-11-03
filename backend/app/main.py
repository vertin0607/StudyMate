"""FastAPI 入口。第一阶段只提供健康检查。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.health import router as health_router

app = FastAPI(title=settings.app_name, version=settings.app_version)

# 允许本地前端页面访问后端。密钥仍然只留在后端。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
