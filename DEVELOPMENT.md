# StudyMate 开发说明

这份文档说明当前代码怎么组织，以及后续阶段从哪里继续。

## 当前进度

第九阶段已完成并通过本地测试。健康检查是第 9 阶段。提交后的 C++ 会在独立 Docker 容器里编译和运行，再用保存的测试数据比对输出。DeepSeek 只在点击「AI 分析错误」后解释已有的判题结果，不决定对错。8.4 题目间隔复习没有做。

- 判题镜像是 `studymate-judge:1`。在 `backend` 目录执行 `docker build -t studymate-judge:1 judge`。每次判题使用新容器，`--network none`、只读根文件系统、丢弃全部权限、非 root、内存 256MB、1 核、最多 32 个进程。临时目录在容器内，可执行，因为编译出的程序要在那里运行。
- 没有检测到 Docker，或镜像还没构建时，结果是 `system_error`，并提示安装或启动 Docker Desktop、或先构建镜像。不会退回本机 `g++`。
- 判题结果在新表 `problem_judge_results` 和 `problem_judge_case_results`。已有的 `problem_submissions.status` 本来就是字符串，直接写入新状态，没有改旧列。
- `accepted`、`wrong_answer`、`compile_error`、`time_limit_exceeded`、`runtime_error` 会更新练习状态。`system_error` 不改练习状态。编译失败、超时和运行异常不会被记成答案错误。
- 这台电脑当前没有安装 Docker Desktop，所以容器内编译、超时、断网和清理没有实际跑过。测试用假的执行结果覆盖了判题流程。

第八阶段 8.3 已完成并通过本地测试。题目可以记录练习状态、多次练习和主动标记的错题。题目复习还没有做。

- 练习状态在 `problem_learning_status`。用户只能改成待练习、练习中或用户自评完成。`accepted` 和 `wrong_answer` 留给判题，本阶段不能手动写入。已有判题结果时，手动修改会被拒绝。
- 每次练习写入 `problem_practice_records`。结束练习只记录过程，不表示代码正确，也不改提交状态和掌握度。
- 错题只来自用户主动标记，写在 `problem_wrong_records`。未判题的提交不会自动进入错题。
- 这些操作不调用 DeepSeek，不运行代码，也不写入 `review_schedules` 或 `review_records`。

第八阶段 8.2 已完成并通过本地测试。题目详情页可以编写 C++，自动保存草稿，并查看只读的提交记录。

- 编辑器使用 CodeMirror 6。没有已保存草稿时显示默认模板，模板不会提前写入数据库。
- 停止输入约 800 毫秒后保存草稿。保存排队执行，进行中的旧请求结束后只提交最新代码，不会把编辑器改回旧内容。
- 提交只新增 `unjudged` 记录。不清空编辑器，不修改草稿，也不表示题目通过。
- 保存草稿、提交代码和查看历史都不调用 DeepSeek，也不运行代码。

第八阶段 8.1 已完成并通过本地测试。代码编辑器和提交历史已经在 8.2 接入。

- 每道题可以保存一份 C++ 代码草稿。没有草稿时返回空代码，不会预先写入默认模板。
- 每次提交都新增一条记录，状态固定为 `unjudged`。草稿修改不会覆盖已提交代码。
- 这些接口不调用 DeepSeek，也不运行代码。
- 删除题目时会删除该题的草稿和提交记录。

题目复习和知识点复习保持两套数据，8.1 还没有建题目复习表：

- 已有的 `review_schedules`、`review_records` 只服务学习目标下的知识点。做题、保存草稿和提交代码都不写这两张表，也不改掌握度。
- 8.4 会新增 `problem_review_schedules` 和 `problem_review_records`。一道题对应一份题目复习计划，结果只记录是否独立完成、是否看了提示或题解。它不生成知识点检测，也不提高掌握度。
- 8.3 的学习状态、8.5 的错题和练习记录也会用新表。`problems` 已有数据不能靠给旧表加列来迁移。

第七阶段已经完成并通过本地测试：

- 健康检查标明当前为第 7 阶段。
- 可以手动导入题目、样例和多组测试数据。测试数据按原文保存。
- 只有点击「AI 分析题目」才调用 DeepSeek。分析失败不会删除原题。
- 题库分类使用独立的 `problem_topics`，不写入学习目标的掌握度。
- 手动改过的分类在再次分析时会保留。
- 已通过和待复习数量当前固定为 0，等做题记录接入后再计算。

第六阶段 6.1 已经完成并通过本地测试：

- 健康检查标明当前为第 6 阶段。
- 可以创建、查看和删除教学会话。刷新后对话仍在。
- 只有发送消息才调用 DeepSeek。读取会话和历史记录不调用模型。
- 回复前会读取学习目标、知识点、掌握度、最近成绩和错题原因。
- 模型没有返回合格 JSON 时，不保存这轮用户消息和回复。
- 教学对话不修改掌握度。

第五阶段已经完成并通过本地测试：

- 健康检查标明当前为第 5 阶段。
- 知识检测提交后，根据成绩写入复习计划和复习记录，并计算下一次复习日期。
- 首页和复习列表只读取数据库。重复打开不会新建重复复习任务，也不会调用 DeepSeek。
- 点击「开始复习」才生成针对性题目。同一份未提交的复习卷会被复用。
- 成绩低于 60 分时，下次间隔缩短为 1 天。连续通过后按 3、7、14、30 天延长，最长 90 天，不会永久标记为掌握。
- 暂停、完成或删除的学习目标不再出现在今日复习队列。删除目标时会清理复习计划和复习记录。
- 自动化测试使用假的模型响应，不请求 DeepSeek，也不改正式数据库。

第四阶段已经完成并通过本地测试：

- 健康检查在第四阶段标明为第 4 阶段，当前代码已改为第 6 阶段。
- 完成学习任务后可以生成 5 道知识检测题。正确答案在提交前不返回给页面。
- 单选、判断和多选由后端按标准答案评分。多选必须选项完全一致。简答题由 DeepSeek 评分，评分失败时试卷仍保持未完成。
- 一次高分不会直接把知识点记成熟练掌握。掌握度变化写在 `knowledge_mastery_events`。
- 重新生成学习计划时会读到掌握度和最近检测。
- 自动化测试使用假的模型响应，不请求 DeepSeek，也不改正式数据库。

第三阶段已经完成并通过本地验证：

- 健康检查仍然可用，并标明当前为第 3 阶段。
- SQLite 文件位于 `backend/data/studymate.db`，路径由 `DATABASE_PATH` 决定。已有学习目标会保留。
- 可以创建、查询、编辑、暂停、恢复、完成和删除学习目标。
- 首页的目标数量来自 `GET /api/goals`。今日计划状态来自 `GET /api/plans/dashboard`，这两个读取接口都不调用模型。
- 同一目标同一天只有一份当前计划。重新生成会把旧计划标为历史，并写入修改原因。
- 完成任务只更新任务状态。没有测试成绩时，知识点掌握程度保持未评估。
- 测试使用 `backend/tests/_test_studymate.db`，模型调用被替换成假函数，不会改写正式学习记录，也不会请求 DeepSeek。

## 为什么第一阶段停在这里

StudyMate 的核心是长期学习记忆和动态调整计划。这些都依赖数据库和模型调用。先把前后端跑通，后面每加一块都可以单独测试，避免一次性生成后难以定位错误。

服务器时间放在健康检查里，是为了先确定「今天是哪一天」由后端时钟提供。每日计划的日期也由服务器决定，不让模型自己填写日期。

## 已安装的依赖

后端，安装在 `backend/.venv`：

- fastapi 0.162.0
- uvicorn 0.54.0
- python-dotenv 1.2.4
- pydantic 2.14.2
- httpx 0.28.1
- pytest 9.2.0
- sqlmodel 0.0.48
- sqlalchemy 2.0.55
- openai 3.42.1

前端：

- react 19、react-dom
- react-router-dom 7
- axios
- recharts（已安装，第一阶段没有图表，避免用虚构数据画学习趋势）
- tailwindcss 4
- vite 8、typescript 7
- codemirror 6、`@codemirror/lang-cpp`。题目编辑使用这套，不使用 Monaco

OpenAI SDK 只在后端调用 DeepSeek。测试和页面刷新都不会发起真实请求。

## 目录和文件

### 后端

| 文件 | 作用 |
| --- | --- |
| `backend/app/main.py` | 创建 FastAPI 应用，允许本地前端跨域访问，挂载 `/api` |
| `backend/app/config.py` | 从 `backend/.env` 读取地址、端口、跨域来源、数据库路径和 DeepSeek 配置 |
| `backend/app/database.py` | 创建 SQLite 连接、数据表、当前计划唯一约束和本地用户 |
| `backend/app/models/user.py` | 用户表 |
| `backend/app/models/goal.py` | 学习目标表 |
| `backend/app/models/knowledge.py` | 知识点表。掌握程度和任务完成分开记录 |
| `backend/app/models/plan.py` | 学习计划、每日任务和修改历史 |
| `backend/app/schemas/goal.py` | 学习目标的请求和响应校验 |
| `backend/app/schemas/plan.py` | 生成计划、调整计划和任务状态的请求校验 |
| `backend/app/services/goal_service.py` | 学习目标的增删改查 |
| `backend/app/services/planning_service.py` | 读取、保存和调整每日计划 |
| `backend/app/services/ai/deepseek_client.py` | 调用 DeepSeek |
| `backend/app/services/ai/prompt_builder.py` | 根据目标和历史记录构造提示词 |
| `backend/app/services/ai/response_parser.py` | 校验模型返回的 JSON，通过后才允许入库 |
| `backend/app/prompts/planner.txt` | 每日计划提示词 |
| `backend/app/routers/goals.py` | 学习目标接口 |
| `backend/app/routers/plans.py` | 学习计划接口 |
| `backend/app/routers/tasks.py` | 更新任务状态 |
| `backend/app/routers/ai.py` | 连通性检查。响应不包含密钥 |
| `backend/app/routers/health.py` | 健康检查 |
| `backend/app/errors.py` | 把非法请求整理成中文说明 |
| `backend/tests/test_health.py` | 检查健康检查，以及尚未实现的课程接口返回 404 |
| `backend/tests/test_goals.py` | 检查学习目标接口和数据是否写入 SQLite |
| `backend/tests/test_plans.py` | 用假模型检查计划读取、生成、调整和任务状态 |
| `backend/tests/test_plan_parser.py` | 检查计划 JSON 校验 |
| `backend/tests/conftest.py` | 让测试使用单独的数据库文件 |
| `backend/requirements.txt` | 当前阶段的 Python 依赖 |
| `backend/.env.example` | 配置模板。可以提交 |
| `backend/.env` | 本机配置。已忽略，不要提交 |
| `backend/data/` | 正式数据库目录。`*.db` 不提交 |
| `backend/app/models/review.py` | 知识点复习计划和复习记录。题目复习不使用这两张表 |
| `backend/app/models/submission.py` | 代码草稿和提交记录。状态字符串会在判题后更新，代码本身不覆盖 |
| `backend/app/models/practice.py` | 练习状态、练习记录和错题。不进入掌握度或知识点复习 |
| `backend/app/services/practice_service.py` | 练习和错题的保存与统计，不调用模型，不运行代码 |
| `backend/tests/test_practice.py` | 练习状态、错题、统计和隔离 |
| `backend/app/services/submission_service.py` | 保存草稿和提交记录，不调用模型，不运行代码 |
| `backend/app/routers/submissions.py` | 按提交编号查看和删除自己的代码 |
| `backend/tests/test_submissions.py` | 草稿、多次提交、用户隔离和删除题目后的清理 |
| `backend/app/services/review_scheduler.py` | 间隔和遗忘风险计算，不调用模型 |
| `backend/app/services/review_service.py` | 复习队列、推迟、开始复习和长期档案 |
| `backend/app/prompts/review.txt` | 复习出题提示词 |
| `backend/app/routers/reviews.py` | 复习队列接口 |
| `backend/tests/test_reviews.py` | 用假模型检查复习队列、间隔和隔离 |
| `backend/tests/test_review_scheduler.py` | 间隔算法的纯计算测试 |
| `backend/app/prompts/` | 每日计划和复习提示词 |

### 前端

| 文件 | 作用 |
| --- | --- |
| `frontend/src/main.tsx` | 挂载 React，并启用路由 |
| `frontend/src/App.tsx` | 注册首页和后续页面的路径 |
| `frontend/src/layouts/AppLayout.tsx` | 左侧导航、服务器时间和内容区 |
| `frontend/src/pages/DashboardPage.tsx` | 首页，展示后端状态、学习目标、今日计划和今日复习 |
| `frontend/src/pages/ReviewsPage.tsx` | 今日、逾期和即将到期的复习 |
| `frontend/src/pages/ReviewDetailPage.tsx` | 单个知识点的长期学习档案 |
| `frontend/src/pages/ProgressPage.tsx` | 掌握度、趋势、遗忘风险和复习统计 |
| `frontend/src/services/reviews.ts` | 调用复习和趋势接口。开始复习使用更长的超时 |
| `frontend/src/pages/PlansPage.tsx` | 今日计划、任务状态、重新生成和历史版本 |
| `frontend/src/pages/GoalsPage.tsx` | 学习目标列表、新建、编辑、暂停、恢复和删除 |
| `frontend/src/pages/GoalDetailPage.tsx` | 单个学习目标 |
| `frontend/src/services/goals.ts` | 调用学习目标接口 |
| `frontend/src/services/plans.ts` | 调用学习计划接口。生成和调整使用更长的超时 |
| `frontend/src/hooks/usePlans.ts` | 读取今日计划和首页计划状态 |
| `frontend/src/hooks/useGoals.ts` | 读取目标列表或单个目标 |
| `frontend/src/types/goal.ts` | 学习目标的 TypeScript 类型 |
| `frontend/src/components/CppEditor.tsx` | CodeMirror 6 的 C++ 编辑器，含行号、高亮、缩进和补全 |
| `frontend/src/components/ProblemWorkspace.tsx` | 草稿自动保存、提交和只读提交历史 |
| `frontend/src/services/submissions.ts` | 草稿和提交记录接口 |
| `frontend/src/utils/draftSave.ts` | 默认模板选择，以及按顺序保存草稿 |
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

当前提供：

```text
GET    /api/health
GET    /api/goals
POST   /api/goals
GET    /api/goals/{goal_id}
PUT    /api/goals/{goal_id}
PATCH  /api/goals/{goal_id}/status
DELETE /api/goals/{goal_id}
POST   /api/ai/test-connection
GET    /api/plans/dashboard
GET    /api/plans/today?goal_id={id}
POST   /api/plans/generate
GET    /api/plans/{plan_id}
GET    /api/plans/{plan_id}/history
POST   /api/plans/{plan_id}/regenerate
PATCH  /api/tasks/{task_id}/status
POST   /api/quizzes/generate
GET    /api/quizzes/history?goal_id={id}
GET    /api/quizzes/{quiz_id}
GET    /api/quizzes/{quiz_id}/result
POST   /api/quizzes/{quiz_id}/submit
GET    /api/knowledge?goal_id={id}
GET    /api/knowledge/{knowledge_id}
GET    /api/knowledge/{knowledge_id}/history
GET    /api/learning/analytics
GET    /api/learning/trends
GET    /api/learning/forgetting-risk
GET    /api/learning/review-statistics
GET    /api/reviews/today
GET    /api/reviews/upcoming
GET    /api/reviews/overdue
GET    /api/reviews/history
POST   /api/reviews/generate
GET    /api/reviews/{schedule_id}
PATCH  /api/reviews/{schedule_id}/postpone
POST   /api/reviews/{schedule_id}/start
POST   /api/tutor/sessions
GET    /api/tutor/sessions
GET    /api/tutor/sessions/{session_id}
POST   /api/tutor/sessions/{session_id}/messages
DELETE /api/tutor/sessions/{session_id}
```

健康检查成功时返回 `phase: 7`。旧的课程讲解占位路径 `/api/lessons` 仍然返回 404。

题库接口：

```text
GET    /api/problems/statistics
GET    /api/problems/topics
GET    /api/problems/knowledge/{topic_id}
POST   /api/problems/import
GET    /api/problems
POST   /api/problems
GET    /api/problems/{problem_id}
PUT    /api/problems/{problem_id}
DELETE /api/problems/{problem_id}
POST   /api/problems/{problem_id}/analyze
PUT    /api/problems/{problem_id}/classification
POST   /api/problems/{problem_id}/topics/confirm
GET    /api/problems/{problem_id}/test-cases
POST   /api/problems/{problem_id}/test-cases
PUT    /api/problems/{problem_id}/test-cases/{case_id}
DELETE /api/problems/{problem_id}/test-cases/{case_id}
GET    /api/problems/{problem_id}/notes
POST   /api/problems/{problem_id}/notes
GET    /api/problems/{problem_id}/draft
PUT    /api/problems/{problem_id}/draft
POST   /api/problems/{problem_id}/submissions
GET    /api/problems/{problem_id}/submissions
GET    /api/submissions/{submission_id}
DELETE /api/submissions/{submission_id}
GET    /api/problems/{problem_id}/learning-status
PATCH  /api/problems/{problem_id}/learning-status
POST   /api/problems/{problem_id}/practice/start
POST   /api/problems/{problem_id}/practice/{record_id}/complete
GET    /api/problems/{problem_id}/practice-history
GET    /api/practice/history
GET    /api/problems/wrong
POST   /api/problems/{problem_id}/wrong
PUT    /api/problems/{problem_id}/wrong
DELETE /api/problems/{problem_id}/wrong
GET    /api/problems/practice-statistics
GET    /api/problems/practice-trends
```

练习状态、错题和统计都不调用 DeepSeek。用户自评完成不会变成系统判题通过。原有题库统计里的 `passed` 仍固定为 0。

保存草稿、提交代码和查看提交记录都不调用 DeepSeek。提交成功只表示代码已保存，状态是 `unjudged`，不是题目通过。

`GET /api/plans/today` 默认不生成计划。打开首页、复习列表和检测页也不会出题。`POST /api/reviews/generate` 只根据已有记录整理队列，不调用模型。生成计划、生成试卷、简答题评分和 `POST /api/reviews/{id}/start` 才会调用 DeepSeek。复习答卷提交仍使用 `POST /api/quizzes/{quiz_id}/submit`。

## 配置

`backend/.env`：

```text
APP_HOST=127.0.0.1
APP_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
DATABASE_PATH=data/studymate.db
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TIMEOUT=45
```

`DATABASE_PATH` 相对 `backend` 目录。密钥只写在本机 `.env`，模板里保持空白。修改 `.env` 后需要重启后端。

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
| 第三阶段 | DeepSeek 和每日学习计划 | `feat: integrate DeepSeek API` |
| 第四阶段 | 知识检测和掌握度 | `feat: add quiz and mastery tracking` |
| 第五阶段 | 长期记忆和间隔复习 | `feat: add spaced review` |
| 第六阶段 6.1 | AI 个性化教学 | `feat: add tutor conversations` |
| 第六阶段后续 | 学习汇报 | 按实际改动编写 |

正式数据库在 `backend/data/studymate.db`。删除数据库或清空学习记录之前，先确认。

## 安全约定

- API Key 只放在 `backend/.env`。
- `.env` 已写进根目录 `.gitignore`。
- 前端不直接请求 DeepSeek。
- 模型输出不能当作 Python 或 SQL 执行。
- 当前保存本地用户名 `local`、学习目标、知识点和计划。不保存密钥。
- 日志只记录模型名称，不记录完整密钥。
