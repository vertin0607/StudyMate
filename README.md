# StudyMate

StudyMate 是一个本地可运行的 AI 个性化学习监督系统。它根据学习目标生成每日计划，用检测和复习跟踪知识点掌握情况，并提供题库与隔离的 C++ 判题。

仓库地址：<https://github.com/vertin0607/StudyMate.git>

当前版本 **0.9.0**（第九阶段）。学习数据保存在本机 SQLite。打开页面只读数据库；生成计划、检测、复习、导师对话，以及题目/错因的 AI 分析，才会调用 DeepSeek。用户代码只在 Docker 容器中编译运行，不会在宿主机直接执行。

本仓库不包含 `.env` 和个人数据库。克隆后需要自行配置密钥，并在首次启动时生成本地空库。

## 功能概览

- 注册 / 登录，会话 Cookie + CSRF；各账号数据隔离
- 学习目标、每日计划、任务完成
- 知识检测（5 题）、掌握度与复习间隔
- 复习检测、题目讲解、知识点讲解与追问
- AI 导师（基于目标与掌握情况，不直接改掌握度）
- 题库导入、草稿、提交记录、错题本、练习状态
- Docker 隔离 C++ 判题（`accepted` / `wrong_answer` / `compile_error` / 超时 / 运行错误）
- 学习档案、主题设置

尚未完成：AI 学习课堂、学习汇报正文、题目间隔复习（8.4）。

## 技术栈

| 部分 | 技术 |
| --- | --- |
| 前端 | React 19、TypeScript、Vite 8、Tailwind CSS 4、CodeMirror 6 |
| 后端 | FastAPI、SQLModel、SQLite、Uvicorn |
| 模型 | DeepSeek（仅后端，`deepseek-chat`） |
| 判题 | Docker 镜像 `studymate-judge:1`，无网络、只读根文件系统、非 root |

## 环境要求

- Windows 10 或更高版本（启动脚本为 PowerShell）
- Python 3.10 或更高版本
- Node.js 20 或更高版本，以及 npm
- Git
- 使用 AI 功能时需要 DeepSeek API 密钥
- 使用代码判题时需要 [Docker Desktop](https://www.docker.com/products/docker-desktop/)，并完成本文「判题环境」一节

开发机上验证过的版本示例：Python 3.10.11、Node.js 24、Git 2.56。

## 安装

在仓库根目录打开 PowerShell。下文用 `<仓库目录>` 表示克隆位置。

### 1. 克隆

```powershell
git clone https://github.com/vertin0607/StudyMate.git
cd StudyMate
```

### 2. 后端

```powershell
cd backend
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

若本机没有 `py -3.10`，改用已安装的 Python 3.10+ 创建虚拟环境。不要把真实密钥写进代码或提交 `.env`。

用编辑器打开 `backend/.env`，填写：

```text
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_MODEL=deepseek-chat
```

其余项可保持示例默认值。`DATABASE_PATH=data/studymate.db` 表示正式数据在 `backend/data/studymate.db`。

### 3. 前端

```powershell
cd ..\frontend
npm install
```

开发时前端通过 Vite 把 `/api` 转到 `http://127.0.0.1:8000`，一般不必改 `frontend/.env`。

## 启动

首次克隆后，数据库文件还不存在。请用下面的 Uvicorn 命令启动后端：进程会自动创建 `backend/data/` 和空库。不要运行 `python -m app.scripts.initialize_owner`，也不要手动删除已有 `studymate.db`。

需要两个终端，并保持运行。

后端（在 `backend` 目录）：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000
```

前端（在 `frontend` 目录）：

```powershell
npm run dev
```

本机打开 <http://127.0.0.1:5173/>。局域网其他设备可使用前端窗口打印的 Network 地址（例如 `http://<局域网IP>:5173/`）。浏览器只访问前端；不要对局域网开放 8000 端口。

根目录的 `start_studymate.ps1` 适合**已经存在** `backend/.venv`、`backend/.env`、`backend/data/studymate.db` 和 `frontend/node_modules` 的机器。它不会建库、不会初始化账号。若 8000 或 5173 已被占用，脚本会退出。

## 确认运行成功

1. <http://127.0.0.1:8000/api/health> 返回 `"status": "ok"`、`"version": "0.9.0"`、`"phase": 9`。
2. <http://127.0.0.1:8000/docs> 可打开 FastAPI 文档。
3. 打开 <http://127.0.0.1:5173/>，注册并登录。刷新后学习数据仍在。打开首页、目标、计划、复习、题库**不会**调用 DeepSeek。
4. 「生成今日计划」「开始知识检测」「开始复习」、导师发消息、「AI 分析题目 / 错误」才会调用模型（需已配置密钥）。
5. 后端测试（不请求真实 DeepSeek，不改正式库）：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

## 判题环境（可选，做 C++ 题时需要）

1. 安装并启动 Docker Desktop，等到引擎就绪。
2. 构建镜像（在 `backend` 目录，只需做一次）：

```powershell
docker build -t studymate-judge:1 judge
```

每次提交判题会启动一次性容器：`--network none`、只读根文件系统、丢弃权限、非 root、内存 256MB、1 核、最多 32 个进程。没有 Docker 或镜像时，结果为 `system_error` 并给出提示，**不会**退回本机 `g++`。

## 故障排查

### 页面提示后端健康检查失败

- 确认后端窗口仍在运行。
- 浏览器访问 <http://127.0.0.1:8000/api/health>。
- 前端请用 <http://127.0.0.1:5173/>（或本机局域网 IP 的 5173）。Vite 只把当前页面的 `/api` 转到后端。

### 端口被占用

```powershell
netstat -ano | findstr :8000
netstat -ano | findstr :5173
```

关掉旧的 StudyMate 窗口后再启动。前端固定 5173，被占用时 Vite 会退出。

### PowerShell 禁止运行脚本

不必激活虚拟环境。使用 `.\.venv\Scripts\python.exe -m uvicorn ...` 即可。

### 依赖安装失败

后端可换官方源：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.org/simple
```

前端在 `frontend` 目录重新执行 `npm install`。

### 修改 `.env` 后未生效

带 `--reload` 时保存 `.env` 不一定重载。在后端窗口按 `Ctrl+C` 后重新启动。

### 判题提示 Docker 未启动或镜像不存在

打开 Docker Desktop，确认 `docker images` 中有 `studymate-judge:1`。未就绪时不要在宿主机安装 g++ 来“代替”判题。

## 项目结构

```text
StudyMate/
├── backend/                 FastAPI、SQLite、DeepSeek、判题调度
│   ├── app/                 路由、服务、模型、提示词
│   ├── judge/               判题镜像 Dockerfile 与容器内 runner
│   ├── data/                本地数据库（不提交）
│   └── tests/               pytest，使用假模型响应
├── frontend/                React + Vite 界面
├── docs/                    课程项目报告（Markdown 与 PDF）
├── start_studymate.ps1      已安装环境下同时打开前后端窗口
├── README.md                环境、安装、运行
└── DEVELOPMENT.md           分阶段实现说明
```

## 课程作业提交材料

评委按本 README 在自己的电脑上安装运行即可，不需要作者电脑保持开机。

建议一并提交：

- 本 GitHub 仓库地址
- 不超过 6 分钟的演示视频（详细版可放 B 站并附链接）
- `docs/` 中的项目报告 PDF（提交前把文件名改为 `小组序号-小组长姓名-StudyMate.pdf`，并填好成员分工）
