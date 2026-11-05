"""诊断汇总只读取已有记录，不写库，也不把两套知识点连起来。"""

import inspect
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models.goal import LearningGoal
from app.models.judge import ProblemJudgeResult
from app.models.knowledge import KnowledgePoint
from app.models.plan import StudyPlan, StudyTask
from app.models.practice import ProblemLearningStatus, ProblemWrongRecord
from app.models.problem import Problem
from app.models.quiz import KnowledgeMasteryEvent, Quiz
from app.models.review import ReviewRecord, ReviewSchedule
from app.models.submission import ProblemSubmission
from app.models.tutor import TutorMessage, TutorSession
from app.models.user import User
from app.services import diagnosis_service
from app.services.actor import acting_as
from app.services.practice_service import mastery_and_review_counts

client = TestClient(app)


def _counts() -> dict[str, int]:
    with Session(engine) as session:
        return mastery_and_review_counts(session) | {
            "goals": len(session.exec(select(LearningGoal)).all()),
            "problems": len(session.exec(select(Problem)).all()),
            "submissions": len(session.exec(select(ProblemSubmission)).all()),
            "judges": len(session.exec(select(ProblemJudgeResult)).all()),
            "statuses": len(session.exec(select(ProblemLearningStatus)).all()),
            "wrongs": len(session.exec(select(ProblemWrongRecord)).all()),
            "messages": len(session.exec(select(TutorMessage)).all()),
        }


def test_snapshot_reads_real_rows_and_ignores_other_users() -> None:
    now = datetime.now(timezone.utc)
    yesterday = date.today() - timedelta(days=1)
    with Session(engine) as session:
        local = session.exec(select(User).where(User.username == "local")).one()
        other = User(username="other-diagnosis")
        session.add(other)
        session.commit()
        session.refresh(other)
        goal = LearningGoal(user_id=local.id, title="诊断目标", description="只读", target_date=date.today(), daily_minutes=25, created_at=now, updated_at=now)
        hidden_goal = LearningGoal(user_id=other.id, title="别人的目标", description="不可见", target_date=date.today(), daily_minutes=25, created_at=now, updated_at=now)
        session.add(goal)
        session.add(hidden_goal)
        session.commit()
        session.refresh(goal)
        session.refresh(hidden_goal)
        point = KnowledgePoint(goal_id=goal.id, name="链式法则", status="needs_review", mastery_level=48, created_at=now, updated_at=now)
        hidden_point = KnowledgePoint(goal_id=hidden_goal.id, name="别人的知识点", status="mastered", mastery_level=95, created_at=now, updated_at=now)
        session.add(point)
        session.add(hidden_point)
        session.commit()
        session.refresh(point)
        session.refresh(hidden_point)
        session.add(KnowledgeMasteryEvent(knowledge_point_id=point.id, previous_level=None, new_level=40, quiz_score=40, reason="第一次", created_at=now - timedelta(days=2)))
        session.add(KnowledgeMasteryEvent(knowledge_point_id=point.id, previous_level=40, new_level=48, quiz_score=55, reason="第二次", created_at=now - timedelta(days=1)))
        session.add(KnowledgeMasteryEvent(knowledge_point_id=hidden_point.id, previous_level=None, new_level=95, quiz_score=99, reason="别人的", created_at=now))
        session.add(ReviewSchedule(goal_id=goal.id, knowledge_point_id=point.id, next_review_date=yesterday, last_score=55, last_reviewed_at=now - timedelta(days=3)))
        plan = StudyPlan(goal_id=goal.id, plan_date=date.today(), title="今天", description="计划", total_minutes=25, created_at=now, updated_at=now)
        session.add(plan)
        session.commit()
        session.refresh(plan)
        session.add(StudyTask(plan_id=plan.id, title="阅读", description="看定义", task_type="study", estimated_minutes=10, status="completed", completed_at=now, created_at=now, updated_at=now))
        quiz = Quiz(goal_id=goal.id, title="检测", status="completed", score=55, submitted_at=now, created_at=now)
        session.add(quiz)
        schedule = session.exec(select(ReviewSchedule).where(ReviewSchedule.knowledge_point_id == point.id)).one()
        session.add(ReviewRecord(schedule_id=schedule.id, knowledge_point_id=point.id, reviewed_at=now - timedelta(days=3), score=55, result="fail", next_interval=2, next_review_date=yesterday, created_at=now))
        own = Problem(user_id=local.id, title="本地通过题", difficulty="easy", created_at=now, updated_at=now)
        failed = Problem(user_id=local.id, title="环境异常题", difficulty="medium", created_at=now, updated_at=now)
        noted = Problem(user_id=local.id, title="自评题", difficulty="unknown", created_at=now, updated_at=now)
        hidden_problem = Problem(user_id=other.id, title="别人的题", created_at=now, updated_at=now)
        session.add(own)
        session.add(failed)
        session.add(noted)
        session.add(hidden_problem)
        session.commit()
        session.refresh(own)
        session.refresh(failed)
        session.refresh(noted)
        session.refresh(hidden_problem)
        session.add(ProblemLearningStatus(user_id=local.id, problem_id=own.id, status="accepted", created_at=now, updated_at=now))
        session.add(ProblemLearningStatus(user_id=local.id, problem_id=noted.id, status="self_completed", created_at=now, updated_at=now))
        accepted_submission = ProblemSubmission(user_id=local.id, problem_id=own.id, source_code="int main(){return 0;}", status="accepted", submitted_at=now)
        error_submission = ProblemSubmission(user_id=local.id, problem_id=failed.id, source_code="int main(){return 0;}", status="system_error", submitted_at=now)
        hidden_submission = ProblemSubmission(user_id=other.id, problem_id=hidden_problem.id, source_code="int main(){return 0;}", status="accepted", submitted_at=now)
        session.add(accepted_submission)
        session.add(error_submission)
        session.add(hidden_submission)
        session.commit()
        session.refresh(accepted_submission)
        session.refresh(error_submission)
        session.refresh(hidden_submission)
        session.add(ProblemJudgeResult(user_id=local.id, submission_id=accepted_submission.id, problem_id=own.id, status="accepted", total_cases=1, passed_cases=1, judged_at=now, created_at=now))
        session.add(ProblemJudgeResult(user_id=local.id, submission_id=error_submission.id, problem_id=failed.id, status="system_error", error_message="没有 Docker", judged_at=now, created_at=now))
        session.add(ProblemJudgeResult(user_id=other.id, submission_id=hidden_submission.id, problem_id=hidden_problem.id, status="accepted", total_cases=1, passed_cases=1, judged_at=now, created_at=now))
        session.add(ProblemWrongRecord(user_id=local.id, problem_id=own.id, reason_type="boundary", reason_detail="空串", created_at=now, updated_at=now))
        own_chat = TutorSession(user_id=local.id, goal_id=goal.id, title="提问", created_at=now, updated_at=now)
        other_chat = TutorSession(user_id=other.id, goal_id=hidden_goal.id, title="别人", created_at=now, updated_at=now)
        session.add(own_chat)
        session.add(other_chat)
        session.commit()
        session.refresh(own_chat)
        session.refresh(other_chat)
        session.add(TutorMessage(session_id=own_chat.id, role="user", content="链式法则怎么用", knowledge_point_ids_json=f"[{point.id}]", created_at=now))
        session.add(TutorMessage(session_id=own_chat.id, role="assistant", content="解释", knowledge_point_ids_json=f"[{point.id}, {hidden_point.id}]", created_at=now))
        session.add(TutorMessage(session_id=other_chat.id, role="user", content="别人问的", knowledge_point_ids_json=f"[{point.id}]", created_at=now))
        session.commit()

    before = _counts()
    first = client.get("/api/learning/diagnosis-sources")
    second = client.get("/api/learning/diagnosis-sources")
    assert first.status_code == 200
    assert second.json() == first.json()
    assert _counts() == before
    body = first.json()
    assert body["knowledge"]["goal_count"] == 1
    assert body["knowledge"]["point_count"] == 1
    point_row = body["knowledge"]["points"][0]
    assert point_row["name"] == "链式法则"
    assert point_row["recent_scores"] == [40, 55]
    assert point_row["latest_score"] == 55
    assert point_row["consecutive_low_scores"] == 2
    assert point_row["review"]["overdue"] is True
    assert body["practice"]["problem_count"] == 3
    assert body["practice"]["learning_status_counts"]["accepted"] == 1
    assert body["practice"]["learning_status_counts"]["self_completed"] == 1
    assert body["practice"]["learning_status_counts"]["todo"] == 1
    assert body["practice"]["judge_result_counts"]["accepted"] == 1
    assert body["practice"]["judge_result_counts"]["system_error"] == 1
    assert body["practice"]["judge_result_counts"]["wrong_answer"] == 0
    titles = {item["title"]: item for item in body["practice"]["problems"]}
    assert titles["自评题"]["learning_status"] == "self_completed"
    assert titles["环境异常题"]["learning_status"] == "todo"
    assert titles["本地通过题"]["wrong_reason_type"] == "boundary"
    assert body["tutor"]["asked"] == [{"knowledge_point_id": point_row["id"], "name": "链式法则", "user_message_count": 1}]
    assert body["behavior"]["completed_task_count"] == 1
    assert body["behavior"]["completed_quiz_count"] == 1
    assert body["behavior"]["review_record_count"] == 1
    assert body["meanings"]["accepted"].startswith("本地判题通过")
    assert "别人的知识点" not in str(body)
    assert "别人的题" not in str(body)


def test_empty_snapshot_and_no_model_or_writes() -> None:
    source = inspect.getsource(diagnosis_service)
    assert "complete_json" not in source
    assert "session.add" not in source
    assert "commit" not in source
    with Session(engine) as session:
        before = mastery_and_review_counts(session)
        local = session.exec(select(User).where(User.username == "local")).one()
        with acting_as(local.id):
            payload = diagnosis_service.snapshot(session)
        assert list(session.new) == []
        assert list(session.dirty) == []
    assert payload["knowledge"]["points"] == []
    assert payload["practice"]["problems"] == []
    assert payload["practice"]["judge_result_counts"]["system_error"] == 0
    assert payload["tutor"]["asked"] == []
    assert payload["behavior"]["active_dates"] == []
    with Session(engine) as session:
        assert mastery_and_review_counts(session) == before
    assert client.get("/api/learning/diagnosis-sources").json()["knowledge"]["goal_count"] == 0
