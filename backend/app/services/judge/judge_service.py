"""调度判题。正确性只来自容器里的编译、运行和输出比对。"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, delete, select

from app.database import engine
from app.models.judge import ProblemJudgeCaseResult, ProblemJudgeResult
from app.models.practice import ProblemLearningStatus
from app.models.problem import Problem, ProblemTestCase
from app.models.submission import ProblemSubmission
from app.services import goal_service
from app.services.ai.deepseek_client import complete_json
from app.services.ai.errors import AIError
from app.services.ai.prompt_builder import MAX_ATTEMPTS, build_repair_messages
from app.services.judge.docker_runner import JudgeEnvironmentError, ProgramExecution, run_program
from app.services.judge.output_comparator import outputs_match
from app.services.submission_service import _owned_submission

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "judge_analysis.txt"
FINAL_STATUSES = {"accepted", "wrong_answer", "compile_error", "time_limit_exceeded", "runtime_error", "system_error"}
CODE_STATUSES = {"accepted", "wrong_answer", "compile_error", "time_limit_exceeded", "runtime_error"}
STORE_LIMIT = 4000
_guard = threading.Lock()
_active: set[int] = set()


def request_judge(session: Session, submission_id: int, background: BackgroundTasks) -> dict:
    submission = _owned_submission(session, submission_id)
    cases = _cases(session, submission.problem_id)
    if not cases:
        raise HTTPException(status_code=400, detail="缺少测试数据，无法判题")
    with _guard:
        existing = _result_row(session, submission.id)
        if existing is not None and existing.status in FINAL_STATUSES:
            return _payload(session, existing)
        if submission.id in _active:
            return _payload(session, existing) if existing is not None else {"submission_id": submission.id, "status": "judging"}
        _active.add(submission.id)
        now = datetime.now(timezone.utc)
        if existing is None:
            existing = ProblemJudgeResult(
                user_id=submission.user_id,
                submission_id=submission.id,
                problem_id=submission.problem_id,
                status="judging",
                created_at=now,
            )
        else:
            existing.status = "judging"
            existing.error_message = ""
        submission.status = "judging"
        session.add(existing)
        session.add(submission)
        try:
            goal_service.commit_or_raise(session)
            session.refresh(existing)
        except Exception:
            _active.discard(submission.id)
            raise
    background.add_task(execute_judge, submission.id)
    return _payload(session, existing)


def execute_judge(submission_id: int) -> None:
    try:
        with Session(engine) as session:
            _execute(session, submission_id)
    finally:
        with _guard:
            _active.discard(submission_id)


def get_result(session: Session, submission_id: int) -> dict:
    submission = _owned_submission(session, submission_id)
    row = _result_row(session, submission.id)
    if row is None:
        raise HTTPException(status_code=404, detail="还没有判题结果")
    return _payload(session, row)


def judge_history(session: Session, problem_id: int) -> dict:
    from app.services.problem_service import _owned_problem

    problem = _owned_problem(session, problem_id)
    user = goal_service.ensure_local_user(session)
    rows = session.exec(
        select(ProblemJudgeResult)
        .where(ProblemJudgeResult.user_id == user.id, ProblemJudgeResult.problem_id == problem.id)
        .order_by(ProblemJudgeResult.id.desc())
    ).all()
    return {"results": [_payload(session, row, include_cases=False) for row in rows]}


def analyze_failure(session: Session, submission_id: int) -> dict:
    submission = _owned_submission(session, submission_id)
    row = _result_row(session, submission.id)
    if row is None or row.status == "judging":
        raise HTTPException(status_code=400, detail="还没有完成判题")
    if row.status == "accepted":
        raise HTTPException(status_code=400, detail="已经通过，不需要错误分析")
    if row.status == "system_error":
        raise HTTPException(status_code=400, detail="这是判题环境的问题，不会交给模型猜测代码对错")
    problem = session.get(Problem, submission.problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    try:
        analysis = _request_analysis(problem, submission, row, _case_rows(session, row.id))
    except (AIError, ValueError) as exc:
        message = exc.message if isinstance(exc, AIError) else str(exc)
        row.ai_analysis_error = message[:500]
        session.add(row)
        goal_service.commit_or_raise(session)
        raise HTTPException(status_code=getattr(exc, "status_code", 502), detail=message) from None
    row.ai_analysis = json.dumps(analysis, ensure_ascii=False)
    row.ai_analysis_error = ""
    session.add(row)
    goal_service.commit_or_raise(session)
    return _payload(session, row)


def _execute(session: Session, submission_id: int) -> None:
    submission = session.get(ProblemSubmission, submission_id)
    result = _result_row(session, submission_id)
    if submission is None or result is None:
        return
    cases = _cases(session, submission.problem_id)
    if not cases:
        _finish_environment(session, submission, result, "缺少测试数据，无法判题")
        return
    try:
        execution = run_program(submission.source_code, [case.input_data for case in cases])
    except JudgeEnvironmentError as exc:
        _finish_environment(session, submission, result, str(exc))
        return
    except Exception:
        _finish_environment(session, submission, result, "判题过程出现异常，没有把这次记成答案错误")
        return
    _apply_execution(session, submission, result, cases, execution)


def _apply_execution(
    session: Session,
    submission: ProblemSubmission,
    result: ProblemJudgeResult,
    cases: list[ProblemTestCase],
    execution: ProgramExecution,
) -> None:
    session.exec(delete(ProblemJudgeCaseResult).where(ProblemJudgeCaseResult.judge_result_id == result.id))
    if execution.compiled and len(execution.cases) != len(cases):
        _finish_environment(session, submission, result, "判题容器返回的测试结果数量不正确")
        return
    if not execution.compiled:
        result.status = "compile_error"
        result.total_cases = len(cases)
        result.passed_cases = 0
        result.failed_cases = len(cases)
        result.compile_output = execution.compile_output[-8000:]
        result.error_message = "编译失败"
        result.execution_time_ms = 0
        result.memory_used_kb = 0
        _save_final(session, submission, result)
        return
    passed = 0
    statuses: list[str] = []
    total_time = 0
    max_memory = 0
    for case, outcome in zip(cases, execution.cases, strict=False):
        if outcome.status == "ok" and outputs_match(outcome.stdout, case.expected_output):
            case_status = "accepted"
            passed += 1
        elif outcome.status == "ok":
            case_status = "wrong_answer"
        else:
            case_status = outcome.status
        statuses.append(case_status)
        total_time += outcome.time_ms
        max_memory = max(max_memory, outcome.memory_kb)
        session.add(
            ProblemJudgeCaseResult(
                judge_result_id=result.id,
                test_case_id=case.id,
                status=case_status,
                execution_time_ms=outcome.time_ms,
                actual_output=outcome.stdout[:STORE_LIMIT],
                expected_output=case.expected_output[:STORE_LIMIT],
                error_message=outcome.error[:1000],
            )
        )
    result.total_cases = len(cases)
    result.passed_cases = passed
    result.failed_cases = len(cases) - passed
    result.execution_time_ms = total_time
    result.memory_used_kb = max_memory
    result.compile_output = ""
    if passed == len(cases) and len(cases) > 0:
        result.status = "accepted"
        result.error_message = ""
    elif "time_limit_exceeded" in statuses:
        result.status = "time_limit_exceeded"
        result.error_message = "有测试数据运行超时"
    elif "runtime_error" in statuses:
        result.status = "runtime_error"
        result.error_message = "有测试数据运行异常"
    else:
        result.status = "wrong_answer"
        result.error_message = "有测试数据输出不符合预期"
    _save_final(session, submission, result)


def _finish_environment(session: Session, submission: ProblemSubmission, result: ProblemJudgeResult, message: str) -> None:
    result.status = "system_error"
    result.error_message = message[:2000]
    result.judged_at = datetime.now(timezone.utc)
    submission.status = "system_error"
    session.add(result)
    session.add(submission)
    goal_service.commit_or_raise(session)


def _save_final(session: Session, submission: ProblemSubmission, result: ProblemJudgeResult) -> None:
    result.judged_at = datetime.now(timezone.utc)
    submission.status = result.status
    session.add(result)
    session.add(submission)
    if result.status in CODE_STATUSES:
        _update_learning_status(session, submission, result.status)
    goal_service.commit_or_raise(session)


def _update_learning_status(session: Session, submission: ProblemSubmission, status: str) -> None:
    row = session.exec(
        select(ProblemLearningStatus).where(
            ProblemLearningStatus.user_id == submission.user_id,
            ProblemLearningStatus.problem_id == submission.problem_id,
        )
    ).first()
    now = datetime.now(timezone.utc)
    if row is None:
        row = ProblemLearningStatus(
            user_id=submission.user_id,
            problem_id=submission.problem_id,
            status=status,
            created_at=now,
            updated_at=now,
        )
    else:
        row.status = status
        row.updated_at = now
    session.add(row)


def _request_analysis(problem: Problem, submission: ProblemSubmission, result: ProblemJudgeResult, cases: list[ProblemJudgeCaseResult]) -> dict:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    failed = [
        {
            "status": item.status,
            "expected_output": item.expected_output[:1500],
            "actual_output": item.actual_output[:1500],
            "error_message": item.error_message,
        }
        for item in cases
        if item.status != "accepted"
    ]
    payload = {
        "title": problem.title,
        "description": problem.description[:4000],
        "source_code": submission.source_code[:8000],
        "judge_status": result.status,
        "compile_output": result.compile_output[:3000],
        "error_message": result.error_message,
        "failed_cases": failed[:5],
    }
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    last_error = "分析结果未通过校验"
    raw = ""
    for _ in range(MAX_ATTEMPTS):
        raw = complete_json(messages, max_tokens=1600)
        try:
            return _parse_analysis(raw)
        except ValueError as exc:
            last_error = str(exc)
            messages = build_repair_messages(messages, raw, last_error)
    raise AIError(last_error, status_code=502)


def _parse_analysis(raw: str) -> dict:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("分析结果不是对象")
    required = ("likely_cause", "location", "explanation", "direction", "patch_example", "confidence_note")
    parsed = {}
    for key in required:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"缺少 {key}")
        parsed[key] = value.strip()[:2000]
    return parsed


def _cases(session: Session, problem_id: int | None) -> list[ProblemTestCase]:
    return list(session.exec(select(ProblemTestCase).where(ProblemTestCase.problem_id == problem_id).order_by(ProblemTestCase.id)).all())


def _result_row(session: Session, submission_id: int | None) -> ProblemJudgeResult | None:
    return session.exec(select(ProblemJudgeResult).where(ProblemJudgeResult.submission_id == submission_id)).first()


def _case_rows(session: Session, result_id: int | None) -> list[ProblemJudgeCaseResult]:
    return list(session.exec(select(ProblemJudgeCaseResult).where(ProblemJudgeCaseResult.judge_result_id == result_id).order_by(ProblemJudgeCaseResult.id)).all())


def _payload(session: Session, row: ProblemJudgeResult, *, include_cases: bool = True) -> dict:
    payload = {
        "id": row.id,
        "submission_id": row.submission_id,
        "problem_id": row.problem_id,
        "status": row.status,
        "total_cases": row.total_cases,
        "passed_cases": row.passed_cases,
        "failed_cases": row.failed_cases,
        "compile_output": row.compile_output,
        "error_message": row.error_message,
        "execution_time_ms": row.execution_time_ms,
        "memory_used_kb": row.memory_used_kb,
        "judged_at": row.judged_at,
        "ai_analysis": _load_analysis(row.ai_analysis),
        "ai_analysis_error": row.ai_analysis_error,
    }
    if include_cases:
        payload["cases"] = [
            {
                "id": item.id,
                "test_case_id": item.test_case_id,
                "status": item.status,
                "execution_time_ms": item.execution_time_ms,
                "actual_output": item.actual_output,
                "expected_output": item.expected_output,
                "error_message": item.error_message,
            }
            for item in _case_rows(session, row.id)
        ]
    return payload


def _load_analysis(raw: str) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
