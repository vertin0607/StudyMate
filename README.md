# StudyMate

StudyMate 是一个 AI 个性化学习监督系统。它会记住学习目标、每天的任务、课程、测试和学习汇报，并据此调整后续计划。

当前仓库完成到**第九阶段：本地 C++ 判题**。学习计划、检测、复习、教学对话、题库和判题结果都保存在 SQLite。打开页面只读取数据库。生成计划、检测、复习、导师发消息，以及点击「AI 分析题目」或「AI 分析错误」，才会调用 DeepSeek。题库不会访问 OJ。用户代码只在 Docker 容器里编译运行；没有 Docker 时会提示安装 Docker Desktop，不会在本机直接运行。

## 环境

在这台电脑上检查到的版本：

| 工具 | 结果 |
| --- | --- |
| Python | 3.10.11（虚拟环境使用这一版） |
| Node.js | 24.20.0 |
| npm | 11.19.0 |
| Git | 2.56.0.windows.4 |

开发时需要：

- Windows 10 或更高版本
- Python 3.10 或更高版本
- Node.js 20 或更高版本，以及 npm

建议安装 [Git for Windows](https://git-scm.com/download/win)。装好后重新打开终端，`git --version` 能输出版本号即可。第一阶段的提交信息可以使用：

```text
feat: initialize project structure
```

本阶段先不要提交。等 Git 可用，并且你确认要保存这次骨架后，再在项目根目录创建仓库并提交。

## 安装

打开 PowerShell。下面的路径按当前项目位置编写。

### 后端

```powershell
cd D:\StudyMate\backend
C:\Users\ACER\AppData\Local\Programs\Python\Python310\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

如果 `.venv` 和 `.env` 已经存在，只需执行安装依赖那一行。

把 DeepSeek 密钥写在 `backend/.env` 的 `DEEPSEEK_API_KEY` 中，并设置 `DEEPSEEK_MODEL=deepseek-chat`。不要把密钥写进 Python 或前端代码，也不要提交 `.env`。

### 前端

```powershell
cd D:\StudyMate\frontend
npm install
```

## 启动

需要两个 PowerShell 窗口，并保持它们运行。

后端：

```powershell
cd D:\StudyMate\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000
```

`--reload-dir app` 让自动重载只监视业务代码。这样安装 Python 依赖时，不会因为虚拟环境里的文件变化把后端打崩。

前端：

```powershell
cd D:\StudyMate\frontend
npm run dev
```

## 确认运行成功

1. 打开 http://127.0.0.1:8000/api/health  
   应看到 `"status": "ok"` 和 `"service": "StudyMate"`。
2. 打开 http://127.0.0.1:8000/docs  
   应看到 FastAPI 自动生成的接口文档，其中有健康检查。
3. 打开 http://127.0.0.1:5173  
   页面会进入首页。后端卡片显示「后端运行正常」。学习目标数量、今日计划和今日复习都来自数据库，打开首页不会调用 DeepSeek。
4. 点击侧边栏「学习目标」。  
   可以新建、编辑、暂停、恢复和删除目标。刷新页面后，刚才保存的目标还在。
5. 点击侧边栏「学习计划」。  
   如果今天还没有计划，页面会停在空状态。只有点击「生成今日计划」或「按要求重新生成」才会调用 DeepSeek。完成一项任务后，可以点击「开始知识检测」。
6. 点击侧边栏「复习」。  
   页面只读取已经安排的复习。没有到期项时保持空状态。只有点击「开始复习」才会调用 DeepSeek。
7. 点击侧边栏「AI 导师」。  
   页面只读取已有目标和历史对话。点击「开始这次对话」也不会调用模型。只有发送消息才会调用 DeepSeek。
8. 点击侧边栏「我的题库」。  
   可以粘贴题面和测试数据。只有点击「AI 分析题目」才会调用 DeepSeek。
9. 在后端目录运行测试：

```powershell
cd D:\StudyMate\backend
.\.venv\Scripts\python.exe -m pytest
```

测试应全部通过。

## 故障排查

### 页面提示后端健康检查失败

- 先看后端窗口是否还在运行，有没有红色报错。
- 浏览器直接访问 http://127.0.0.1:8000/api/health 。
- 确认前端地址是 http://127.0.0.1:5173 。Vite 只把这个开发服务器上的 `/api` 转到后端。

### 提示端口已被占用

```powershell
netstat -ano | findstr :8000
netstat -ano | findstr :5173
```

关掉已经占用端口的旧窗口，再重新启动。前端固定使用 5173，端口被占用时 Vite 会直接退出。

### PowerShell 禁止运行 `.venv\Scripts\Activate.ps1`

不需要激活虚拟环境。使用上面的 `.\.venv\Scripts\python.exe -m uvicorn ...` 即可。

### `python` 不是 3.10

这台电脑上有多个 Python。创建虚拟环境时请使用：

```powershell
C:\Users\ACER\AppData\Local\Programs\Python\Python310\python.exe -m venv .venv
```

### 依赖安装很慢或失败

后端使用了清华 PyPI 镜像。如果镜像不可用，可以暂时改用官方源：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.org/simple
```

前端安装失败时，检查网络后在 `frontend` 目录重新执行 `npm install`。

### 修改 `.env` 后没有生效

后端使用了 `--reload` 时，保存 `.env` 不一定会自动重载。在后端窗口按 `Ctrl+C` 后重新执行启动命令。

## 项目结构

```text
StudyMate/
├── backend/          FastAPI、SQLite 和 DeepSeek 调用
├── frontend/         React + Vite。当前提供首页、学习目标、每日计划、检测和复习
├── README.md         安装、启动和排查
└── DEVELOPMENT.md    阶段划分和代码说明
```

更细的文件说明写在 `DEVELOPMENT.md`。

## 还没有完成的功能

- 课程讲解和学习汇报
- 登录与多用户隔离。数据表已经保留 `user_id`，当前自动使用本地用户 `local`
- 答题过程中的选项只保存在当前页面，刷新未提交的试卷会清空已选答案

这些会按 `DEVELOPMENT.md` 中的阶段继续实现。
