import type { GoalStatus } from "../types/goal.ts";

const labels: Record<GoalStatus, string> = {
  active: "进行中",
  paused: "已暂停",
  completed: "已完成",
};

const styles: Record<GoalStatus, string> = {
  active: "bg-accent-soft text-accent",
  paused: "bg-amber-50 text-amber-800",
  completed: "bg-soft text-muted",
};

export function GoalStatusBadge({ status }: { status: GoalStatus }) {
  return (
    <span className={`inline-flex rounded-full px-3 py-1 text-sm font-medium ${styles[status]}`}>
      {labels[status]}
    </span>
  );
}
