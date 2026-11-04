"""判题限制只在这里读取，避免散落在多个文件里。"""

import os

COMPILE_TIMEOUT_SECONDS = float(os.getenv("JUDGE_COMPILE_TIMEOUT", "15"))
RUN_TIMEOUT_SECONDS = float(os.getenv("JUDGE_RUN_TIMEOUT", "2"))
MEMORY_MB = int(os.getenv("JUDGE_MEMORY_MB", "256"))
CPUS = os.getenv("JUDGE_CPUS", "1")
PIDS_LIMIT = int(os.getenv("JUDGE_PIDS_LIMIT", "32"))
OUTPUT_LIMIT_BYTES = int(os.getenv("JUDGE_OUTPUT_LIMIT", str(1024 * 1024)))
IMAGE = os.getenv("JUDGE_IMAGE", "studymate-judge:1")
TMPFS_SIZE = os.getenv("JUDGE_TMPFS_SIZE", "64m")

DOCKER_MISSING_MESSAGE = "未检测到 Docker。请安装并启动 Docker Desktop 后再判题。系统不会在本机直接运行代码。"
IMAGE_MISSING_MESSAGE = "判题镜像不存在。请在 backend 目录执行：docker build -t studymate-judge:1 judge。系统不会在本机直接运行代码。"
