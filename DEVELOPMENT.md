# StudyMate 开发说明

这份文档说明当前代码怎么组织，以及后续阶段从哪里继续。

## 当前进度

第一阶段已经完成并通过本地验证：

- 后端可以启动，`GET /api/health` 返回状态和服务器时间。
- 前端可以启动，首页读取这条健康检查。
- 规格中的主要路由已经注册，其余页面明确标成尚未实现。
- 后端测试覆盖健康检查和未实现接口的 404。

同一天的学习计划、课程生成和数据库保存从后面的阶段开始。现在刷新页面只会再次请求健康检查，不会创建学习数据。

## 为什么第一阶段停在这里

StudyMate 的核心是长期学习记忆和动态调整计划。这些都依赖数据库和模型调用。先把前后端跑通，后面每加一块都可以单独测试，避免一次性生成后难以定位错误。

服务器时间放在健康检查里，是为了先确定「今天是哪一天」由后端时钟提供。第四阶段生成每日计划时继续使用这个原则，不让模型自己填写日期。

## 已安装的依赖

后端，安装在 `backend/.venv`：

- fastapi 0.162.0
- uvicorn 0.54.0
- python-dotenv 1.2.4
- pydantic 2.14.2
- httpx 0.28.1
- pytest 9.2.0

前端：

- react 19、react-dom
- react-router-dom 7
- axios
- recharts（已安装，第一阶段没有图表，避免用虚构数据画学习趋势）
- tailwindcss 4
- vite 8、typescript 7

SQLModel 和 OpenAI SDK 到对应阶段再加入 `requirements.txt` 并安装。现在不调用它们。

## 目录和文件

### 后端

| 文件 | 作用 |
| --- | --- |
| `backend/app/main.py` | 创建 FastAPI 应用，允许本地前端跨域访问，挂载 `/api` |
| `backend/app/config.py` | 从 `backend/.env` 读取地址、端口和跨域来源 |
| `backend/app/routers/health.py` | 健康检查 |
| `backend/tests/test_health.py` | 检查健康检查成功，以及尚未实现的目标接口返回 404 |
| `backend/requirements.txt` | 当前阶段的 Python 依赖 |
| `backend/.env.example` | 配置模板。可以提交 |
| `backend/.env` | 本机配置。已忽略，不要提交 |
| `backend/app/models/` | 空包。第二阶段放数据表 |
| `backend/app/schemas/` | 空包。后续放请求和响应模型 |
| `backend/app/services/` | 空包。后续放规划、教学、出题和诊断 |
| `backend/app/prompts/` | 空目录。后续放独立提示词，不把所有任务写成一段超长提示词 |

### 前端

| 文件 | 作用 |
| --- | --- |
| `frontend/src/main.tsx` | 挂载 React，并启用路由 |
| `frontend/src/App.tsx` | 注册首页和后续页面的路径 |
| `frontend/src/layouts/AppLayout.tsx` | 左侧导航、服务器时间和内容区 |
| `frontend/src/pages/DashboardPage.tsx` | 第一阶段首页 |
| `frontend/src/pages/PlaceholderPage.tsx` | 尚未实现的页面 |
| `frontend/src/components/HealthCard.tsx` | 展示后端是否在线 |
| `frontend/src/hooks/useHealth.ts` | 请求健康检查，并提供重新检测 |
| `frontend/src/services/api.ts` | Axios 实例。请求只发往自己的后端 |
| `frontend/src/types/health.ts` | 健康检查响应的类型 |
| `frontend/src/utils/format.ts` | 格式化服务器时间 |
| `frontend/src/utils/navigation.ts` | 侧边栏入口 |
| `frontend/vite.config.ts` | Tailwind，以及把 `/api` 代理到 8000 端口 |
| `frontend/src/index.css` | 全局颜色、字体和页面背景 |

首页和顶栏共用同一次健康检查。点击「重新检测」时，顶栏时间会一起更新。

## 日常命令

后端测试：

```powershell
cd D:\StudyMate\backend
.\.venv\Scripts\python.exe -m pytest
```

前端类型检查、打包和静态检查：

```powershell
cd D:\StudyMate\frontend
npm run build
npm run lint
```

启动方式见根目录 `README.md`。

## 接口约定

第一阶段只有：

```text
GET /api/health
```

成功时返回：

```json
{
  "status": "ok",
  "service": "StudyMate",
  "version": "0.1.0",
  "phase": 1,
  "server_time": "2026-11-03T13:20:00+08:00"
}
```

`/api/goals` 等业务接口现在会返回 404。第二阶段实现时再添加，不在健康检查里伪造这些数据。

## 配置

`backend/.env`：

```text
APP_HOST=127.0.0.1
APP_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=
```

DeepSeek 三项留给第三阶段。密钥为空时，第一阶段仍然可以启动。

前端默认不设置 `VITE_API_BASE_URL`。浏览器访问 `http://127.0.0.1:5173/api/health` 时，由 Vite 转发到后端。

## 出错时先看哪里

1. 复制终端里的完整报错。
2. 区分是安装、启动、测试，还是浏览器请求。
3. 后端导入错误：看报错里的文件路径，优先检查 `backend/app/main.py` 和 `backend/app/config.py`。
4. 前端类型错误：在 `frontend` 目录运行 `npm run build`，按 TypeScript 指出的文件修改。
5. 页面能开但显示离线：后端窗口和 http://127.0.0.1:8000/api/health 。
6. 只改出错的那一处，保留已经通过的健康检查。

## 后续阶段

每个阶段完成并测试后，再进入下一阶段。建议当时再做一次 Git 提交。

| 阶段 | 内容 | 建议提交说明 |
| --- | --- | --- |
| 第一阶段 | 项目骨架和健康检查 | `feat: initialize project structure` |
| 第二阶段 | SQLite 和学习目标管理 | `feat: add learning goal management` |
| 第三阶段 | DeepSeek API | `feat: integrate DeepSeek API` |
| 第四阶段 | 每日学习计划 | `feat: implement daily study planner` |
| 第五阶段 | 课程、测试和诊断 | `feat: add quiz and evaluation system` |
| 第六阶段 | 学习档案和计划调整 | 按实际改动编写 |
| 第七阶段 | 界面完善和本地运行说明 | 按实际改动编写 |

第二阶段开始时新增 `backend/app/database.py`，用 SQLModel 把 SQLite 文件放在 `backend/data/`，不要放进临时目录。删除数据库或清空学习记录之前，先确认。

## 安全约定

- API Key 只放在 `backend/.env`。
- `.env` 已写进根目录 `.gitignore`。
- 前端不直接请求 DeepSeek。
- 模型输出不能当作 Python 或 SQL 执行。
- 第一阶段没有用户个人信息。
