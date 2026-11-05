"""两个登录用户的业务数据隔离。使用不自动登录的客户端。"""

import uuid
from datetime import date, datetime, timezone

from sqlmodel import Session, func, select

from app.database import engine
from app.main import app
from app.models.goal import LearningGoal
from app.models.knowledge import KnowledgePoint
from app.models.quiz import KnowledgeMasteryEvent, Quiz
from app.models.recommendation import TrainingRecommendation
from app.models.review import ReviewSchedule
from app.models.user import User
from app.models.judge import ProblemJudgeCaseResult, ProblemJudgeResult
from app.models.problem import ProblemTestCase
from app.models.submission import ProblemSubmission
from tests.client import LOCAL_PASSWORD, RawTestClient

GOAL = {
    "title": "隔离目标",
    "description": "只属于创建它的用户。",
    "target_date": "2026-12-31",
    "daily_minutes": 25,
}
PROBLEM = {"title": "隔离题目", "description": "只属于创建它的用户。"}


def _client() -> RawTestClient:
    return RawTestClient(app)


def _csrf(client: RawTestClient) -> dict[str, str]:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def _login(username: str) -> RawTestClient:
    client = _client()
    registered = client.post(
        "/api/auth/register",
        json={"username": username, "password": "study1234"},
        headers=_csrf(client),
    )
    assert registered.status_code == 201
    logged = client.post(
        "/api/auth/login",
        json={"username": username, "password": "study1234", "user_id": 1},
        headers=_csrf(client),
    )
    assert logged.status_code == 200
    assert logged.json()["username"] == username
    assert "password_hash" not in logged.json()
    return client


def _send(client: RawTestClient, method: str, url: str, **kwargs):
    headers = dict(kwargs.pop("headers", {}) or {})
    headers.setdefault("X-CSRF-Token", client.cookies.get("studymate_csrf"))
    kwargs["headers"] = headers
    return getattr(client, method)(url, **kwargs)


def _goal(client: RawTestClient, title: str) -> dict:
    response = _send(client, "post", "/api/goals", json=GOAL | {"title": title})
    assert response.status_code == 201, response.text
    return response.json()


def test_users_only_see_and_change_their_own_records() -> None:
    anonymous = _client()
    assert anonymous.get("/api/goals").status_code == 401
    assert anonymous.get("/api/learning/growth").status_code == 401
    assert anonymous.get("/api/learning/diagnosis-sources").status_code == 401

    suffix = uuid.uuid4().hex[:8]
    user_a = _login(f"a_{suffix}")
    user_b = _login(f"b_{suffix}")
    local = _client()
    local_login = local.post(
        "/api/auth/login",
        json={"username": "local", "password": LOCAL_PASSWORD},
        headers=_csrf(local),
    )
    assert local_login.status_code == 200
    local_goal = _goal(local, f"local 的历史目标 {suffix}")
    goal_a = _goal(user_a, f"A 的目标 {suffix}")
    goal_b = _goal(user_b, f"B 的目标 {suffix}")

    titles_a = {item["title"] for item in user_a.get("/api/goals").json()}
    titles_b = {item["title"] for item in user_b.get("/api/goals").json()}
    assert goal_a["title"] in titles_a
    assert goal_b["title"] not in titles_a
    assert local_goal["title"] not in titles_a
    assert goal_b["title"] in titles_b
    assert goal_a["title"] not in titles_b
    assert user_a.get(f"/api/goals/{goal_b['id']}").status_code == 404
    assert _send(user_a, "put", f"/api/goals/{goal_b['id']}", json=GOAL | {"title": "改掉 B"}).status_code == 404
    assert _send(user_a, "delete", f"/api/goals/{goal_b['id']}").status_code == 404
    assert user_b.get(f"/api/goals/{goal_b['id']}").status_code == 200

    forged = _send(user_a, "post", "/api/goals", json=GOAL | {"title": f"伪造 {suffix}", "user_id": goal_b["user_id"]})
    assert forged.status_code == 201
    assert forged.json()["user_id"] == goal_a["user_id"]
    assert forged.json()["user_id"] != goal_b["user_id"]

    by_query = user_a.get("/api/goals", params={"user_id": goal_b["user_id"]})
    assert by_query.status_code == 200
    query_titles = {item["title"] for item in by_query.json()}
    assert goal_a["title"] in query_titles
    assert goal_b["title"] not in query_titles
    by_header = user_a.get("/api/goals", headers={"X-User-Id": str(goal_b["user_id"])})
    assert by_header.status_code == 200
    header_titles = {item["title"] for item in by_header.json()}
    assert goal_a["title"] in header_titles
    assert goal_b["title"] not in header_titles
    by_path = user_a.get(f"/api/users/{goal_b['user_id']}/goals")
    assert by_path.status_code == 404
    assert user_a.get("/api/goals").status_code == 200

    problem_b = _send(user_b, "post", "/api/problems", json=PROBLEM | {"title": f"B 的题目 {suffix}"}).json()["problem"]["id"]
    problem_a = _send(user_a, "post", "/api/problems", json=PROBLEM | {"title": f"A 的题目 {suffix}"}).json()["problem"]["id"]
    assert user_a.get(f"/api/problems/{problem_b}").status_code == 404
    assert user_a.get(f"/api/problems/{problem_b}/draft").status_code == 404
    assert _send(user_a, "post", f"/api/problems/{problem_b}/test-cases", json={"name": "越权", "input_data": "1", "expected_output": "1"}).status_code == 404
    draft = _send(user_b, "put", f"/api/problems/{problem_b}/draft", json={"language": "cpp", "source_code": "int main(){return 0;}"})
    assert draft.status_code == 200
    assert user_a.get(f"/api/problems/{problem_b}/draft").status_code == 404
    submission = _send(user_b, "post", f"/api/problems/{problem_b}/submissions", json={"language": "cpp", "source_code": "int main(){return 0;}"})
    assert submission.status_code == 201
    submission_id = submission.json()["id"]
    assert user_a.get(f"/api/submissions/{submission_id}").status_code == 404
    with Session(engine) as session:
        row = session.get(ProblemSubmission, submission_id)
        assert row is not None
        now = datetime.now(timezone.utc)
        case = ProblemTestCase(
            problem_id=row.problem_id,
            name="b-only",
            input_data="1",
            expected_output="B-SECRET-OUTPUT",
            created_at=now,
            updated_at=now,
        )
        session.add(case)
        session.commit()
        session.refresh(case)
        result = ProblemJudgeResult(
            user_id=row.user_id,
            submission_id=row.id,
            problem_id=row.problem_id,
            status="accepted",
            created_at=now,
        )
        session.add(result)
        session.commit()
        session.refresh(result)
        session.add(
            ProblemJudgeCaseResult(
                judge_result_id=result.id,
                test_case_id=case.id,
                status="accepted",
                actual_output="B-SECRET-OUTPUT",
                expected_output="B-SECRET-OUTPUT",
            )
        )
        session.commit()
    hidden = user_a.get(f"/api/submissions/{submission_id}/judge-result")
    assert hidden.status_code == 404
    assert "B-SECRET-OUTPUT" not in hidden.text
    visible = user_b.get(f"/api/submissions/{submission_id}/judge-result")
    assert visible.status_code == 200
    assert "B-SECRET-OUTPUT" in visible.text
    assert _send(user_a, "post", f"/api/submissions/{submission_id}/judge").status_code == 404

    with Session(engine) as session:
        now = datetime.now(timezone.utc)
        point = KnowledgePoint(goal_id=goal_b["id"], name=f"B 的知识点 {suffix}", created_at=now, updated_at=now)
        session.add(point)
        session.commit()
        session.refresh(point)
        quiz = Quiz(goal_id=goal_b["id"], title=f"B 的检测 {suffix}", status="completed", score=80, created_at=now, submitted_at=now)
        session.add(quiz)
        session.add(
            KnowledgeMasteryEvent(
                knowledge_point_id=point.id,
                new_level=80,
                quiz_score=80,
                reason="隔离",
                created_at=now,
            )
        )
        session.add(
            ReviewSchedule(
                goal_id=goal_b["id"],
                knowledge_point_id=point.id,
                next_review_date=date.today(),
                reason="隔离",
                updated_at=now,
            )
        )
        session.add(
            TrainingRecommendation(
                user_id=goal_b["user_id"],
                goal_id=goal_b["id"],
                knowledge_point_id=point.id,
                category="knowledge_understanding",
                title=f"B 的建议 {suffix}",
                estimated_minutes=20,
                priority=1,
                completion_criteria="看一遍解析",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
        session.refresh(quiz)
        schedule = session.exec(select(ReviewSchedule).where(ReviewSchedule.knowledge_point_id == point.id)).one()
        recommendation = session.exec(select(TrainingRecommendation).where(TrainingRecommendation.user_id == goal_b["user_id"])).one()
        point_id = point.id
        quiz_id = quiz.id
        schedule_id = schedule.id
        recommendation_id = recommendation.id
        schedules_before = session.exec(select(func.count()).select_from(ReviewSchedule)).one()

    assert user_a.get(f"/api/knowledge/{point_id}").status_code == 404
    assert user_a.get(f"/api/quizzes/{quiz_id}").status_code == 404
    assert user_a.get(f"/api/quizzes/{quiz_id}/result").status_code == 404
    assert user_a.get(f"/api/reviews/{schedule_id}").status_code == 404
    assert user_a.get(f"/api/learning/recommendations/{recommendation_id}").status_code == 404
    session_b = _send(user_b, "post", "/api/tutor/sessions", json={"goal_id": goal_b["id"]})
    assert session_b.status_code == 201
    assert user_a.get(f"/api/tutor/sessions/{session_b.json()['id']}").status_code == 404

    assert user_a.get("/api/reviews/today").status_code == 200
    other_growth = user_a.get(
        "/api/learning/growth",
        params={"goal_id": goal_b["id"], "user_id": goal_b["user_id"]},
        headers={"X-User-Id": str(goal_b["user_id"])},
    )
    assert other_growth.status_code == 404
    own_growth = user_a.get("/api/learning/growth", params={"user_id": goal_b["user_id"], "days": 30})
    assert own_growth.status_code == 200
    assert own_growth.json()["quizzes"]["count"] == 0
    assert goal_b["title"] not in own_growth.text
    assert f"B 的知识点 {suffix}" not in own_growth.text
    assert f"B 的检测 {suffix}" not in own_growth.text
    sources = user_a.get(
        "/api/learning/diagnosis-sources",
        params={"user_id": goal_b["user_id"]},
        headers={"X-User-Id": str(goal_b["user_id"])},
    )
    assert sources.status_code == 200
    assert goal_b["title"] not in sources.text
    assert f"B 的知识点 {suffix}" not in sources.text
    assert f"B 的检测 {suffix}" not in sources.text
    with Session(engine) as session:
        assert session.exec(select(func.count()).select_from(ReviewSchedule)).one() == schedules_before
        assert session.exec(select(ReviewSchedule).where(ReviewSchedule.knowledge_point_id == point_id)).one().goal_id == goal_b["id"]
        users_before = session.exec(select(func.count()).select_from(User)).one()
    assert user_a.get("/api/learning/diagnosis-sources").status_code == 200
    with Session(engine) as session:
        assert session.exec(select(func.count()).select_from(User)).one() == users_before
        assert session.exec(select(User).where(User.username == "local")).one().id == local_login.json()["id"]
        assert session.get(LearningGoal, local_goal["id"]) is not None

    assert _send(user_a, "delete", f"/api/goals/{goal_a['id']}").status_code == 204
    assert user_b.get(f"/api/goals/{goal_b['id']}").status_code == 200
    assert _send(user_a, "delete", f"/api/problems/{problem_a}").status_code == 204
    assert user_b.get(f"/api/problems/{problem_b}").status_code == 200

    rejected = user_a.post("/api/goals", json=GOAL | {"title": f"缺少令牌 {suffix}"})
    assert rejected.status_code == 403
    cookie = user_a.cookies.get("studymate_csrf") or ""
    forged_token = user_a.post(
        "/api/goals",
        json=GOAL | {"title": f"伪造令牌 {suffix}"},
        headers={"X-CSRF-Token": "a" * len(cookie)},
    )
    assert forged_token.status_code == 403
    assert user_b.get(f"/api/goals/{goal_b['id']}").status_code == 200
