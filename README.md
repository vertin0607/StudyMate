# StudyMate

StudyMate 是一个 AI 个性化学习监督系统。它会记住学习目标、每天的任务、课程、测试和学习汇报，并据此调整后续计划。

当前仓库完成的是**第一阶段：环境与项目骨架**。现在可以在本机启动前端和后端，并确认两边已经连通。学习目标、数据库和 DeepSeek 还没有接入。

## 环境

在这台电脑上检查到的版本：

| 工具 | 结果 |
| --- | --- |
| Python | 3.10.11（虚拟环境使用这一版） |
| Node.js | 24.20.0 |
| npm | 11.19.0 |
| Git | 终端里找不到 `git` 命令 |

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

`.env` 里的 `DEEPSEEK_API_KEY` 在第一阶段保持空白。不要把密钥写进 Python 或前端代码。

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
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

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
   页面会进入首页。后端卡片显示「后端运行正常」，顶部显示服务器时间。
4. 点击侧边栏「学习目标」。  
   应打开占位页，并说明该功能属于第二阶段。
5. 在后端目录运行测试：

```powershell
cd D:\StudyMate\backend
.\.venv\Scripts\python.exe -m pytest
```

两条测试都应通过。

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
├── backend/          FastAPI。第一阶段只有健康检查
├── frontend/         React + Vite。第一阶段是页面骨架
├── README.md         安装、启动和排查
└── DEVELOPMENT.md    阶段划分和代码说明
```

更细的文件说明写在 `DEVELOPMENT.md`。

## 第一阶段还没有的功能

- 用户、学习目标和学习记录数据库
- DeepSeek API
- 学习计划、课程、测试和汇报
- 登录与多用户隔离

这些会按 `DEVELOPMENT.md` 中的阶段继续实现。
