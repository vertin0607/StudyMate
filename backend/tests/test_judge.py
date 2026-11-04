"""判题结果来自执行比对。没有 Docker 时不能在本机运行代码。"""

import inspect
import json

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models.judge import ProblemJudgeResult
from app.models.problem import Problem
from app.models.submission import ProblemSubmission
from app.models.user import User
from app.services.ai.errors import AIError
from app.services.judge import docker_runner
from app.services.judge.docker_runner import CaseExecution, ProgramExecution, build_run_args
from app.services.judge.output_comparator import outputs_match
from app.services.practice_service import mastery_and_review_counts

client = TestClient(app)


def problem_body(**overrides) -> dict:
    body = {
        "title": "判题题",
        "description": "读入一个整数并输出它。",
        "source_platform": "南开大学校内 OJ",
        "source_problem_id": "9001",
        "sample_input": "1\n",
        "sample_output": "1\n",
        "test_cases": [
            {"name": "自定义", "input_data": "2\n", "expected_output": "2\n", "case_type": "custom", "is_public": False, "note": ""}
        ],
    }
    body.update(overrides)
    return body


def _echo(inputs: list[str], wrong: bool) -> ProgramExecution:
    cases = []
    for raw in inputs:
        text = "9\n" if wrong and raw.startswith("2") else ("1\n" if raw.startswith("1") else "2\n")
        cases.append(CaseExecution("ok", 0, 4, 128, text, ""))
    return ProgramExecution(True, "", cases)


def test_output_rules() -> None:
    assert outputs_match("hello world   \r\n", "hello world")
    assert outputs_match("hello world\n\n", "hello world")
    assert not outputs_match("hello  world", "hello world")
    assert not outputs_match("Hello", "hello")
    assert not outputs_match("2", "1")


def test_docker_arguments_do_not_include_code_or_host_mounts() -> None:
    source = inspect.getsource(docker_runner)
    assert "shell=True" not in source
    args = build_run_args("docker", "studymate-judge-test")
    assert isinstance(args, list)
    assert args[args.index("--network") + 1] == "none"
    assert "--read-only" in args
    assert args[args.index("--cap-drop") + 1] == "ALL"
    assert "no-new-privileges" in args
    assert "--privileged" not in args
    assert "-v" not in args
    assert "docker.sock" not in args
    assert "int main" not in args


def test_judging_uses_execution_results_and_not_the_model(monkeypatch) -> None:
    calls = {"n": 0}

    def fake(source: str, inputs: list[str]) -> ProgramExecution:
        calls["n"] += 1
        if source == "return 0":
            return ProgramExecution(False, "expected ';'", [])
        return _echo(inputs, wrong=source == "wrong-code")

    monkeypatch.setattr("app.services.judge.judge_service.run_program", fake)
    monkeypatch.setattr("app.services.judge.judge_service.complete_json", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("判题不应调用模型")))
    with Session(engine) as session:
        before = mastery_and_review_counts(session)
    problem_id = client.post("/api/problems/import", json=problem_body()).json()["problem"]["id"]
    empty_created = client.post("/api/problems/import", json=problem_body(source_problem_id="9002", sample_input="", sample_output="", test_cases=[], title="无数据"))
    assert empty_created.status_code == 201
    empty_id = empty_created.json()["problem"]["id"]
    empty_submission = client.post(f"/api/problems/{empty_id}/submissions", json={"source_code": "int main(){return 0;}"}).json()["id"]
    assert client.post(f"/api/submissions/{empty_submission}/judge").status_code == 400
    assert client.get(f"/api/submissions/{empty_submission}").json()["status"] == "unjudged"

    accepted_id = client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": "accepted-code"}).json()["id"]
    assert client.post(f"/api/submissions/{accepted_id}/judge").json()["status"] == "judging"
    accepted = client.get(f"/api/submissions/{accepted_id}/judge-result").json()
    assert accepted["status"] == "accepted"
    assert accepted["passed_cases"] == 2
    assert accepted["total_cases"] == 2
    assert client.get(f"/api/problems/{problem_id}/learning-status").json()["status"] == "accepted"
    assert client.post(f"/api/submissions/{accepted_id}/judge").json()["status"] == "accepted"
    assert calls["n"] == 1
    assert client.post(f"/api/submissions/{accepted_id}/ai-analysis").status_code == 400

    wrong_id = client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": "wrong-code"}).json()["id"]
    client.post(f"/api/submissions/{wrong_id}/judge")
    wrong = client.get(f"/api/submissions/{wrong_id}/judge-result").json()
    assert wrong["status"] == "wrong_answer"
    assert wrong["passed_cases"] == 1
    assert wrong["failed_cases"] == 1
    assert client.get(f"/api/submissions/{wrong_id}").json()["source_code"] == "wrong-code"
    client.put(f"/api/problems/{problem_id}/draft", json={"source_code": "draft-only"})
    assert client.get(f"/api/submissions/{accepted_id}").json()["source_code"] == "accepted-code"

    compile_id = client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": "return 0"}).json()["id"]
    client.post(f"/api/submissions/{compile_id}/judge")
    assert client.get(f"/api/submissions/{compile_id}/judge-result").json()["status"] == "compile_error"
    assert client.get(f"/api/problems/{problem_id}/learning-status").json()["status"] == "compile_error"
    with Session(engine) as session:
        assert mastery_and_review_counts(session) == before


def test_runtime_timeout_and_spacing(monkeypatch) -> None:
    def fake(source: str, inputs: list[str]) -> ProgramExecution:
        if "loop" in source:
            return ProgramExecution(True, "", [CaseExecution("time_limit_exceeded", -1, 2000, 32, "", "运行超时") for _ in inputs])
        if "crash" in source:
            return ProgramExecution(True, "", [CaseExecution("runtime_error", 139, 2, 16, "", "退出码 139") for _ in inputs])
        return ProgramExecution(True, "", [CaseExecution("ok", 0, 1, 8, "hello world   \r\n", "") for _ in inputs])

    monkeypatch.setattr("app.services.judge.judge_service.run_program", fake)
    problem_id = client.post(
        "/api/problems/import",
        json=problem_body(source_problem_id="9003", sample_input="a\n", sample_output="hello world\n", test_cases=[]),
    ).json()["problem"]["id"]
    spaced = client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": "print"}).json()["id"]
    client.post(f"/api/submissions/{spaced}/judge")
    assert client.get(f"/api/submissions/{spaced}/judge-result").json()["status"] == "accepted"
    timed = client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": "loop"}).json()["id"]
    client.post(f"/api/submissions/{timed}/judge")
    assert client.get(f"/api/submissions/{timed}/judge-result").json()["status"] == "time_limit_exceeded"
    crashed = client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": "crash"}).json()["id"]
    client.post(f"/api/submissions/{crashed}/judge")
    body = client.get(f"/api/submissions/{crashed}/judge-result").json()
    assert body["status"] == "runtime_error"
    assert body["status"] != "wrong_answer"


def test_missing_docker_is_system_error_and_does_not_run_code(monkeypatch) -> None:
    def blocked(*_args, **_kwargs):
        raise AssertionError("没有 Docker 时不能启动进程")

    monkeypatch.setattr("app.services.judge.docker_runner.find_docker", lambda: None)
    monkeypatch.setattr("app.services.judge.docker_runner.subprocess.run", blocked)
    problem_id = client.post("/api/problems/import", json=problem_body(source_problem_id="9004")).json()["problem"]["id"]
    client.patch(f"/api/problems/{problem_id}/learning-status", json={"status": "self_completed"})
    submission_id = client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": "int main(){return 0;}"}).json()["id"]
    client.post(f"/api/submissions/{submission_id}/judge")
    result = client.get(f"/api/submissions/{submission_id}/judge-result").json()
    assert result["status"] == "system_error"
    assert "Docker Desktop" in result["error_message"]
    assert client.get(f"/api/problems/{problem_id}/learning-status").json()["status"] == "self_completed"
    with Session(engine) as session:
        other = User(username="other-judge")
        session.add(other)
        session.commit()
        session.refresh(other)
        row = session.get(ProblemSubmission, submission_id)
        assert row is not None
        row.user_id = other.id
        session.add(row)
        session.commit()
    assert client.get(f"/api/submissions/{submission_id}/judge-result").status_code == 404
    with Session(engine) as session:
        local = session.exec(select(User).where(User.username == "local")).one()
        row = session.get(ProblemSubmission, submission_id)
        parent = session.get(Problem, problem_id)
        assert row is not None and parent is not None
        row.user_id = local.id
        parent.user_id = local.id
        session.add(row)
        session.add(parent)
        session.commit()
    assert client.delete(f"/api/problems/{problem_id}").status_code == 204
    with Session(engine) as session:
        assert session.exec(select(ProblemJudgeResult).where(ProblemJudgeResult.problem_id == problem_id)).all() == []


def test_ai_analysis_does_not_replace_the_verdict(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.judge.judge_service.run_program",
        lambda _source, inputs: ProgramExecution(True, "", [CaseExecution("ok", 0, 1, 1, "0", "") for _ in inputs]),
    )
    problem_id = client.post("/api/problems/import", json=problem_body(source_problem_id="9005", sample_output="1\n", test_cases=[])).json()["problem"]["id"]
    submission_id = client.post(f"/api/problems/{problem_id}/submissions", json={"source_code": "wrong"}).json()["id"]
    client.post(f"/api/submissions/{submission_id}/judge")
    assert client.get(f"/api/submissions/{submission_id}/judge-result").json()["status"] == "wrong_answer"

    def fail(_messages, **_kwargs):
        raise AIError("模型暂时不可用", status_code=503)

    monkeypatch.setattr("app.services.judge.judge_service.complete_json", fail)
    assert client.post(f"/api/submissions/{submission_id}/ai-analysis").status_code == 503
    assert client.get(f"/api/submissions/{submission_id}/judge-result").json()["status"] == "wrong_answer"
    monkeypatch.setattr(
        "app.services.judge.judge_service.complete_json",
        lambda _messages, **_kwargs: json.dumps(
            {
                "likely_cause": "输出和预期不一致",
                "location": "输出语句",
                "explanation": "判题看到的实际输出不是预期输出",
                "direction": "检查输出内容",
                "patch_example": "先打印预期中的整数",
                "confidence_note": "这是根据判题结果作出的推测，不是重新执行后的验证",
            },
            ensure_ascii=False,
        ),
    )
    analyzed = client.post(f"/api/submissions/{submission_id}/ai-analysis").json()
    assert analyzed["status"] == "wrong_answer"
    assert analyzed["ai_analysis"]["confidence_note"].startswith("这是根据判题结果")
    assert client.get(f"/api/submissions/{submission_id}").json()["source_code"] == "wrong"
