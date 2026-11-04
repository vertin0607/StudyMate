"""SQLite 连接。数据库文件位置来自配置，不放在临时目录。"""

from collections.abc import Generator

from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# 每个请求使用自己的 Session。关闭同线程检查，避免 FastAPI 线程池报错。
engine = create_engine(
    f"sqlite:///{settings.database_path.as_posix()}",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db() -> None:
    """创建数据目录和表，并保证本地用户存在。"""
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    # 先导入模型，再创建表。
    import app.models  # noqa: F401

    try:
        SQLModel.metadata.create_all(engine)
    except OperationalError:
        # 开发时热重载可能让两个进程同时建表。表已经存在时再检查一次即可。
        SQLModel.metadata.create_all(engine)
    with engine.begin() as connection:
        # 同一目标同一天只能有一份 status=active 的计划，历史版本仍保留。
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_active_plan_per_goal_date "
            "ON study_plans(goal_id, plan_date) WHERE status = 'active'"
        )
    from app.services.goal_service import ensure_local_user

    with Session(engine) as session:
        ensure_local_user(session)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
