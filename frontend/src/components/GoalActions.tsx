import type { Goal, GoalStatus } from "../types/goal.ts";

type GoalActionsProps = {
  goal: Goal;
  busy: boolean;
  onEdit: () => void;
  onStatus: (status: GoalStatus) => void;
  onDelete: () => void;
};

const buttonClass =
  "rounded-full border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-60";

export function GoalActions({ goal, busy, onEdit, onStatus, onDelete }: GoalActionsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <button type="button" className={buttonClass} disabled={busy} onClick={onEdit}>
        编辑
      </button>
      {goal.status === "active" && (
        <button type="button" className={buttonClass} disabled={busy} onClick={() => onStatus("paused")}>
          暂停
        </button>
      )}
      {goal.status !== "active" && (
        <button type="button" className={buttonClass} disabled={busy} onClick={() => onStatus("active")}>
          恢复
        </button>
      )}
      {goal.status !== "completed" && (
        <button type="button" className={buttonClass} disabled={busy} onClick={() => onStatus("completed")}>
          完成
        </button>
      )}
      <button
        type="button"
        className="rounded-full border border-rose-200 px-3 py-1.5 text-sm font-medium text-rose-700 transition hover:bg-rose-50 disabled:opacity-60"
        disabled={busy}
        onClick={onDelete}
      >
        删除
      </button>
    </div>
  );
}
