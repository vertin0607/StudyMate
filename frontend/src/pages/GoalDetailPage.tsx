import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ConfirmDialog } from "../components/ConfirmDialog.tsx";
import { GoalActions } from "../components/GoalActions.tsx";
import { GoalForm } from "../components/GoalForm.tsx";
import { GoalStatusBadge } from "../components/GoalStatusBadge.tsx";
import { useGoal } from "../hooks/useGoals.ts";
import { deleteGoal, updateGoal, updateGoalStatus } from "../services/goals.ts";
import type { GoalInput, GoalStatus } from "../types/goal.ts";
import { getErrorMessage } from "../utils/apiError.ts";
import { formatDate, formatServerTime } from "../utils/format.ts";

export function GoalDetailPage() {
  const params = useParams();
  const navigate = useNavigate();
  const goalId = Number(params.id);
  const validId = Number.isInteger(goalId) && goalId > 0 ? goalId : null;
  const { goal, setGoal, loading, error, reload } = useGoal(validId);
  const [editing, setEditing] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  async function handleSubmit(input: GoalInput) {
    if (!goal) {
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      setGoal(await updateGoal(goal.id, input));
      setEditing(false);
    } catch (reason) {
      setFormError(getErrorMessage(reason, "保存学习目标失败"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStatus(status: GoalStatus) {
    if (!goal) {
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      setGoal(await updateGoalStatus(goal.id, status));
    } catch (reason) {
      setActionError(getErrorMessage(reason, "修改学习目标状态失败"));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!goal) {
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      await deleteGoal(goal.id);
      navigate("/goals");
    } catch (reason) {
      setActionError(getErrorMessage(reason, "删除学习目标失败"));
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/goals" className="text-sm font-medium text-accent">
        返回学习目标
      </Link>

      {validId === null && <p className="mt-6 text-sm text-rose-700">这个地址里的目标编号不正确。</p>}
      {loading && <p className="mt-6 text-sm text-slate-500">正在读取学习目标…</p>}
      {!loading && error && (
        <div className="mt-6 rounded-3xl border border-rose-200 bg-rose-50 p-6 text-sm leading-6 text-rose-800">
          <p>{error}</p>
          <button type="button" onClick={reload} className="mt-4 rounded-full bg-ink px-4 py-2 text-white">
            重新读取
          </button>
        </div>
      )}

      {goal && (
        <article className="mt-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-accent">目标详情</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">{goal.title}</h1>
            </div>
            <GoalStatusBadge status={goal.status} />
          </div>
          <p className="mt-4 text-base leading-7 text-slate-600">{goal.description}</p>
          <dl className="mt-6 grid gap-3 rounded-3xl border border-slate-200 bg-white p-6 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-slate-500">预计完成</dt>
              <dd className="mt-1 font-medium">{formatDate(goal.target_date)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">每日学习</dt>
              <dd className="mt-1 font-medium">{goal.daily_minutes} 分钟</dd>
            </div>
            <div>
              <dt className="text-slate-500">创建时间</dt>
              <dd className="mt-1 font-medium">{formatServerTime(goal.created_at)}</dd>
            </div>
          </dl>
          {actionError && (
            <p className="mt-4 text-sm text-rose-700" role="alert">
              {actionError}
            </p>
          )}
          <div className="mt-4">
            <GoalActions
              goal={goal}
              busy={busy || submitting}
              onEdit={() => {
                setFormError(null);
                setEditing(true);
              }}
              onStatus={(status) => void handleStatus(status)}
              onDelete={() => setConfirmingDelete(true)}
            />
          </div>
          {editing && (
            <div className="mt-6">
              <GoalForm
                key={`${goal.id}-${goal.updated_at}`}
                initial={goal}
                submitLabel="保存修改"
                submitting={submitting}
                error={formError}
                onSubmit={(input) => void handleSubmit(input)}
                onCancel={() => setEditing(false)}
              />
            </div>
          )}
        </article>
      )}

      {confirmingDelete && goal && (
        <ConfirmDialog
          title="删除这个学习目标？"
          description={`「${goal.title}」会从数据库中删除，而且不能恢复。`}
          confirmLabel="确认删除"
          busy={busy}
          onConfirm={() => void handleDelete()}
          onCancel={() => setConfirmingDelete(false)}
        />
      )}
    </div>
  );
}
