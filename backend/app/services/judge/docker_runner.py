"""通过 Docker 启动一次性只读容器。用户代码只放在标准输入里，不拼进命令。"""

import shutil
import struct
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.services.judge.config import (
    CPUS,
    DOCKER_MISSING_MESSAGE,
    DOCKER_NOT_RUNNING_MESSAGE,
    IMAGE,
    IMAGE_MISSING_MESSAGE,
    MEMORY_MB,
    OUTPUT_LIMIT_BYTES,
    PIDS_LIMIT,
    TMPFS_SIZE,
)
from app.services.judge.config import COMPILE_TIMEOUT_SECONDS, RUN_TIMEOUT_SECONDS

MAGIC = b"SMJ1"
WINDOWS_DOCKER_CANDIDATES = (
    Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"),
    Path.home() / "AppData" / "Local" / "Programs" / "DockerDesktop" / "resources" / "bin" / "docker.exe",
)
DAEMON_HINTS = (
    "dockerDesktopLinuxEngine",
    "Is the docker daemon running",
    "failed to connect to the docker API",
    "Cannot connect to the Docker daemon",
    "error during connect",
)


class JudgeEnvironmentError(Exception):
    """判题环境不可用。这不是用户代码的答案错误。"""


@dataclass
class CaseExecution:
    status: str
    exit_code: int
    time_ms: int
    memory_kb: int
    stdout: str
    error: str


@dataclass
class ProgramExecution:
    compiled: bool
    compile_output: str
    cases: list[CaseExecution]


def find_docker() -> str | None:
    found = shutil.which("docker")
    if found:
        return found
    for candidate in WINDOWS_DOCKER_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return None


def build_run_args(docker: str, name: str) -> list[str]:
    """固定参数列表。不挂载宿主机目录，不使用特权，也不打开网络。"""
    return [
        docker,
        "run",
        "--rm",
        "--name",
        name,
        "--network",
        "none",
        "--memory",
        f"{MEMORY_MB}m",
        "--memory-swap",
        f"{MEMORY_MB}m",
        "--cpus",
        str(CPUS),
        "--pids-limit",
        str(PIDS_LIMIT),
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "1000:1000",
        "--tmpfs",
        f"/tmp:rw,exec,nosuid,nodev,size={TMPFS_SIZE}",
        "-e",
        "HOME=/tmp",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-e",
        f"JUDGE_COMPILE_TIMEOUT={COMPILE_TIMEOUT_SECONDS}",
        "-e",
        f"JUDGE_RUN_TIMEOUT={RUN_TIMEOUT_SECONDS}",
        "-e",
        f"JUDGE_OUTPUT_LIMIT={OUTPUT_LIMIT_BYTES}",
        "-i",
        IMAGE,
    ]


def run_program(source: str, inputs: list[str]) -> ProgramExecution:
    docker = find_docker()
    if not docker:
        raise JudgeEnvironmentError(DOCKER_MISSING_MESSAGE)
    _ensure_engine(docker)
    if not _image_exists(docker):
        raise JudgeEnvironmentError(IMAGE_MISSING_MESSAGE)
    name = f"studymate-judge-{uuid.uuid4().hex[:12]}"
    args = build_run_args(docker, name)
    payload = _pack(source.encode("utf-8"), [item.encode("utf-8") for item in inputs])
    timeout = COMPILE_TIMEOUT_SECONDS + RUN_TIMEOUT_SECONDS * max(1, len(inputs)) + 10
    try:
        completed = subprocess.run(
            args,
            input=payload,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        subprocess.run([docker, "rm", "-f", name], capture_output=True, check=False)
        raise JudgeEnvironmentError("判题容器超时，已强制停止") from None
    except FileNotFoundError:
        raise JudgeEnvironmentError(DOCKER_MISSING_MESSAGE) from None
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace")
        if _daemon_unavailable(detail):
            raise JudgeEnvironmentError(DOCKER_NOT_RUNNING_MESSAGE)
        if "No such image" in detail or "Unable to find image" in detail:
            raise JudgeEnvironmentError(IMAGE_MISSING_MESSAGE)
        raise JudgeEnvironmentError("判题容器异常退出")
    return _parse(completed.stdout)


def _ensure_engine(docker: str) -> None:
    try:
        completed = subprocess.run([docker, "info"], capture_output=True, timeout=12, check=False)
    except subprocess.TimeoutExpired as exc:
        raise JudgeEnvironmentError(DOCKER_NOT_RUNNING_MESSAGE) from exc
    if completed.returncode == 0:
        return
    detail = completed.stderr.decode("utf-8", "replace") + completed.stdout.decode("utf-8", "replace")
    if _daemon_unavailable(detail):
        raise JudgeEnvironmentError(DOCKER_NOT_RUNNING_MESSAGE)
    raise JudgeEnvironmentError(DOCKER_MISSING_MESSAGE)


def _daemon_unavailable(detail: str) -> bool:
    return any(hint in detail for hint in DAEMON_HINTS)


def _image_exists(docker: str) -> bool:
    completed = subprocess.run([docker, "image", "inspect", IMAGE], capture_output=True, check=False)
    if completed.returncode == 0:
        return True
    detail = completed.stderr.decode("utf-8", "replace")
    if _daemon_unavailable(detail):
        raise JudgeEnvironmentError(DOCKER_NOT_RUNNING_MESSAGE)
    return False


def _pack(source: bytes, inputs: list[bytes]) -> bytes:
    body = bytearray(MAGIC)
    body += struct.pack(">I", len(source))
    body += source
    body += struct.pack(">I", len(inputs))
    for item in inputs:
        body += struct.pack(">I", len(item))
        body += item
    return bytes(body)


def _parse(raw: bytes) -> ProgramExecution:
    if len(raw) < 5 or raw[:4] != MAGIC:
        raise JudgeEnvironmentError("判题容器没有返回有效结果")
    phase = raw[4]
    offset = 5
    if phase == 1:
        output, offset = _take_blob(raw, offset)
        return ProgramExecution(False, output.decode("utf-8", "replace"), [])
    if phase != 2:
        raise JudgeEnvironmentError("判题容器返回了未知结果")
    count = struct.unpack(">I", raw[offset : offset + 4])[0]
    offset += 4
    cases: list[CaseExecution] = []
    labels = {0: "ok", 1: "time_limit_exceeded", 2: "runtime_error", 3: "runtime_error"}
    for _ in range(count):
        status_code = raw[offset]
        offset += 1
        exit_code, elapsed, memory_kb, output_len = struct.unpack(">iIII", raw[offset : offset + 16])
        offset += 16
        output = raw[offset : offset + output_len]
        offset += output_len
        error, offset = _take_blob(raw, offset)
        cases.append(
            CaseExecution(
                status=labels.get(status_code, "runtime_error"),
                exit_code=exit_code,
                time_ms=elapsed,
                memory_kb=memory_kb,
                stdout=output.decode("utf-8", "replace"),
                error=error.decode("utf-8", "replace"),
            )
        )
    return ProgramExecution(True, "", cases)


def _take_blob(raw: bytes, offset: int) -> tuple[bytes, int]:
    size = struct.unpack(">I", raw[offset : offset + 4])[0]
    start = offset + 4
    end = start + size
    return raw[start:end], end
