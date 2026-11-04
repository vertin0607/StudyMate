import type { GrowthSummary } from "../../types/growth.ts";
import { formatPassRate, formatPracticeDuration } from "../../utils/growthDisplay.ts";

export function GrowthOverview({ summary, goalSelected }: { summary: GrowthSummary; goalSelected: boolean }) {
  const primary = [
    ["累计学习天数", String(summary.study_day_count), goalSelected ? "当前目标" : "全部目标"],
    ["连续学习天数", String(summary.current_streak_days), summary.studied_today ? "今天有学习活动" : "今天还没有学习活动"],
    ["完成任务", String(summary.completed_task_count), "有完成时间的任务"],
    ["完成检测", String(summary.completed_quiz_count), "已提交的检测"],
  ];
  const secondary = [
    ["复习次数", String(summary.review_count)],
    ["练习题数", String(summary.practiced_problem_count)],
    ["提交次数", String(summary.submission_count)],
    ["本地通过题数", String(summary.local_accepted_problem_count)],
    ["本地判题通过率", formatPassRate(summary.pass_rate, summary.pass_rate_denominator)],
    ["实际练习时长", formatPracticeDuration(summary.actual_practice_seconds)],
  ];

  return (
    <div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {primary.map(([label, value, note]) => (
          <div key={label} className="rounded-3xl bg-ink px-5 py-4 text-white">
            <p className="text-sm text-slate-300">{label}</p>
            <p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p>
            <p className="mt-2 text-xs leading-5 text-slate-400">{note}</p>
          </div>
        ))}
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3">
        {secondary.map(([label, value]) => (
          <div key={label} className="rounded-2xl bg-mist px-4 py-3">
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="mt-1 text-sm font-medium">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs leading-5 text-slate-500">
        本地判题通过率的分母不含系统异常和尚未判题。自评完成不算正式通过。这里的通过是本地测试通过。
        {summary.pass_rate_denominator > 0 ? ` 当前 ${summary.pass_rate_numerator}/${summary.pass_rate_denominator}。` : ""}
      </p>
    </div>
  );
}
