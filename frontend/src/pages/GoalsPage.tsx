import { useState } from "react";
import { Link } from "react-router-dom";

import { ConfirmDialog } from "../components/ConfirmDialog.tsx";
import { GoalActions } from "../components/GoalActions.tsx";
import { GoalForm } from "../components/GoalForm.tsx";
import { GoalStatusBadge } from "../components/GoalStatusBadge.tsx";
import { useGoals } from "../hooks/useGoals.ts";
import { createGoal, deleteGoal, updateGoal, updateGoalStatus } from "../services/goals.ts";
import { emptyGoalInput, type Goal, type GoalInput, type GoalStatus } from "../types/goal.ts";
import { getErrorMessage } from "../utils/apiError.ts";
import { formatDate } from "../utils/format.ts";

export function GoalsPage() {
  const { goals, loading, error, reload } = useGoals();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Goal | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<Goal | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  function openCreate() {
    setEditing(null);
    setFormError(null);
    setCreating(true);
  }

  function openEdit(goal: Goal) {
    setCreating(false);
    setFormError(null);
    setEditing(goal);
  }

  function closeForm() {
    setCreating(false);
    setEditing(null);
    setFormError(null);
  }

  async function handleSubmit(input: GoalInput) {
    setSubmitting(true);
    setFormError(null);
    try {
      if (editing) {
        await updateGoal(editing.id, input);
      } else {
        await createGoal(input);
      }
      closeForm();
      reload();
    } catch (reason) {
      setFormError(getErrorMessage(reason, "保存学习目标失败"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStatus(goal: Goal, status: GoalStatus) {
    setBusyId(goal.id);
    setActionError(null);
    try {
      await updateGoalStatus(goal.id, status);
      reload();
    } catch (reason) {
      setActionError(getErrorMessage(reason, "修改学习目标状态失败"));
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete() {
    if (!pendingDelete) {
      return;
    }
    setDeleting(true);
    setActionError(null);
    try {
      await deleteGoal(pendingDelete.id);
      setPendingDelete(null);
      if (editing?.id === pendingDelete.id) {
        closeForm();
      }
      reload();
    } catch (reason) {
      setActionError(getErrorMessage(reason, "删除学习目标失败"));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-accent">学习目标</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">你正在学什么</h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
            每个目标会单独保存在本地数据库里。暂停后可以恢复，删除前会再确认一次。
          </p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="rounded-full bg-ink px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
        >
          新建学习目标
        </button>
      </div>

      {creating && (
        <div className="mt-6">
          <GoalForm
            key="create"
            initial={emptyGoalInput}
            submitLabel="创建目标"
            submitting={submitting}
            error={formError}
            onSubmit={handleSubmit}
            onCancel={closeForm}
          />
        </div>
      )}

      {editing && (
        <div className="mt-6">
          <GoalForm
            key={editing.id}
            initial={editing}
            submitLabel="保存修改"
            submitting={submitting}
            error={formError}
            onSubmit={handleSubmit}
            onCancel={closeForm}
          />
        </div>
      )}

      {actionError && (
        <p className="mt-4 text-sm text-rose-700" role="alert">
          {actionError}
        </p>
      )}

      <div className="mt-6">
        {loading && <p className="text-sm text-slate-500">正在读取学习目标…</p>}
        {!loading && error && (
          <div className="rounded-3xl border border-rose-200 bg-rose-50 p-6 text-sm leading-6 text-rose-800">
            <p>{error}</p>
            <button type="button" onClick={reload} className="mt-4 rounded-full bg-ink px-4 py-2 text-white">
              重新读取
            </button>
          </div>
        )}
        {!loading && !error && goals.length === 0 && (
          <div className="rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-10 text-sm leading-6 text-slate-500">
            还没有学习目标。创建之后，首页上的数量会跟着变化。
          </div>
        )}
        {!loading && !error && goals.length > 0 && (
          <ul className="space-y-4">
            {goals.map((goal) => (
              <li key={goal.id} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <Link to={`/goals/${goal.id}`} className="text-xl font-semibold tracking-tight hover:text-accent">
                      {goal.title}
                    </Link>
                    <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{goal.description}</p>
                  </div>
                  <GoalStatusBadge status={goal.status} />
                </div>
                <p className="mt-4 text-sm text-slate-500">
                  预计 {formatDate(goal.target_date)} 完成 · 每天 {goal.daily_minutes} 分钟
                </p>
                <div className="mt-4">
                  <GoalActions
                    goal={goal}
                    busy={busyId === goal.id}
                    onEdit={() => openEdit(goal)}
                    onStatus={(status) => void handleStatus(goal, status)}
                    onDelete={() => setPendingDelete(goal)}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {pendingDelete && (
        <ConfirmDialog
          title="删除这个学习目标？"
          description={`「${pendingDelete.title}」会从数据库中删除，而且不能恢复。`}
          confirmLabel="确认删除"
          busy={deleting}
          onConfirm={() => void handleDelete()}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </div>
  );
}
