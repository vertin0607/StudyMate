"""容器内的固定判题程序。用户代码只作为字节写入 /tmp，不进入命令行。"""

import os
import resource
import struct
import subprocess
import sys
import threading
import time

MAGIC = b"SMJ1"
COMPILE_TIMEOUT = float(os.environ.get("JUDGE_COMPILE_TIMEOUT", "15"))
RUN_TIMEOUT = float(os.environ.get("JUDGE_RUN_TIMEOUT", "2"))
OUTPUT_LIMIT = int(os.environ.get("JUDGE_OUTPUT_LIMIT", str(1024 * 1024)))
STATUS_OK = 0
STATUS_TLE = 1
STATUS_RUNTIME = 2
STATUS_OUTPUT = 3


def read_exact(count: int) -> bytes:
    chunks = []
    remaining = count
    while remaining:
        block = sys.stdin.buffer.read(remaining)
        if not block:
            raise EOFError("判题协议不完整")
        chunks.append(block)
        remaining -= len(block)
    return b"".join(chunks)


def read_blob() -> bytes:
    size = struct.unpack(">I", read_exact(4))[0]
    if size > 2_000_000:
        raise ValueError("输入过大")
    return read_exact(size) if size else b""


def kill_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.kill()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass


def drain(stream, target: bytearray, limit: int, proc: subprocess.Popen, exceeded: dict[str, bool], key: str) -> None:
    while True:
        block = stream.read(8192)
        if not block:
            return
        if len(target) + len(block) > limit:
            room = max(0, limit - len(target))
            target.extend(block[:room])
            exceeded[key] = True
            kill_process(proc)
            return
        target.extend(block)


def compile_source(source: bytes) -> tuple[bool, str]:
    path = "/tmp/main.cpp"
    with open(path, "wb") as handle:
        handle.write(source)
    try:
        completed = subprocess.run(
            ["g++", "-std=gnu++17", "-O2", "-pipe", "-o", "/tmp/main", path],
            capture_output=True,
            timeout=COMPILE_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "编译超时"
    output = (completed.stderr or b"").decode("utf-8", "replace")
    if completed.returncode != 0:
        return False, output[-8000:]
    os.chmod("/tmp/main", 0o755)
    return True, output[-8000:]


def run_case(data: bytes) -> tuple[int, int, int, int, bytes, str]:
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    try:
        proc = subprocess.Popen(
            ["/tmp/main"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd="/tmp",
        )
    except OSError as exc:
        return STATUS_RUNTIME, -1, 0, 0, b"", f"程序无法启动：{exc.strerror or exc}"
    assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
    stdout = bytearray()
    stderr = bytearray()
    exceeded = {"out": False, "err": False}
    out_thread = threading.Thread(target=drain, args=(proc.stdout, stdout, OUTPUT_LIMIT, proc, exceeded, "out"), daemon=True)
    err_thread = threading.Thread(target=drain, args=(proc.stderr, stderr, 64 * 1024, proc, exceeded, "err"), daemon=True)
    try:
        proc.stdin.write(data)
        proc.stdin.close()
    except BrokenPipeError:
        pass
    out_thread.start()
    err_thread.start()
    started = time.monotonic()
    try:
        proc.wait(timeout=RUN_TIMEOUT)
        timed_out = False
    except subprocess.TimeoutExpired:
        kill_process(proc)
        timed_out = True
    out_thread.join(timeout=1)
    err_thread.join(timeout=1)
    elapsed = int((time.monotonic() - started) * 1000)
    after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    memory_kb = max(0, after - before)
    error = stderr.decode("utf-8", "replace")[-2000:]
    if exceeded["out"] or exceeded["err"]:
        return STATUS_OUTPUT, proc.returncode or -1, elapsed, memory_kb, bytes(stdout), "输出超过限制"
    if timed_out:
        return STATUS_TLE, proc.returncode or -1, elapsed, memory_kb, bytes(stdout), "运行超时"
    if proc.returncode != 0:
        return STATUS_RUNTIME, proc.returncode or -1, elapsed, memory_kb, bytes(stdout), error or f"退出码 {proc.returncode}"
    return STATUS_OK, 0, elapsed, memory_kb, bytes(stdout), ""


def write_blob(payload: bytes) -> None:
    sys.stdout.buffer.write(struct.pack(">I", len(payload)))
    sys.stdout.buffer.write(payload)


def main() -> None:
    header = read_exact(4)
    if header != MAGIC:
        raise SystemExit("协议头不正确")
    source = read_blob()
    case_count = struct.unpack(">I", read_exact(4))[0]
    inputs = [read_blob() for _ in range(case_count)]
    ok, compile_output = compile_source(source)
    sys.stdout.buffer.write(MAGIC)
    if not ok:
        sys.stdout.buffer.write(bytes([1]))
        write_blob(compile_output.encode("utf-8"))
        return
    sys.stdout.buffer.write(bytes([2, *struct.pack(">I", len(inputs))]))
    for data in inputs:
        status, exit_code, elapsed, memory_kb, output, error = run_case(data)
        sys.stdout.buffer.write(bytes([status]))
        sys.stdout.buffer.write(struct.pack(">iIII", exit_code, elapsed, memory_kb, len(output)))
        sys.stdout.buffer.write(output)
        write_blob(error.encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.stderr.write(str(exc))
        raise SystemExit(1) from exc
