"""历史账号初始化。只使用临时数据库，不读取、不修改正式学习记录。"""

import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import settings
from app.database import get_session
from app.main import app
from app.models.goal import LearningGoal
from app.models.judge import ProblemJudgeCaseResult, ProblemJudgeResult
from app.models.knowledge import KnowledgePoint
from app.models.plan import PlanRevision, StudyPlan, StudyTask
from app.models.practice import ProblemLearningStatus, ProblemPracticeRecord, ProblemWrongRecord
from app.models.problem import Problem, ProblemNote, ProblemTestCase, ProblemTopic, ProblemTopicLink
from app.models.quiz import KnowledgeMasteryEvent, Quiz, QuizAnswer, QuizQuestion
from app.models.recommendation import TrainingRecommendation
from app.models.review import ReviewRecord, ReviewSchedule
from app.models.submission import ProblemCodeDraft, ProblemSubmission
from app.models.topic_link import TopicKnowledgeLink
from app.models.tutor import TutorMessage, TutorSession
from app.models.user import User, UserSession, utc_now
from app.services.auth_service import hash_token
from app.services.goal_service import ensure_local_user
from app.services.owner_init import OwnerInitError, initialize_owner, owned_ids
from tests.client import RawTestClient

PASSWORD = "owner1234"
CREATED = datetime(2026, 11, 3, 6, 6, 16, tzinfo=timezone.utc)


def _engine(path):
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    return engine


def _graph(session: Session, user_id: int, marker: str) -> dict:
    goal = LearningGoal(
        user_id=user_id,
        title=f"{marker}目标",
        description=f"{marker}描述",
        target_date=date(2026, 12, 31),
        daily_minutes=30,
    )
    session.add(goal)
    session.commit()
    session.refresh(goal)
    point = KnowledgePoint(goal_id=goal.id, name=f"{marker}知识点", description=f"{marker}说明")
    session.add(point)
    session.commit()
    session.refresh(point)
    plan = StudyPlan(
        goal_id=goal.id,
        plan_date=date(2026, 12, 1),
        title=f"{marker}计划",
        description=f"{marker}计划说明",
        total_minutes=30,
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    task = StudyTask(
        plan_id=plan.id,
        knowledge_point_id=point.id,
        title=f"{marker}任务",
        description=f"{marker}任务说明",
        task_type="study",
        estimated_minutes=20,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    session.add(PlanRevision(plan_id=plan.id, old_content="旧", new_content="新", reason=marker))
    quiz = Quiz(goal_id=goal.id, plan_id=plan.id, task_id=task.id, title=f"{marker}检测")
    session.add(quiz)
    session.commit()
    session.refresh(quiz)
    question = QuizQuestion(
        quiz_id=quiz.id,
        knowledge_point_id=point.id,
        question_type="single",
        difficulty="easy",
        stem=f"{marker}题干",
        correct_answer="A",
        explanation=f"{marker}解析",
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    session.add(QuizAnswer(question_id=question.id, user_answer="A", is_correct=True, score=100))
    session.add(KnowledgeMasteryEvent(knowledge_point_id=point.id, quiz_id=quiz.id, new_level=40, quiz_score=80, reason=marker))
    schedule = ReviewSchedule(goal_id=goal.id, knowledge_point_id=point.id, next_review_date=date(2026, 12, 31))
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    session.add(
        ReviewRecord(
            schedule_id=schedule.id,
            knowledge_point_id=point.id,
            quiz_id=quiz.id,
            result="pass",
            next_interval=1,
            next_review_date=date(2026, 12, 31),
        )
    )
    topic = ProblemTopic(user_id=user_id, category="algorithm", name=f"{marker}专题")
    problem = Problem(user_id=user_id, title=f"{marker}题目", description=f"{marker}题目说明")
    session.add(topic)
    session.add(problem)
    session.commit()
    session.refresh(topic)
    session.refresh(problem)
    session.add(ProblemTopicLink(problem_id=problem.id, topic_id=topic.id, relevance="primary"))
    case = ProblemTestCase(problem_id=problem.id, name=f"{marker}用例", input_data="1", expected_output="1")
    session.add(case)
    session.add(ProblemNote(problem_id=problem.id, user_id=user_id, content=f"{marker}笔记"))
    session.add(ProblemCodeDraft(user_id=user_id, problem_id=problem.id, language="cpp", source_code="int main(){return 0;}"))
    submission = ProblemSubmission(
        user_id=user_id,
        problem_id=problem.id,
        language="cpp",
        source_code="int main(){return 0;}",
    )
    session.add(submission)
    session.commit()
    session.refresh(case)
    session.refresh(submission)
    judge = ProblemJudgeResult(user_id=user_id, submission_id=submission.id, problem_id=problem.id, status="accepted")
    session.add(judge)
    session.commit()
    session.refresh(judge)
    session.add(
        ProblemJudgeCaseResult(
            judge_result_id=judge.id,
            test_case_id=case.id,
            status="accepted",
            expected_output="1",
            actual_output="1",
        )
    )
    session.add(ProblemLearningStatus(user_id=user_id, problem_id=problem.id, status="todo"))
    session.add(ProblemPracticeRecord(user_id=user_id, problem_id=problem.id))
    session.add(ProblemWrongRecord(user_id=user_id, problem_id=problem.id, reason_type="logic"))
    session.add(
        TrainingRecommendation(
            user_id=user_id,
            goal_id=goal.id,
            knowledge_point_id=point.id,
            problem_topic_id=topic.id,
            problem_id=problem.id,
            category="practice",
            title=f"{marker}建议",
            estimated_minutes=20,
            priority=1,
            completion_criteria="完成",
        )
    )
    session.add(TopicKnowledgeLink(user_id=user_id, problem_topic_id=topic.id, knowledge_point_id=point.id))
    tutor = TutorSession(user_id=user_id, goal_id=goal.id, title=f"{marker}对话")
    session.add(tutor)
    session.commit()
    session.refresh(tutor)
    session.add(TutorMessage(session_id=tutor.id, role="user", content=f"{marker}消息"))
    token = f"token-{user_id}-{marker}"
    session.add(
        UserSession(
            user_id=user_id,
            session_token_hash=hash_token(token),
            expires_at=utc_now() + timedelta(days=2),
        )
    )
    session.commit()
    return {"goal_id": goal.id, "problem_id": problem.id, "token": token}


def _prepare(
    path,
    *,
    password_hash: str | None = None,
    second_username: str = "夜临",
    second_email: str | None = "night@example.com",
    include_second: bool = True,
    extra_user: bool = False,
    empty: bool = False,
    ambiguous: bool = False,
    full: bool = False,
) -> dict:
    engine = _engine(path)
    info: dict = {}
    with Session(engine) as session:
        if not empty:
            session.add(
                User(
                    id=1,
                    username="local",
                    nickname="local",
                    password_hash=password_hash,
                    created_at=CREATED,
                    updated_at=CREATED,
                )
            )
            session.commit()
            if full:
                info = _graph(session, 1, "历史")
            else:
                goal = LearningGoal(
                    user_id=1,
                    title="历史目标",
                    description="保留下来的历史目标",
                    target_date=date(2026, 12, 31),
                    daily_minutes=30,
                )
                session.add(goal)
                session.commit()
                session.refresh(goal)
                session.add(KnowledgePoint(goal_id=goal.id, name="历史知识点", description="保留下来的知识点"))
                tutor = TutorSession(user_id=1, goal_id=goal.id, title="历史对话")
                session.add(tutor)
                session.commit()
                session.refresh(tutor)
                session.add(TutorMessage(session_id=tutor.id, role="user", content="历史消息"))
                problem = Problem(user_id=1, title="历史题目", description="保留下来的题目")
                session.add(problem)
                session.commit()
                session.refresh(problem)
                session.add(
                    ProblemSubmission(
                        user_id=1,
                        problem_id=problem.id,
                        language="cpp",
                        source_code="int main(){return 0;}",
                    )
                )
                info = {"goal_id": goal.id, "problem_id": problem.id, "token": "legacy-session-token"}
                session.add(
                    UserSession(
                        user_id=1,
                        session_token_hash=hash_token(info["token"]),
                        expires_at=utc_now() + timedelta(days=2),
                    )
                )
            if include_second:
                session.add(
                    User(
                        id=2,
                        username=second_username,
                        email=second_email,
                        password_hash="set",
                        nickname=second_username,
                    )
                )
                session.commit()
                if ambiguous:
                    session.add(TutorSession(user_id=2, goal_id=info["goal_id"], title="跨用户会话"))
                elif full:
                    info["removed"] = _graph(session, 2, "待删除")
                else:
                    removed = LearningGoal(
                        user_id=2,
                        title="待删除目标",
                        description="不能并入历史账号",
                        target_date=date(2026, 12, 31),
                        daily_minutes=20,
                    )
                    session.add(removed)
                    session.commit()
                    session.refresh(removed)
                    info["removed_goal_id"] = removed.id
                    session.add(
                        UserSession(
                            user_id=2,
                            session_token_hash=hash_token("removed-session-token"),
                            expires_at=utc_now() + timedelta(days=2),
                        )
                    )
            if extra_user:
                session.add(User(id=3, username="extra", password_hash="set", nickname="extra"))
            session.commit()
    engine.dispose()
    return info


def _user(path, user_id: int):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    connection.close()
    return row


def _owned(path, user_id: int) -> dict[str, tuple[int, ...]]:
    connection = sqlite3.connect(path)
    try:
        return owned_ids(connection, user_id)
    finally:
        connection.close()


def _init(path, **overrides):
    payload = {
        "username": "夜临",
        "email": "night@example.com",
        "nickname": "夜临",
        "password": PASSWORD,
        "confirm_password": PASSWORD,
    }
    payload.update(overrides)
    return initialize_owner(path, **payload)


def _csrf(client: RawTestClient) -> dict[str, str]:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def _login(client: RawTestClient, username: str, password: str):
    return client.post("/api/auth/login", json={"username": username, "password": password}, headers=_csrf(client))


def test_initialize_owner_replaces_username_and_deletes_second_user(tmp_path) -> None:
    path = tmp_path / "studymate.db"
    info = _prepare(path, full=True)
    preserved_before = _owned(path, 1)
    removed_before = _owned(path, 2)
    assert all(removed_before.values())

    result = _init(path)

    row = _user(path, 1)
    assert result.user_id == 1
    assert result.preserved == preserved_before
    assert result.removed == removed_before
    assert _owned(path, 1) == preserved_before
    assert not any(_owned(path, 2).values())
    assert row["username"] == "夜临"
    assert row["email"] == "night@example.com"
    assert row["nickname"] == "夜临"
    assert row["created_at"] == result.created_at
    assert row["password_hash"].startswith("$argon2")
    assert PASSWORD not in row["password_hash"]
    connection = sqlite3.connect(path)
    assert [item[0] for item in connection.execute("SELECT id FROM users")] == [1]
    assert connection.execute("SELECT title FROM learning_goals").fetchall() == [("历史目标",)]
    assert connection.execute("SELECT revoked_at FROM user_sessions WHERE user_id = 1").fetchone()[0] is not None
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    connection.close()
    backup = sqlite3.connect(result.backup_path)
    assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert backup.execute("SELECT username FROM users WHERE id = 1").fetchone()[0] == "local"
    assert backup.execute("SELECT id FROM users WHERE id = 2").fetchone()[0] == 2
    assert backup.execute("SELECT title FROM learning_goals WHERE user_id = 2").fetchone()[0] == "待删除目标"
    backup.close()
    assert info["goal_id"] in result.preserved["learning_goals"]
    assert info["removed"]["goal_id"] in result.removed["learning_goals"]


def test_second_username_conflict_is_resolved_by_deleting_that_user(tmp_path) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path, second_username="夜临", second_email="night@example.com")
    result = _init(path, email="night@example.com")
    assert _user(path, 1)["username"] == "夜临"
    assert _user(path, 1)["email"] == "night@example.com"
    assert _user(path, 2) is None
    assert result.removed["learning_goals"]
    connection = sqlite3.connect(path)
    assert connection.execute("SELECT title FROM learning_goals").fetchall() == [("历史目标",)]
    connection.close()


def test_other_name_is_deleted_without_merging(tmp_path) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path, second_username="other", second_email=None)
    _init(path, email=None)
    assert _user(path, 1)["username"] == "夜临"
    assert _user(path, 1)["email"] is None
    connection = sqlite3.connect(path)
    assert connection.execute("SELECT COUNT(*) FROM learning_goals WHERE title = '待删除目标'").fetchone()[0] == 0
    assert connection.execute("SELECT user_id FROM learning_goals").fetchall() == [(1,)]
    connection.close()


def test_missing_database_file_fails(tmp_path) -> None:
    with pytest.raises(OwnerInitError, match="没有找到数据库文件"):
        _init(tmp_path / "missing.db")


def test_missing_local_fails(tmp_path) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path, empty=True)
    with pytest.raises(OwnerInitError, match="没有找到 id=1"):
        _init(path)
    assert sqlite3.connect(path).execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_missing_second_user_fails(tmp_path) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path, include_second=False)
    with pytest.raises(OwnerInitError, match="方案不一致"):
        _init(path)
    assert _user(path, 1)["password_hash"] is None


def test_existing_password_is_not_overwritten(tmp_path) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path, password_hash="already-set")
    with pytest.raises(OwnerInitError, match="不能再次覆盖"):
        _init(path)
    row = _user(path, 1)
    assert row["username"] == "local"
    assert row["password_hash"] == "already-set"
    assert _user(path, 2) is not None


def test_second_run_refuses_overwrite(tmp_path) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path)
    _init(path)
    password_hash = _user(path, 1)["password_hash"]
    with pytest.raises(OwnerInitError, match="已经完成初始化"):
        _init(path, email="another@example.com", nickname="另一个")
    row = _user(path, 1)
    assert row["username"] == "夜临"
    assert row["password_hash"] == password_hash


def test_extra_user_stops_initialization(tmp_path) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path, extra_user=True)
    with pytest.raises(OwnerInitError, match="方案不一致"):
        _init(path)
    assert _user(path, 1)["password_hash"] is None
    assert _user(path, 3)["username"] == "extra"


def test_uncertain_ownership_stops_initialization(tmp_path) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path, ambiguous=True)
    with pytest.raises(OwnerInitError, match="无法确认归属"):
        _init(path)
    assert _user(path, 1)["username"] == "local"
    assert _user(path, 2) is not None
    connection = sqlite3.connect(path)
    assert connection.execute("SELECT COUNT(*) FROM tutor_sessions WHERE title = '跨用户会话'").fetchone()[0] == 1
    connection.close()


def test_wrong_username_fails(tmp_path) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path)
    with pytest.raises(OwnerInitError, match="正式用户名需要是夜临") as caught:
        _init(path, username="owner")
    assert "owner" not in str(caught.value)
    assert _user(path, 1)["password_hash"] is None


@pytest.mark.parametrize(
    ("password", "confirm", "message"),
    [
        ("short1", "short1", "8 到 128"),
        ("onlyletters", "onlyletters", "字母和数字"),
        ("12345678", "12345678", "字母和数字"),
        ("owner1234", "different1", "不一致"),
    ],
)
def test_invalid_password_fails(tmp_path, password: str, confirm: str, message: str) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path)
    with pytest.raises(OwnerInitError, match=message) as caught:
        _init(path, password=password, confirm_password=confirm)
    assert password not in str(caught.value)
    assert _user(path, 1)["password_hash"] is None
    assert _user(path, 2) is not None


def test_exception_rolls_back_delete_and_update(tmp_path) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path, full=True)
    before = _owned(path, 1)
    removed = _owned(path, 2)

    def fail() -> None:
        raise RuntimeError("stop")

    with pytest.raises(RuntimeError, match="stop"):
        _init(path, before_commit=fail)

    assert _owned(path, 1) == before
    assert _owned(path, 2) == removed
    assert _user(path, 1)["username"] == "local"
    assert _user(path, 1)["password_hash"] is None
    assert _user(path, 2)["username"] == "夜临"


def test_backup_failure_leaves_database_unchanged(tmp_path) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path)
    (path.parent / "backups").write_text("not a directory", encoding="utf-8")
    with pytest.raises(OwnerInitError, match="备份"):
        _init(path)
    assert _user(path, 1)["username"] == "local"
    assert _user(path, 1)["password_hash"] is None
    assert _user(path, 2) is not None


def test_locked_database_fails_without_changes(tmp_path) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path)
    holder = sqlite3.connect(path, isolation_level=None)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(OwnerInitError, match="占用"):
            _init(path)
    finally:
        holder.execute("ROLLBACK")
        holder.close()
    assert _user(path, 1)["password_hash"] is None


def test_password_prompt_avoids_getpass_chinese_prompt(monkeypatch, capsys) -> None:
    prompts: list[str] = []

    def fake_getpass(prompt: str = "") -> str:
        prompts.append(prompt)
        return "hidden-secret"

    monkeypatch.setattr("getpass.getpass", fake_getpass)
    from app.scripts.initialize_owner import _read_secret

    assert _read_secret("密码：") == "hidden-secret"
    assert prompts == [""]
    captured = capsys.readouterr().out
    assert "密码：" in captured
    assert "hidden-secret" not in captured


def test_cli_rejects_arguments() -> None:
    from app.scripts.initialize_owner import main

    assert main(["--keep-other-users"]) == 1


def test_cli_rejects_other_username(monkeypatch, tmp_path, capsys) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path)
    monkeypatch.setattr(settings, "database_path", path)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "owner")

    from app.scripts.initialize_owner import main

    assert main([]) == 1
    assert "owner1234" not in capsys.readouterr().out
    assert _user(path, 1)["password_hash"] is None


def test_cli_cancel_keeps_database(monkeypatch, tmp_path, capsys) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path)
    monkeypatch.setattr(settings, "database_path", path)
    answers = iter(["夜临", "night@example.com", "夜临", "NO"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": PASSWORD)

    from app.scripts.initialize_owner import main

    assert main([]) == 1
    assert _user(path, 1)["password_hash"] is None
    assert _user(path, 2) is not None
    output = capsys.readouterr().out
    assert PASSWORD not in output
    assert not (path.parent / "backups").exists()


def test_cli_success_does_not_reveal_password(monkeypatch, tmp_path, capsys) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path)
    monkeypatch.setattr(settings, "database_path", path)
    answers = iter(["夜临", "", "夜临", "YES"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": PASSWORD)

    from app.scripts.initialize_owner import main

    assert main([]) == 0
    output = capsys.readouterr().out
    assert PASSWORD not in output
    assert "id=1" in output
    assert "learning_goals: 1" in output
    row = _user(path, 1)
    assert row["username"] == "夜临"
    assert row["email"] is None
    assert PASSWORD not in (row["password_hash"] or "")


def test_initialized_account_can_log_in_and_stays_isolated(tmp_path) -> None:
    path = tmp_path / "studymate.db"
    info = _prepare(path)
    _init(path)
    engine = _engine(path)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    client = RawTestClient(app)
    try:
        client.cookies.set("studymate_session", info["token"])
        assert client.get("/api/goals").status_code == 401
        client.cookies.clear()

        assert _login(client, "夜临", "wrong1234").status_code == 401
        assert _login(client, "local", PASSWORD).status_code == 401
        logged_in = _login(client, "夜临", PASSWORD)
        assert logged_in.status_code == 200, logged_in.text
        assert logged_in.json()["id"] == 1
        assert logged_in.json()["username"] == "夜临"
        assert "password_hash" not in logged_in.json()
        assert "studymate_session" in logged_in.cookies

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["nickname"] == "夜临"

        created = client.post(
            "/api/goals",
            json={"title": "新目标", "description": "属于正式账号", "target_date": "2026-12-31", "daily_minutes": 15},
            headers={"X-CSRF-Token": client.cookies.get("studymate_csrf")},
        )
        assert created.status_code == 201, created.text
        assert created.json()["user_id"] == 1
        titles = {item["title"] for item in client.get("/api/goals").json()}
        assert titles == {"历史目标", "新目标"}
        growth = client.get("/api/learning/growth?days=30")
        assert any(point["name"] == "历史知识点" for point in growth.json()["mastery"]["points"])
        sources = client.get("/api/learning/diagnosis-sources")
        assert any(point["name"] == "历史知识点" for point in sources.json()["knowledge"]["points"])
        diagnosis = client.get(f"/api/learning/diagnosis?goal_id={info['goal_id']}")
        assert any(point["name"] == "历史知识点" for point in diagnosis.json()["knowledge_points"])
        assert any(item["title"] == "历史对话" for item in client.get("/api/tutor/sessions").json()["sessions"])
        assert any(item["title"] == "历史题目" for item in client.get("/api/problems").json()["problems"])
        assert len(client.get(f"/api/problems/{info['problem_id']}/submissions").json()["submissions"]) == 1

        registered = client.post(
            "/api/auth/register",
            json={"username": "reader", "password": "reader1234"},
            headers={"X-CSRF-Token": client.cookies.get("studymate_csrf")},
        )
        assert registered.status_code == 201, registered.text
        assert registered.json()["id"] != 1
        assert _login(client, "reader", "reader1234").status_code == 200
        assert client.get("/api/goals").json() == []
        assert client.get(f"/api/goals/{info['goal_id']}").status_code == 404
        changed = client.put(
            f"/api/goals/{info['goal_id']}",
            json={"title": "被改掉", "description": "不应该成功", "target_date": "2026-12-31", "daily_minutes": 20},
            headers={"X-CSRF-Token": client.cookies.get("studymate_csrf")},
        )
        assert changed.status_code == 404
        deleted = client.delete(
            f"/api/goals/{info['goal_id']}",
            headers={"X-CSRF-Token": client.cookies.get("studymate_csrf")},
        )
        assert deleted.status_code == 404
        assert client.get("/api/tutor/sessions").json()["sessions"] == []
        assert all(item["title"] != "历史题目" for item in client.get("/api/problems").json()["problems"])

        assert _login(client, "夜临", PASSWORD).status_code == 200
        assert any(item["title"] == "历史目标" for item in client.get("/api/goals").json())
        logged_out = client.post("/api/auth/logout", headers={"X-CSRF-Token": client.cookies.get("studymate_csrf")})
        assert logged_out.status_code == 204
        assert client.get("/api/goals").status_code == 401
        assert client.get("/api/auth/me").status_code == 401
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_startup_does_not_recreate_local_after_initialization(tmp_path) -> None:
    path = tmp_path / "studymate.db"
    _prepare(path)
    _init(path)
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    with Session(engine) as session:
        assert ensure_local_user(session) is None
        assert [user.username for user in session.exec(select(User)).all()] == ["夜临"]
    engine.dispose()
