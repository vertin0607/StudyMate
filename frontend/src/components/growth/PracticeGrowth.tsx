import { useState } from "react";

import type { GrowthReport } from "../../types/growth.ts";
import { formatPassRate, formatPracticeDuration, judgeCountLabels } from "../../utils/growthDisplay.ts";

export function PracticeGrowth({ practice, goalSelected }: { practice: GrowthReport["practice"]; goalSelected: boolean }) {
  const [open, setOpen] = useState(false);
  const counts = practice.judge_counts;
  return (
    <div>
      <p className="rounded-2xl bg-accent-soft px-4 py-3 text-sm leading-6 text-slate-700">
        全部题库统计。当前刷题数据统计范围为全部题库，不随学习目标筛选变化。
        {goalSelected ? " 你正在查看某一个学习目标，下面的数字仍然是全部题目。" : ""}
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          ["练习题数", String(practice.practiced_problem_count)],
          ["提交次数", String(practice.submission_count)],
          ["本地通过题数", String(practice.local_accepted_problem_count)],
          ["当前错题数", String(practice.wrong_record_count)],
          ["本地判题通过率", formatPassRate(practice.pass_rate, practice.pass_rate_denominator)],
          ["实际练习时长", formatPracticeDuration(practice.actual_practice_seconds)],
          ["自评完成", `${practice.self_completed_problem_count} 题`],
          ["已提交题目", String(practice.submitted_problem_count)],
        ].map(([label, value]) => (
          <div key={label} className="rounded-2xl bg-mist px-4 py-3">
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="mt-1 text-sm font-medium">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs leading-5 text-slate-500">
        {practice.pass_rate_note} {practice.duration_note} 自评完成不是正式通过。系统异常单独列出，不算用户答错。尚未判题不算通过或失败。
      </p>
      <button type="button" onClick={() => setOpen((value) => !value)} className="mt-3 text-sm font-medium text-accent">
        {open ? "收起判题分类" : "展开判题分类"}
      </button>
      {open ? (
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {judgeCountLabels.map(([key, label]) => (
            <li key={key} className="flex items-center justify-between rounded-2xl border border-slate-200 px-4 py-2 text-sm">
              <span>{label}</span>
              <span className="font-medium">{counts[key]} 次</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
