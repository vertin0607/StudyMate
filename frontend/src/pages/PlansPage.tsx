import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useGoals } from "../hooks/useGoals.ts";
import { useTodayPlan } from "../hooks/usePlans.ts";
import {
  fetchPlan,
  fetchPlanHistory,
  generatePlan,
  regeneratePlan,
  updateTaskStatus,
} from "../services/plans.ts";
import { generateQuiz } from "../services/quizzes.ts";
import type { PlanHistory, StudyPlan, TaskStatus, TaskType } from "../types/plan.ts";
import { getErrorMessage } from "../utils/apiError.ts";
import { formatDate } from "../utils/format.ts";

const taskTypeLabels: Record<TaskType, string> = {
  learn: "学习",
  practice: "练习",
  review: "复习",
  quiz: "检测",
};

const taskStatusLabels: Record<TaskStatus, string> = {
  pending: "未开始",
  in_progress: "进行中",
  completed: "已完成",
  skipped: "已跳过",
};

export function PlansPage() {
  const { goals, loading: goalsLoading, error: goalsError } = useGoals();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedId = Number(searchParams.get("goal_id"));
  const activeGoals = goals.filter((goal) => goal.status === "active");
  const selected = activeGoals.find((goal) => goal.id === requestedId) ?? activeGoals[0] ?? null;
  const { today, loading, error, reload } = useTodayPlan(selected?.id ?? null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [history, setHistory] = useState<PlanHistory | null>(null);
  const [viewing, setViewing] = useState<StudyPlan | null>(null);
  const [busyTaskId, setBusyTaskId] = useState<number | null>(null);
  const [quizTaskId, setQuizTaskId] = useState<number | null>(null);
  const navigate = useNavigate();

  const plan = viewing ?? today?.plan ?? null;
  const isCurrent = plan?.status === "active";
  const completedCount = plan?.tasks.filter((task) => task.status === "completed").length ?? 0;
  const progress = plan && plan.tasks.length > 0 ? Math.round((completedCount / plan.tasks.length) * 100) : 0;

  function chooseGoal(goalId: number) {
    setViewing(null);
    setHistory(null);
    setSearchParams({ goal_id: String(goalId) });
  }

  async function handleGenerate() {
    if (!selected) {
      return;
    }
    setGenerating(true);
    setActionError(null);
    try {
      await generatePlan(selected.id);
      setViewing(null);
      reload();
    } catch (reason) {
      setActionError(getErrorMessage(reason, "生成计划失败"));
      reload();
    } finally {
      setGenerating(false);
    }
  }

  async function handleRegenerate() {
    if (!today?.plan) {
      return;
    }
    setGenerating(true);
    setActionError(null);
    try {
      await regeneratePlan(today.plan.id, instruction);
      setInstruction("");
      setViewing(null);
      setHistory(null);
      reload();
    } catch (reason) {
      setActionError(getErrorMessage(reason, "调整计划失败"));
    } finally {
      setGenerating(false);
    }
  }

  async function handleStatus(taskId: number, status: TaskStatus) {
    setBusyTaskId(taskId);
    setActionError(null);
    try {
      await updateTaskStatus(taskId, status);
      reload();
    } catch (reason) {
      setActionError(getErrorMessage(reason, "更新任务状态失败"));
    } finally {
      setBusyTaskId(null);
    }
  }

  async function handleQuiz(taskId: number) {
    setQuizTaskId(taskId);
    setActionError(null);
    try {
      const quiz = await generateQuiz(taskId);
      navigate(`/quiz/${quiz.id}`);
    } catch (reason) {
      setActionError(getErrorMessage(reason, "生成检测失败"));
    } finally {
      setQuizTaskId(null);
    }
  }

  async function toggleHistory() {
    if (!today?.plan) {
      return;
    }
    if (history) {
      setHistory(null);
      return;
    }
    try {
      setHistory(await fetchPlanHistory(today.plan.id));
    } catch (reason) {
      setActionError(getErrorMessage(reason, "读取历史版本失败"));
    }
  }

  async function openVersion(planId: number) {
    setActionError(null);
    try {
      const next = await fetchPlan(planId);
      setViewing(next.id === today?.plan?.id ? null : next);
    } catch (reason) {
      setActionError(getErrorMessage(reason, "读取历史计划失败"));
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <p className="text-sm font-medium text-accent">每日计划</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">今天学什么</h1>
      <p className="mt-3 text-sm leading-6 text-muted">
        {today ? `服务器日期 ${formatDate(today.plan_date)}。` : "日期由服务器决定。"}
        已有计划时，刷新页面只读取数据库。
      </p>

      {goalsLoading && <p className="mt-6 text-sm text-muted">正在读取学习目标…</p>}
      {goalsError && <p className="mt-6 text-sm text-rose-700">{goalsError}</p>}
      {!goalsLoading && !goalsError && activeGoals.length === 0 && (
        <div className="mt-6 rounded-3xl border border-dashed border-line bg-surface px-6 py-8 text-sm leading-6 text-muted">
          还没有进行中的学习目标。
          <Link to="/goals" className="ml-2 font-medium text-accent">
            去创建一个
          </Link>
        </div>
      )}

      {activeGoals.length > 1 && (
        <label className="mt-6 block text-sm font-medium text-ink">
          当前学习目标
          <select
            value={selected?.id ?? ""}
            onChange={(event) => chooseGoal(Number(event.target.value))}
            className="mt-2 w-full rounded-2xl border border-line bg-surface px-4 py-3 text-sm"
          >
            {activeGoals.map((goal) => (
              <option key={goal.id} value={goal.id}>
                {goal.title}
              </option>
            ))}
          </select>
        </label>
      )}

      {selected && activeGoals.length === 1 && (
        <p className="mt-6 text-sm text-muted">
          当前目标：<span className="font-medium text-ink">{selected.title}</span>
          <span className="mx-2">·</span>每天 {selected.daily_minutes} 分钟
        </p>
      )}

      {loading && <p className="mt-6 text-sm text-muted">正在读取今天的计划…</p>}
      {error && (
        <div className="mt-6 rounded-3xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-800">
          <p>{error}</p>
          <button type="button" onClick={reload} className="mt-4 rounded-full bg-accent px-4 py-2 text-on-accent">
            重新读取
          </button>
        </div>
      )}

      {selected && today && !today.plan && !loading && !error && (
        <div className="mt-6 rounded-3xl border border-line bg-surface p-6">
          <h2 className="text-xl font-semibold">今天还没有计划</h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            点击下面的按钮才会调用 DeepSeek。生成后会保存到数据库，再次打开不会重复请求。
          </p>
          <button
            type="button"
            onClick={() => void handleGenerate()}
            disabled={generating}
            className="mt-5 rounded-full bg-accent px-4 py-2 text-sm font-medium text-on-accent disabled:opacity-60"
          >
            {generating ? "正在生成…" : "生成今日计划"}
          </button>
        </div>
      )}

      {plan && (
        <article className="mt-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm text-muted">{isCurrent ? `第 ${plan.version} 版` : `历史版本 · 第 ${plan.version} 版`}</p>
              <h2 className="mt-1 text-2xl font-semibold tracking-tight">{plan.title}</h2>
            </div>
            <p className="text-sm font-medium text-accent">{plan.total_minutes} 分钟</p>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted">{plan.description}</p>
          <div className="mt-4">
            <div className="flex justify-between text-sm text-muted">
              <span>完成 {completedCount} / {plan.tasks.length}</span>
              <span>{progress}%</span>
            </div>
            <div className="mt-2 h-2 rounded-full bg-soft">
              <div className="h-2 rounded-full bg-accent" style={{ width: `${progress}%` }} />
            </div>
          </div>
          <p className="mt-3 text-sm text-muted">完成任务只会记录进度。没有测试成绩时，知识点仍显示为尚未评估。</p>
          {actionError && (
            <p className="mt-4 text-sm text-rose-700" role="alert">
              {actionError}
            </p>
          )}

          <ol className="mt-5 space-y-3">
            {plan.tasks.map((task, index) => (
              <li key={task.id} className="rounded-3xl border border-line bg-surface p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm text-muted">
                    {index + 1}. {taskTypeLabels[task.task_type]} · {task.estimated_minutes} 分钟
                  </p>
                  <span className="rounded-full bg-soft px-3 py-1 text-sm text-muted">
                    {taskStatusLabels[task.status]}
                  </span>
                </div>
                <h3 className="mt-2 text-lg font-semibold">{task.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted">{task.description}</p>
                <p className="mt-3 text-sm text-muted">
                  知识点：{task.knowledge_point_name ?? "未关联"}
                  <span className="mx-2">·</span>
                  {task.mastery_assessed ? `掌握 ${task.mastery_level}` : "掌握程度尚未评估"}
                </p>
                {isCurrent && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {task.status === "pending" && (
                      <TaskButton
                        label="开始"
                        disabled={busyTaskId === task.id}
                        onClick={() => void handleStatus(task.id, "in_progress")}
                      />
                    )}
                    {task.status !== "completed" && (
                      <TaskButton
                        label="完成"
                        disabled={busyTaskId === task.id}
                        onClick={() => void handleStatus(task.id, "completed")}
                      />
                    )}
                    {task.status !== "skipped" && task.status !== "completed" && (
                      <TaskButton
                        label="跳过"
                        disabled={busyTaskId === task.id}
                        onClick={() => void handleStatus(task.id, "skipped")}
                      />
                    )}
                    {task.status === "completed" ? (
                      <TaskButton
                        label={quizTaskId === task.id ? "正在出题…" : "开始知识检测"}
                        disabled={quizTaskId !== null}
                        onClick={() => void handleQuiz(task.id)}
                      />
                    ) : (
                      <span className="self-center text-sm text-muted">完成学习后可以检测</span>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ol>

          {isCurrent && today?.plan && (
            <section className="mt-6 rounded-3xl border border-line bg-surface p-5">
              <h3 className="text-lg font-semibold">调整今天的安排</h3>
              <p className="mt-2 text-sm leading-6 text-muted">
                重新生成会保留原来的版本。每次点击都会调用一次 DeepSeek。
              </p>
              <textarea
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
                maxLength={500}
                rows={3}
                placeholder="例如：今天只有 15 分钟，帮我缩短学习计划。"
                className="mt-4 w-full rounded-2xl border border-line px-4 py-3 text-sm"
              />
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void handleRegenerate()}
                  disabled={generating}
                  className="rounded-full bg-accent px-4 py-2 text-sm font-medium text-on-accent disabled:opacity-60"
                >
                  {generating ? "正在调整…" : "按要求重新生成"}
                </button>
                <button type="button" onClick={() => void toggleHistory()} className="rounded-full border border-line px-4 py-2 text-sm">
                  {history ? "收起历史版本" : "查看历史版本"}
                </button>
              </div>
            </section>
          )}

          {history && (
            <ul className="mt-4 space-y-2">
              {history.versions.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => void openVersion(item.id)}
                    className="w-full rounded-2xl border border-line bg-surface px-4 py-3 text-left text-sm"
                  >
                    第 {item.version} 版 · {item.title}
                    <span className="ml-2 text-muted">{item.status === "active" ? "当前" : "历史"}</span>
                  </button>
                </li>
              ))}
              {history.revisions.map((item) => (
                <li key={item.id} className="px-4 text-sm text-muted">
                  修改原因：{item.reason}
                </li>
              ))}
            </ul>
          )}
        </article>
      )}

    </div>
  );
}

function TaskButton({ label, disabled, onClick }: { label: string; disabled: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="rounded-full border border-line px-3 py-1.5 text-sm font-medium text-ink disabled:opacity-60"
    >
      {label}
    </button>
  );
}
