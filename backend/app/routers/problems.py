"""题库接口。打开和刷新页面不会调用 DeepSeek。"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session

from app.database import get_session
from app.schemas.practice import LearningStatusUpdate, PracticeComplete, WrongWrite
from app.schemas.problem import ClassificationUpdate, NoteWrite, ProblemWrite, TestCaseInput, TopicConfirm
from app.schemas.submission import DraftWrite, SubmissionWrite
from app.services import practice_service, problem_service, submission_service
from app.services.judge import judge_service
from app.services.ai.errors import AIError

router = APIRouter(prefix="/problems", tags=["problems"])


def _call(action):
    try:
        return action()
    except AIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None


@router.get("/statistics")
def problem_statistics(session: Session = Depends(get_session)) -> dict:
    return problem_service.statistics(session)


@router.get("/practice-statistics")
def practice_statistics(session: Session = Depends(get_session)) -> dict:
    return practice_service.practice_statistics(session)


@router.get("/practice-trends")
def practice_trends(session: Session = Depends(get_session)) -> dict:
    return practice_service.practice_trends(session)


@router.get("/wrong")
def list_wrong(
    topic_id: int | None = Query(default=None, ge=1),
    difficulty: str = "",
    session: Session = Depends(get_session),
) -> dict:
    return practice_service.list_wrong(session, topic_id=topic_id, difficulty=difficulty)


@router.get("/topics")
def problem_topics(session: Session = Depends(get_session)) -> dict:
    return problem_service.topics(session)


@router.delete("/topics/{topic_id}", status_code=204)
def delete_topic(topic_id: int, session: Session = Depends(get_session)) -> Response:
    problem_service.delete_topic(session, topic_id)
    return Response(status_code=204)


@router.get("/knowledge/{topic_id}")
def problems_by_topic(topic_id: int, session: Session = Depends(get_session)) -> dict:
    return problem_service.problems_for_topic(session, topic_id)


@router.post("/import", status_code=201)
def import_problem(payload: ProblemWrite, session: Session = Depends(get_session)) -> dict:
    return problem_service.import_problem(session, payload)


@router.get("")
def list_problems(
    keyword: str = "",
    course: str = "",
    topic_id: int | None = Query(default=None, ge=1),
    difficulty: str = "",
    source_platform: str = "",
    analysis_status: str = "",
    session: Session = Depends(get_session),
) -> dict:
    return problem_service.list_problems(
        session,
        keyword=keyword,
        course=course,
        topic_id=topic_id,
        difficulty=difficulty,
        source_platform=source_platform,
        analysis_status=analysis_status,
    )


@router.post("", status_code=201)
def create_problem(payload: ProblemWrite, session: Session = Depends(get_session)) -> dict:
    return problem_service.create_problem(session, payload)


@router.get("/{problem_id}")
def problem_detail(problem_id: int, session: Session = Depends(get_session)) -> dict:
    return problem_service.get_problem(session, problem_id)


@router.put("/{problem_id}")
def update_problem(problem_id: int, payload: ProblemWrite, session: Session = Depends(get_session)) -> dict:
    return problem_service.update_problem(session, problem_id, payload)


@router.delete("/{problem_id}", status_code=204)
def remove_problem(problem_id: int, session: Session = Depends(get_session)) -> Response:
    problem_service.delete_problem(session, problem_id)
    return Response(status_code=204)


@router.post("/{problem_id}/analyze")
def analyze_problem(problem_id: int, session: Session = Depends(get_session)) -> dict:
    return _call(lambda: problem_service.analyze_problem(session, problem_id))


@router.put("/{problem_id}/classification")
def update_classification(
    problem_id: int, payload: ClassificationUpdate, session: Session = Depends(get_session)
) -> dict:
    return problem_service.update_classification(session, problem_id, payload)


@router.post("/{problem_id}/topics/confirm")
def confirm_topic(problem_id: int, payload: TopicConfirm, session: Session = Depends(get_session)) -> dict:
    return problem_service.confirm_topic(session, problem_id, payload)


@router.get("/{problem_id}/test-cases")
def list_cases(problem_id: int, session: Session = Depends(get_session)) -> dict:
    return problem_service.list_cases(session, problem_id)


@router.post("/{problem_id}/test-cases", status_code=201)
def add_case(problem_id: int, payload: TestCaseInput, session: Session = Depends(get_session)) -> dict:
    return problem_service.add_case(session, problem_id, payload)


@router.put("/{problem_id}/test-cases/{case_id}")
def update_case(
    problem_id: int, case_id: int, payload: TestCaseInput, session: Session = Depends(get_session)
) -> dict:
    return problem_service.update_case(session, problem_id, case_id, payload)


@router.delete("/{problem_id}/test-cases/{case_id}", status_code=204)
def remove_case(problem_id: int, case_id: int, session: Session = Depends(get_session)) -> Response:
    problem_service.delete_case(session, problem_id, case_id)
    return Response(status_code=204)


@router.get("/{problem_id}/draft")
def get_draft(problem_id: int, session: Session = Depends(get_session)) -> dict:
    return submission_service.get_draft(session, problem_id)


@router.put("/{problem_id}/draft")
def save_draft(problem_id: int, payload: DraftWrite, session: Session = Depends(get_session)) -> dict:
    return submission_service.save_draft(session, problem_id, payload)


@router.post("/{problem_id}/submissions", status_code=201)
def create_submission(problem_id: int, payload: SubmissionWrite, session: Session = Depends(get_session)) -> dict:
    return submission_service.create_submission(session, problem_id, payload)


@router.get("/{problem_id}/submissions")
def list_submissions(problem_id: int, session: Session = Depends(get_session)) -> dict:
    return submission_service.list_submissions(session, problem_id)


@router.get("/{problem_id}/judge-history")
def judge_history(problem_id: int, session: Session = Depends(get_session)) -> dict:
    return judge_service.judge_history(session, problem_id)


@router.get("/{problem_id}/learning-status")
def learning_status(problem_id: int, session: Session = Depends(get_session)) -> dict:
    return practice_service.get_learning_status(session, problem_id)


@router.patch("/{problem_id}/learning-status")
def update_learning_status(problem_id: int, payload: LearningStatusUpdate, session: Session = Depends(get_session)) -> dict:
    return practice_service.update_learning_status(session, problem_id, payload)


@router.post("/{problem_id}/practice/start")
def start_practice(problem_id: int, session: Session = Depends(get_session)) -> dict:
    return practice_service.start_practice(session, problem_id)


@router.post("/{problem_id}/practice/{record_id}/complete")
def complete_practice(
    problem_id: int, record_id: int, payload: PracticeComplete, session: Session = Depends(get_session)
) -> dict:
    return practice_service.complete_practice(session, problem_id, record_id, payload)


@router.get("/{problem_id}/practice-history")
def practice_history(problem_id: int, session: Session = Depends(get_session)) -> dict:
    return practice_service.practice_history(session, problem_id)


@router.post("/{problem_id}/wrong", status_code=201)
def add_wrong(problem_id: int, payload: WrongWrite, session: Session = Depends(get_session)) -> dict:
    return practice_service.add_wrong(session, problem_id, payload)


@router.put("/{problem_id}/wrong")
def update_wrong(problem_id: int, payload: WrongWrite, session: Session = Depends(get_session)) -> dict:
    return practice_service.update_wrong(session, problem_id, payload)


@router.delete("/{problem_id}/wrong", status_code=204)
def remove_wrong(problem_id: int, session: Session = Depends(get_session)) -> Response:
    practice_service.delete_wrong(session, problem_id)
    return Response(status_code=204)


@router.get("/{problem_id}/notes")
def get_note(problem_id: int, session: Session = Depends(get_session)) -> dict:
    return problem_service.get_note(session, problem_id)


@router.post("/{problem_id}/notes")
def save_note(problem_id: int, payload: NoteWrite, session: Session = Depends(get_session)) -> dict:
    return problem_service.save_note(session, problem_id, payload)
