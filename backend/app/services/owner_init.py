"""把 users.id=1 原地初始化为正式账号，并删除 users.id=2 及其关联数据。

不新建用户，不把 id=2 的业务数据并入 id=1，也不删除 id=1 的历史数据。
外键都是 ON DELETE NO ACTION，因此按子表到父表的顺序显式删除。
"""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from app.schemas.auth import RegisterRequest
from app.services.auth_service import hash_password

LOCAL_USERNAME = "local"
HISTORICAL_USER_ID = 1
REMOVED_USER_ID = 2
TARGET_USERNAME = "夜临"

_USER_ID_TABLES = (
    "learning_goals",
    "problem_topics",
    "problems",
    "problem_notes",
    "problem_code_drafts",
    "problem_submissions",
    "problem_learning_status",
    "problem_practice_records",
    "problem_wrong_records",
    "problem_judge_results",
    "training_recommendations",
    "tutor_sessions",
    "topic_knowledge_links",
    "user_sessions",
)

# 只检查已经存在的表。子资源没有 user_id 时，核对它和父记录是否属于同一用户。
_RELATION_CHECKS = (
    ("knowledge_points", "SELECT COUNT(*) FROM knowledge_points WHERE goal_id NOT IN (SELECT id FROM learning_goals)"),
    ("study_plans", "SELECT COUNT(*) FROM study_plans WHERE goal_id NOT IN (SELECT id FROM learning_goals)"),
    ("study_tasks", "SELECT COUNT(*) FROM study_tasks WHERE plan_id NOT IN (SELECT id FROM study_plans)"),
    (
        "study_tasks",
        """
        SELECT COUNT(*) FROM study_tasks AS child
        WHERE child.knowledge_point_id IS NOT NULL
          AND (SELECT goal_id FROM knowledge_points WHERE id = child.knowledge_point_id)
              != (SELECT goal_id FROM study_plans WHERE id = child.plan_id)
        """,
    ),
    ("plan_revisions", "SELECT COUNT(*) FROM plan_revisions WHERE plan_id NOT IN (SELECT id FROM study_plans)"),
    ("quizzes", "SELECT COUNT(*) FROM quizzes WHERE goal_id NOT IN (SELECT id FROM learning_goals)"),
    ("quiz_questions", "SELECT COUNT(*) FROM quiz_questions WHERE quiz_id NOT IN (SELECT id FROM quizzes)"),
    ("quiz_answers", "SELECT COUNT(*) FROM quiz_answers WHERE question_id NOT IN (SELECT id FROM quiz_questions)"),
    (
        "knowledge_mastery_events",
        "SELECT COUNT(*) FROM knowledge_mastery_events WHERE knowledge_point_id NOT IN (SELECT id FROM knowledge_points)",
    ),
    (
        "review_schedules",
        """
        SELECT COUNT(*) FROM review_schedules
        WHERE goal_id NOT IN (SELECT id FROM learning_goals)
           OR knowledge_point_id NOT IN (SELECT id FROM knowledge_points)
        """,
    ),
    ("review_records", "SELECT COUNT(*) FROM review_records WHERE schedule_id NOT IN (SELECT id FROM review_schedules)"),
    ("tutor_messages", "SELECT COUNT(*) FROM tutor_messages WHERE session_id NOT IN (SELECT id FROM tutor_sessions)"),
    (
        "tutor_sessions",
        """
        SELECT COUNT(*) FROM tutor_sessions AS child
        WHERE child.goal_id IS NOT NULL
          AND child.user_id != (SELECT user_id FROM learning_goals WHERE id = child.goal_id)
        """,
    ),
    ("problem_test_cases", "SELECT COUNT(*) FROM problem_test_cases WHERE problem_id NOT IN (SELECT id FROM problems)"),
    (
        "problem_topic_links",
        """
        SELECT COUNT(*) FROM problem_topic_links
        WHERE problem_id NOT IN (SELECT id FROM problems)
           OR topic_id NOT IN (SELECT id FROM problem_topics)
        """,
    ),
    (
        "problem_topic_links",
        """
        SELECT COUNT(*) FROM problem_topic_links AS child
        WHERE (SELECT user_id FROM problems WHERE id = child.problem_id)
           != (SELECT user_id FROM problem_topics WHERE id = child.topic_id)
        """,
    ),
    (
        "problem_submissions",
        """
        SELECT COUNT(*) FROM problem_submissions AS child
        WHERE child.problem_id NOT IN (SELECT id FROM problems)
           OR child.user_id != (SELECT user_id FROM problems WHERE id = child.problem_id)
        """,
    ),
    (
        "problem_code_drafts",
        """
        SELECT COUNT(*) FROM problem_code_drafts AS child
        WHERE child.user_id != (SELECT user_id FROM problems WHERE id = child.problem_id)
        """,
    ),
    (
        "problem_judge_results",
        """
        SELECT COUNT(*) FROM problem_judge_results AS child
        WHERE child.user_id != (SELECT user_id FROM problem_submissions WHERE id = child.submission_id)
           OR child.problem_id != (SELECT problem_id FROM problem_submissions WHERE id = child.submission_id)
        """,
    ),
    (
        "problem_judge_case_results",
        """
        SELECT COUNT(*) FROM problem_judge_case_results AS child
        WHERE (SELECT problem_id FROM problem_test_cases WHERE id = child.test_case_id)
           != (SELECT problem_id FROM problem_judge_results WHERE id = child.judge_result_id)
        """,
    ),
    (
        "topic_knowledge_links",
        """
        SELECT COUNT(*) FROM topic_knowledge_links AS child
        WHERE child.user_id != (SELECT user_id FROM problem_topics WHERE id = child.problem_topic_id)
           OR child.user_id != (
                SELECT learning_goals.user_id FROM knowledge_points
                JOIN learning_goals ON learning_goals.id = knowledge_points.goal_id
                WHERE knowledge_points.id = child.knowledge_point_id
           )
        """,
    ),
    (
        "problem_notes",
        """
        SELECT COUNT(*) FROM problem_notes AS child
        WHERE child.user_id != (SELECT user_id FROM problems WHERE id = child.problem_id)
        """,
    ),
    (
        "problem_learning_status",
        """
        SELECT COUNT(*) FROM problem_learning_status AS child
        WHERE child.user_id != (SELECT user_id FROM problems WHERE id = child.problem_id)
        """,
    ),
    (
        "problem_practice_records",
        """
        SELECT COUNT(*) FROM problem_practice_records AS child
        WHERE child.user_id != (SELECT user_id FROM problems WHERE id = child.problem_id)
        """,
    ),
    (
        "problem_wrong_records",
        """
        SELECT COUNT(*) FROM problem_wrong_records AS child
        WHERE child.user_id != (SELECT user_id FROM problems WHERE id = child.problem_id)
        """,
    ),
    (
        "quiz_questions",
        """
        SELECT COUNT(*) FROM quiz_questions AS child
        JOIN quizzes ON quizzes.id = child.quiz_id
        JOIN knowledge_points ON knowledge_points.id = child.knowledge_point_id
        WHERE (SELECT user_id FROM learning_goals WHERE id = quizzes.goal_id)
           != (SELECT user_id FROM learning_goals WHERE id = knowledge_points.goal_id)
        """,
    ),
    (
        "quizzes",
        """
        SELECT COUNT(*) FROM quizzes AS child
        WHERE (
            child.plan_id IS NOT NULL
            AND (SELECT learning_goals.user_id FROM study_plans
                 JOIN learning_goals ON learning_goals.id = study_plans.goal_id
                 WHERE study_plans.id = child.plan_id)
               != (SELECT user_id FROM learning_goals WHERE id = child.goal_id)
        ) OR (
            child.task_id IS NOT NULL
            AND (SELECT learning_goals.user_id FROM study_tasks
                 JOIN study_plans ON study_plans.id = study_tasks.plan_id
                 JOIN learning_goals ON learning_goals.id = study_plans.goal_id
                 WHERE study_tasks.id = child.task_id)
               != (SELECT user_id FROM learning_goals WHERE id = child.goal_id)
        )
        """,
    ),
    (
        "knowledge_mastery_events",
        """
        SELECT COUNT(*) FROM knowledge_mastery_events AS child
        WHERE child.quiz_id IS NOT NULL
          AND (SELECT learning_goals.user_id FROM quizzes
               JOIN learning_goals ON learning_goals.id = quizzes.goal_id
               WHERE quizzes.id = child.quiz_id)
            != (SELECT learning_goals.user_id FROM knowledge_points
                JOIN learning_goals ON learning_goals.id = knowledge_points.goal_id
                WHERE knowledge_points.id = child.knowledge_point_id)
        """,
    ),
    (
        "review_schedules",
        """
        SELECT COUNT(*) FROM review_schedules AS child
        JOIN knowledge_points ON knowledge_points.id = child.knowledge_point_id
        WHERE (SELECT user_id FROM learning_goals WHERE id = child.goal_id)
           != (SELECT user_id FROM learning_goals WHERE id = knowledge_points.goal_id)
        """,
    ),
    (
        "review_records",
        """
        SELECT COUNT(*) FROM review_records AS child
        JOIN review_schedules ON review_schedules.id = child.schedule_id
        JOIN knowledge_points ON knowledge_points.id = child.knowledge_point_id
        WHERE (SELECT user_id FROM learning_goals WHERE id = review_schedules.goal_id)
           != (SELECT user_id FROM learning_goals WHERE id = knowledge_points.goal_id)
           OR (
                child.quiz_id IS NOT NULL
                AND (SELECT learning_goals.user_id FROM quizzes
                     JOIN learning_goals ON learning_goals.id = quizzes.goal_id
                     WHERE quizzes.id = child.quiz_id)
                  != (SELECT user_id FROM learning_goals WHERE id = review_schedules.goal_id)
           )
        """,
    ),
    (
        "training_recommendations",
        """
        SELECT COUNT(*) FROM training_recommendations AS child
        WHERE (
            child.goal_id IS NOT NULL
            AND (SELECT user_id FROM learning_goals WHERE id = child.goal_id) != child.user_id
        ) OR (
            child.problem_id IS NOT NULL
            AND (SELECT user_id FROM problems WHERE id = child.problem_id) != child.user_id
        ) OR (
            child.problem_topic_id IS NOT NULL
            AND (SELECT user_id FROM problem_topics WHERE id = child.problem_topic_id) != child.user_id
        ) OR (
            child.knowledge_point_id IS NOT NULL
            AND (SELECT learning_goals.user_id FROM knowledge_points
                 JOIN learning_goals ON learning_goals.id = knowledge_points.goal_id
                 WHERE knowledge_points.id = child.knowledge_point_id) != child.user_id
        )
        """,
    ),
)


class OwnerInitError(Exception):
    """初始化不能继续。调用方只展示这条消息，其中不含密码。"""


@dataclass(frozen=True)
class OwnerPreview:
    created_at: str
    preserved: dict[str, tuple[int, ...]]
    removed: dict[str, tuple[int, ...]]


@dataclass(frozen=True)
class OwnerInitResult:
    user_id: int
    username: str
    email: str | None
    nickname: str
    created_at: str
    backup_path: Path
    preserved: dict[str, tuple[int, ...]]
    removed: dict[str, tuple[int, ...]]


# 用同一套归属 SQL 统计删除前后的主键。只读，不根据表名拼接用户输入。
_OWNED_ID_SQL: tuple[tuple[str, str], ...] = (
    ("learning_goals", "SELECT id FROM learning_goals WHERE user_id = ? ORDER BY id"),
    (
        "knowledge_points",
        """
        SELECT knowledge_points.id FROM knowledge_points
        JOIN learning_goals ON learning_goals.id = knowledge_points.goal_id
        WHERE learning_goals.user_id = ? ORDER BY knowledge_points.id
        """,
    ),
    (
        "study_plans",
        """
        SELECT study_plans.id FROM study_plans
        JOIN learning_goals ON learning_goals.id = study_plans.goal_id
        WHERE learning_goals.user_id = ? ORDER BY study_plans.id
        """,
    ),
    (
        "study_tasks",
        """
        SELECT study_tasks.id FROM study_tasks
        JOIN study_plans ON study_plans.id = study_tasks.plan_id
        JOIN learning_goals ON learning_goals.id = study_plans.goal_id
        WHERE learning_goals.user_id = ? ORDER BY study_tasks.id
        """,
    ),
    (
        "plan_revisions",
        """
        SELECT plan_revisions.id FROM plan_revisions
        JOIN study_plans ON study_plans.id = plan_revisions.plan_id
        JOIN learning_goals ON learning_goals.id = study_plans.goal_id
        WHERE learning_goals.user_id = ? ORDER BY plan_revisions.id
        """,
    ),
    (
        "quizzes",
        """
        SELECT quizzes.id FROM quizzes
        JOIN learning_goals ON learning_goals.id = quizzes.goal_id
        WHERE learning_goals.user_id = ? ORDER BY quizzes.id
        """,
    ),
    (
        "quiz_questions",
        """
        SELECT quiz_questions.id FROM quiz_questions
        JOIN quizzes ON quizzes.id = quiz_questions.quiz_id
        JOIN learning_goals ON learning_goals.id = quizzes.goal_id
        WHERE learning_goals.user_id = ? ORDER BY quiz_questions.id
        """,
    ),
    (
        "quiz_answers",
        """
        SELECT quiz_answers.id FROM quiz_answers
        JOIN quiz_questions ON quiz_questions.id = quiz_answers.question_id
        JOIN quizzes ON quizzes.id = quiz_questions.quiz_id
        JOIN learning_goals ON learning_goals.id = quizzes.goal_id
        WHERE learning_goals.user_id = ? ORDER BY quiz_answers.id
        """,
    ),
    (
        "knowledge_mastery_events",
        """
        SELECT knowledge_mastery_events.id FROM knowledge_mastery_events
        JOIN knowledge_points ON knowledge_points.id = knowledge_mastery_events.knowledge_point_id
        JOIN learning_goals ON learning_goals.id = knowledge_points.goal_id
        WHERE learning_goals.user_id = ? ORDER BY knowledge_mastery_events.id
        """,
    ),
    (
        "review_schedules",
        """
        SELECT review_schedules.id FROM review_schedules
        JOIN learning_goals ON learning_goals.id = review_schedules.goal_id
        WHERE learning_goals.user_id = ? ORDER BY review_schedules.id
        """,
    ),
    (
        "review_records",
        """
        SELECT review_records.id FROM review_records
        JOIN review_schedules ON review_schedules.id = review_records.schedule_id
        JOIN learning_goals ON learning_goals.id = review_schedules.goal_id
        WHERE learning_goals.user_id = ? ORDER BY review_records.id
        """,
    ),
    ("tutor_sessions", "SELECT id FROM tutor_sessions WHERE user_id = ? ORDER BY id"),
    (
        "tutor_messages",
        """
        SELECT tutor_messages.id FROM tutor_messages
        JOIN tutor_sessions ON tutor_sessions.id = tutor_messages.session_id
        WHERE tutor_sessions.user_id = ? ORDER BY tutor_messages.id
        """,
    ),
    ("problems", "SELECT id FROM problems WHERE user_id = ? ORDER BY id"),
    ("problem_topics", "SELECT id FROM problem_topics WHERE user_id = ? ORDER BY id"),
    (
        "problem_topic_links",
        """
        SELECT problem_topic_links.id FROM problem_topic_links
        JOIN problems ON problems.id = problem_topic_links.problem_id
        WHERE problems.user_id = ? ORDER BY problem_topic_links.id
        """,
    ),
    (
        "problem_test_cases",
        """
        SELECT problem_test_cases.id FROM problem_test_cases
        JOIN problems ON problems.id = problem_test_cases.problem_id
        WHERE problems.user_id = ? ORDER BY problem_test_cases.id
        """,
    ),
    ("problem_notes", "SELECT id FROM problem_notes WHERE user_id = ? ORDER BY id"),
    ("problem_code_drafts", "SELECT id FROM problem_code_drafts WHERE user_id = ? ORDER BY id"),
    ("problem_submissions", "SELECT id FROM problem_submissions WHERE user_id = ? ORDER BY id"),
    ("problem_judge_results", "SELECT id FROM problem_judge_results WHERE user_id = ? ORDER BY id"),
    (
        "problem_judge_case_results",
        """
        SELECT problem_judge_case_results.id FROM problem_judge_case_results
        JOIN problem_judge_results ON problem_judge_results.id = problem_judge_case_results.judge_result_id
        WHERE problem_judge_results.user_id = ? ORDER BY problem_judge_case_results.id
        """,
    ),
    ("problem_learning_status", "SELECT id FROM problem_learning_status WHERE user_id = ? ORDER BY id"),
    ("problem_practice_records", "SELECT id FROM problem_practice_records WHERE user_id = ? ORDER BY id"),
    ("problem_wrong_records", "SELECT id FROM problem_wrong_records WHERE user_id = ? ORDER BY id"),
    ("training_recommendations", "SELECT id FROM training_recommendations WHERE user_id = ? ORDER BY id"),
    ("topic_knowledge_links", "SELECT id FROM topic_knowledge_links WHERE user_id = ? ORDER BY id"),
    ("user_sessions", "SELECT id FROM user_sessions WHERE user_id = ? ORDER BY id"),
)

# 子表在前。全部外键都是 ON DELETE NO ACTION，不能依赖级联。
_DELETE_REMOVED_USER: tuple[tuple[str, str], ...] = (
    (
        "problem_judge_case_results",
        """
        DELETE FROM problem_judge_case_results
        WHERE judge_result_id IN (SELECT id FROM problem_judge_results WHERE user_id = ?)
        """,
    ),
    ("problem_judge_results", "DELETE FROM problem_judge_results WHERE user_id = ?"),
    (
        "quiz_answers",
        """
        DELETE FROM quiz_answers WHERE question_id IN (
            SELECT quiz_questions.id FROM quiz_questions
            JOIN quizzes ON quizzes.id = quiz_questions.quiz_id
            JOIN learning_goals ON learning_goals.id = quizzes.goal_id
            WHERE learning_goals.user_id = ?
        )
        """,
    ),
    (
        "knowledge_mastery_events",
        """
        DELETE FROM knowledge_mastery_events WHERE knowledge_point_id IN (
            SELECT knowledge_points.id FROM knowledge_points
            JOIN learning_goals ON learning_goals.id = knowledge_points.goal_id
            WHERE learning_goals.user_id = ?
        )
        """,
    ),
    (
        "review_records",
        """
        DELETE FROM review_records WHERE schedule_id IN (
            SELECT review_schedules.id FROM review_schedules
            JOIN learning_goals ON learning_goals.id = review_schedules.goal_id
            WHERE learning_goals.user_id = ?
        )
        """,
    ),
    (
        "tutor_messages",
        "DELETE FROM tutor_messages WHERE session_id IN (SELECT id FROM tutor_sessions WHERE user_id = ?)",
    ),
    (
        "problem_topic_links",
        """
        DELETE FROM problem_topic_links
        WHERE problem_id IN (SELECT id FROM problems WHERE user_id = ?)
           OR topic_id IN (SELECT id FROM problem_topics WHERE user_id = ?)
        """,
    ),
    ("topic_knowledge_links", "DELETE FROM topic_knowledge_links WHERE user_id = ?"),
    ("training_recommendations", "DELETE FROM training_recommendations WHERE user_id = ?"),
    ("problem_notes", "DELETE FROM problem_notes WHERE user_id = ?"),
    ("problem_code_drafts", "DELETE FROM problem_code_drafts WHERE user_id = ?"),
    ("problem_submissions", "DELETE FROM problem_submissions WHERE user_id = ?"),
    ("problem_learning_status", "DELETE FROM problem_learning_status WHERE user_id = ?"),
    ("problem_practice_records", "DELETE FROM problem_practice_records WHERE user_id = ?"),
    ("problem_wrong_records", "DELETE FROM problem_wrong_records WHERE user_id = ?"),
    (
        "problem_test_cases",
        "DELETE FROM problem_test_cases WHERE problem_id IN (SELECT id FROM problems WHERE user_id = ?)",
    ),
    (
        "quiz_questions",
        """
        DELETE FROM quiz_questions WHERE quiz_id IN (
            SELECT quizzes.id FROM quizzes
            JOIN learning_goals ON learning_goals.id = quizzes.goal_id
            WHERE learning_goals.user_id = ?
        )
        """,
    ),
    (
        "quizzes",
        "DELETE FROM quizzes WHERE goal_id IN (SELECT id FROM learning_goals WHERE user_id = ?)",
    ),
    (
        "plan_revisions",
        """
        DELETE FROM plan_revisions WHERE plan_id IN (
            SELECT study_plans.id FROM study_plans
            JOIN learning_goals ON learning_goals.id = study_plans.goal_id
            WHERE learning_goals.user_id = ?
        )
        """,
    ),
    (
        "study_tasks",
        """
        DELETE FROM study_tasks WHERE plan_id IN (
            SELECT study_plans.id FROM study_plans
            JOIN learning_goals ON learning_goals.id = study_plans.goal_id
            WHERE learning_goals.user_id = ?
        )
        """,
    ),
    (
        "study_plans",
        "DELETE FROM study_plans WHERE goal_id IN (SELECT id FROM learning_goals WHERE user_id = ?)",
    ),
    (
        "review_schedules",
        "DELETE FROM review_schedules WHERE goal_id IN (SELECT id FROM learning_goals WHERE user_id = ?)",
    ),
    (
        "knowledge_points",
        "DELETE FROM knowledge_points WHERE goal_id IN (SELECT id FROM learning_goals WHERE user_id = ?)",
    ),
    ("tutor_sessions", "DELETE FROM tutor_sessions WHERE user_id = ?"),
    ("problems", "DELETE FROM problems WHERE user_id = ?"),
    ("problem_topics", "DELETE FROM problem_topics WHERE user_id = ?"),
    ("learning_goals", "DELETE FROM learning_goals WHERE user_id = ?"),
    ("user_sessions", "DELETE FROM user_sessions WHERE user_id = ?"),
    ("users", "DELETE FROM users WHERE id = ?"),
)


def preview_owner_init(database_path: Path) -> OwnerPreview:
    """只读查看即将保留和删除的主键。不创建备份，也不修改数据库。"""
    path = Path(database_path)
    if not path.is_file():
        raise OwnerInitError("没有找到数据库文件")
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    except sqlite3.OperationalError as exc:
        if _is_locked(exc):
            raise OwnerInitError("数据库正被其他进程占用，请先停止 StudyMate 后端后再执行初始化") from None
        raise
    connection.row_factory = sqlite3.Row
    try:
        try:
            _require_integrity(connection)
            created_at = _require_accounts(connection)
        except sqlite3.OperationalError as exc:
            if _is_locked(exc):
                raise OwnerInitError("数据库正被其他进程占用，请先停止 StudyMate 后端后再执行初始化") from None
            raise
        return OwnerPreview(
            created_at=created_at,
            preserved=owned_ids(connection, HISTORICAL_USER_ID),
            removed=owned_ids(connection, REMOVED_USER_ID),
        )
    finally:
        connection.close()


def initialize_owner(
    database_path: Path,
    *,
    username: str,
    email: str | None,
    nickname: str | None,
    password: str,
    confirm_password: str,
    before_commit: Callable[[], None] | None = None,
) -> OwnerInitResult:
    """在一个写事务中删除 id=2，再把 id=1 更新为正式账号。"""
    if password != confirm_password:
        raise OwnerInitError("两次输入的密码不一致")
    profile = _validate_profile(username, email, nickname, password)
    if profile.username != TARGET_USERNAME:
        raise OwnerInitError("正式用户名需要是夜临")
    path = Path(database_path)
    preview = preview_owner_init(path)
    _ensure_writable(path)
    backup_path = _backup(path)
    _verify_backup(backup_path, preview.created_at)

    connection = _connect(path, autocommit=True)
    try:
        try:
            connection.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            if _is_locked(exc):
                raise OwnerInitError("数据库正被其他进程占用，请先停止 StudyMate 后端后再执行初始化") from None
            raise OwnerInitError("初始化失败，尚未修改账号") from None
        try:
            created_at, preserved, removed = _apply_changes(connection, profile, before_commit)
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
    finally:
        connection.close()

    confirmed = _connect(path)
    try:
        _require_integrity(confirmed)
        if confirmed.execute("PRAGMA foreign_key_check").fetchall():
            raise OwnerInitError(f"初始化后外键检查未通过。备份仍在：{backup_path}")
        row = confirmed.execute(
            "SELECT id, username, email, nickname, password_hash, created_at FROM users WHERE id = ?",
            (HISTORICAL_USER_ID,),
        ).fetchone()
        user_ids = [item[0] for item in confirmed.execute("SELECT id FROM users ORDER BY id")]
        if (
            user_ids != [HISTORICAL_USER_ID]
            or row is None
            or row["username"] != profile.username
            or not row["password_hash"]
            or row["created_at"] != created_at
            or owned_ids(confirmed, HISTORICAL_USER_ID) != preserved
            or any(owned_ids(confirmed, REMOVED_USER_ID).values())
        ):
            raise OwnerInitError(f"初始化后的用户记录与预期不符。备份仍在：{backup_path}")
        if ownership_problems(confirmed):
            raise OwnerInitError(f"初始化后用户归属检查未通过。备份仍在：{backup_path}")
    finally:
        confirmed.close()

    return OwnerInitResult(
        user_id=HISTORICAL_USER_ID,
        username=profile.username,
        email=profile.email,
        nickname=profile.nickname or profile.username,
        created_at=created_at,
        backup_path=backup_path,
        preserved=preserved,
        removed=removed,
    )


def table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    names = [
        name
        for (name,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\' ORDER BY name"
        )
        if _safe_identifier(name)
    ]
    return {name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in names}


def ownership_problems(connection: sqlite3.Connection) -> list[str]:
    problems: list[str] = []
    existing = {name for name in table_counts(connection)}
    for table in _USER_ID_TABLES:
        if table not in existing:
            continue
        orphan = connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE user_id NOT IN (SELECT id FROM users)"
        ).fetchone()[0]
        if orphan:
            problems.append(f"{table} 有 {orphan} 行不属于任何用户")
    for table, statement in _RELATION_CHECKS:
        if table not in existing:
            continue
        mismatch = connection.execute(statement).fetchone()[0]
        if mismatch:
            problems.append(f"{table} 有 {mismatch} 行父子归属不一致")
    return problems


def _validate_profile(username: str, email: str | None, nickname: str | None, password: str) -> RegisterRequest:
    try:
        return RegisterRequest(username=username, email=email, nickname=nickname, password=password)
    except ValidationError as exc:
        parts: list[str] = []
        for item in exc.errors():
            message = str(item.get("msg", "输入不符合要求"))
            if message.startswith("Value error, "):
                message = message.removeprefix("Value error, ")
            parts.append(message)
        text = "；".join(parts) or "输入不符合要求"
        for secret in (password, username, email or "", nickname or ""):
            if secret:
                text = text.replace(secret, "")
        raise OwnerInitError(text) from None


def owned_ids(connection: sqlite3.Connection, user_id: int) -> dict[str, tuple[int, ...]]:
    existing = set(table_counts(connection))
    found: dict[str, tuple[int, ...]] = {}
    for table, statement in _OWNED_ID_SQL:
        if table not in existing:
            continue
        found[table] = tuple(row[0] for row in connection.execute(statement, (user_id,)))
    return found


def _require_accounts(connection: sqlite3.Connection) -> str:
    rows = connection.execute("SELECT id, username, password_hash, created_at FROM users ORDER BY id").fetchall()
    if len(rows) == 1 and rows[0]["id"] == HISTORICAL_USER_ID and rows[0]["password_hash"] is not None:
        raise OwnerInitError("历史账号已经完成初始化，不能再次覆盖密码")
    local = next((row for row in rows if row["id"] == HISTORICAL_USER_ID), None)
    if local is None or local["username"] != LOCAL_USERNAME:
        raise OwnerInitError("没有找到 id=1 且用户名为 local 的历史账号")
    if local["password_hash"] is not None:
        raise OwnerInitError("local 已经设置过密码，不能再次覆盖")
    if [row["id"] for row in rows] != [HISTORICAL_USER_ID, REMOVED_USER_ID]:
        raise OwnerInitError("当前数据库必须同时包含未初始化的 id=1（local）和待删除的 id=2。现有用户与已确认的方案不一致，已停止")
    uncertain = ownership_problems(connection)
    if uncertain:
        raise OwnerInitError("存在无法确认归属的记录，已停止")
    return str(local["created_at"])


def _apply_changes(
    connection: sqlite3.Connection,
    profile: RegisterRequest,
    before_commit: Callable[[], None] | None,
) -> tuple[str, dict[str, tuple[int, ...]], dict[str, tuple[int, ...]]]:
    _require_integrity(connection)
    created_at = _require_accounts(connection)
    preserved = owned_ids(connection, HISTORICAL_USER_ID)
    removed = owned_ids(connection, REMOVED_USER_ID)
    _reject_other_conflict(connection, "username", profile.username)
    _reject_other_conflict(connection, "email", profile.email)
    _delete_removed_user(connection)
    if any(owned_ids(connection, REMOVED_USER_ID).values()):
        raise OwnerInitError("删除后仍然存在 id=2 的业务数据，已回滚")
    if [row[0] for row in connection.execute("SELECT id FROM users ORDER BY id")] != [HISTORICAL_USER_ID]:
        raise OwnerInitError("初始化后用户表不是只保留 id=1，已回滚")
    if owned_ids(connection, HISTORICAL_USER_ID) != preserved:
        raise OwnerInitError("id=1 的历史数据数量发生变化，已回滚")
    if connection.execute(
        "SELECT id FROM users WHERE username = ? AND id != ?",
        (profile.username, HISTORICAL_USER_ID),
    ).fetchone() is not None:
        raise OwnerInitError("用户名已被使用，已回滚")
    if profile.email is not None and connection.execute(
        "SELECT id FROM users WHERE email = ? AND id != ?",
        (profile.email, HISTORICAL_USER_ID),
    ).fetchone() is not None:
        raise OwnerInitError("邮箱已被使用，已回滚")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
    password_hash = hash_password(profile.password)
    updated = connection.execute(
        """
        UPDATE users
        SET username = ?, email = ?, password_hash = ?, nickname = ?, updated_at = ?
        WHERE id = ? AND username = ? AND password_hash IS NULL
        """,
        (
            profile.username,
            profile.email,
            password_hash,
            profile.nickname or profile.username,
            now,
            HISTORICAL_USER_ID,
            LOCAL_USERNAME,
        ),
    )
    if updated.rowcount != 1:
        raise OwnerInitError("更新历史账号失败，已回滚")
    connection.execute(
        "UPDATE user_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
        (now, HISTORICAL_USER_ID),
    )
    if owned_ids(connection, HISTORICAL_USER_ID) != preserved:
        raise OwnerInitError("id=1 的历史数据数量发生变化，已回滚")
    if ownership_problems(connection):
        raise OwnerInitError("用户归属检查未通过，已回滚")
    _require_integrity(connection)
    if connection.execute("PRAGMA foreign_key_check").fetchall():
        raise OwnerInitError("外键检查未通过，已回滚")
    if before_commit is not None:
        before_commit()
    return created_at, preserved, removed


def _reject_other_conflict(connection: sqlite3.Connection, column: str, value: str | None) -> None:
    if column not in {"username", "email"} or value is None:
        return
    conflict = connection.execute(
        f"SELECT id FROM users WHERE {column} = ? AND id NOT IN (?, ?)",
        (value, HISTORICAL_USER_ID, REMOVED_USER_ID),
    ).fetchone()
    if conflict is not None:
        label = "用户名" if column == "username" else "邮箱"
        raise OwnerInitError(f"{label}已被使用")


def _delete_removed_user(connection: sqlite3.Connection) -> None:
    existing = set(table_counts(connection))
    for table, statement in _DELETE_REMOVED_USER:
        if table not in existing:
            continue
        connection.execute(statement, (REMOVED_USER_ID,) * statement.count("?"))


def _backup(database_path: Path) -> Path:
    directory = database_path.parent / "backups"
    source = None
    target = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        destination = directory / f"studymate-before-owner-init-{stamp}.db"
        if destination.exists():
            destination = directory / f"studymate-before-owner-init-{stamp}{datetime.now().strftime('%f')}.db"
        source = _connect(database_path)
        target = sqlite3.connect(destination)
        source.backup(target)
    except OwnerInitError:
        raise
    except sqlite3.OperationalError as exc:
        if _is_locked(exc):
            raise OwnerInitError("数据库正被其他进程占用，请先停止 StudyMate 后端后再执行初始化") from None
        raise OwnerInitError("创建数据库备份失败，尚未修改原数据库") from None
    except OSError:
        raise OwnerInitError("创建数据库备份失败，尚未修改原数据库") from None
    finally:
        if target is not None:
            target.close()
        if source is not None:
            source.close()
    return destination


def _verify_backup(backup_path: Path, created_at: str) -> None:
    connection = sqlite3.connect(backup_path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        status = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if status != "ok":
            raise OwnerInitError("备份完整性检查未通过，尚未修改原数据库")
        local = connection.execute(
            "SELECT username, password_hash, created_at FROM users WHERE id = ?",
            (HISTORICAL_USER_ID,),
        ).fetchone()
        removed = connection.execute("SELECT id FROM users WHERE id = ?", (REMOVED_USER_ID,)).fetchone()
        if (
            local is None
            or local["username"] != LOCAL_USERNAME
            or local["password_hash"] is not None
            or local["created_at"] != created_at
            or removed is None
        ):
            raise OwnerInitError("备份没有保留初始化前的两个账号，尚未修改原数据库")
    finally:
        connection.close()


def _ensure_writable(path: Path) -> None:
    connection = _connect(path, autocommit=True)
    try:
        connection.execute("BEGIN EXCLUSIVE")
        connection.execute("ROLLBACK")
    except sqlite3.OperationalError as exc:
        if _is_locked(exc):
            raise OwnerInitError("数据库正被其他进程占用，请先停止 StudyMate 后端后再执行初始化") from None
        raise
    finally:
        connection.close()


def _require_integrity(connection: sqlite3.Connection) -> None:
    status = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if status != "ok":
        raise OwnerInitError("数据库完整性检查未通过，尚未修改账号")


def _connect(path: Path, *, autocommit: bool = False) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=2, isolation_level=None if autocommit else "")
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 2000")
    except sqlite3.OperationalError as exc:
        connection.close()
        if _is_locked(exc):
            raise OwnerInitError("数据库正被其他进程占用，请先停止 StudyMate 后端后再执行初始化") from None
        raise
    return connection


def _safe_identifier(name: str) -> bool:
    return bool(name) and name.replace("_", "").isalnum() and not name.startswith("sqlite_")


def _is_locked(exc: sqlite3.OperationalError) -> bool:
    text = str(exc).lower()
    return "locked" in text or "busy" in text
