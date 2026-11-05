"""FastAPI 入口。健康检查和学习目标接口在这里汇总。"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.deps import get_current_user, require_mutation_csrf
from app.errors import validation_exception_handler
from app.routers.ai import router as ai_router
from app.routers.auth import router as auth_router
from app.routers.analytics import router as analytics_router
from app.routers.goals import router as goals_router
from app.routers.health import router as health_router
from app.routers.knowledge import router as knowledge_router
from app.routers.plans import router as plans_router
from app.routers.practice import router as practice_router
from app.routers.problems import router as problems_router
from app.routers.quizzes import router as quizzes_router
from app.routers.recommendations import router as recommendations_router
from app.routers.reviews import router as reviews_router
from app.routers.submissions import router as submissions_router
from app.routers.tasks import router as tasks_router
from app.routers.topic_links import router as topic_links_router
from app.routers.tutor import router as tutor_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 启动时建表。已有的学习记录会保留，不会被清空。
    init_db()
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# 允许本地前端页面访问后端。密钥仍然只留在后端。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

business = [Depends(get_current_user), Depends(require_mutation_csrf)]

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(goals_router, prefix="/api", dependencies=business)
app.include_router(ai_router, prefix="/api", dependencies=business)
app.include_router(plans_router, prefix="/api", dependencies=business)
app.include_router(tasks_router, prefix="/api", dependencies=business)
app.include_router(quizzes_router, prefix="/api", dependencies=business)
app.include_router(reviews_router, prefix="/api", dependencies=business)
app.include_router(knowledge_router, prefix="/api", dependencies=business)
app.include_router(analytics_router, prefix="/api", dependencies=business)
app.include_router(recommendations_router, prefix="/api", dependencies=business)
app.include_router(topic_links_router, prefix="/api", dependencies=business)
app.include_router(tutor_router, prefix="/api", dependencies=business)
app.include_router(problems_router, prefix="/api", dependencies=business)
app.include_router(practice_router, prefix="/api", dependencies=business)
app.include_router(submissions_router, prefix="/api", dependencies=business)
