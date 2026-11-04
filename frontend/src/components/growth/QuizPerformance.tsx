import { useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { GrowthQuizItem, GrowthQuizPoint, GrowthReport, QuizHistoryItem } from "../../types/growth.ts";
import { formatDate } from "../../utils/format.ts";
import { daysBefore, localDateKey } from "../../utils/growthDisplay.ts";

type QuizRange = "7" | "30" | "all";

export function QuizPerformance({
  quizzes,
  today,
  history,
  historyLoading,
  historyError,
  selectedPointId,
}: {
  quizzes: GrowthReport["quizzes"];
  today: string;
  history: QuizHistoryItem[];
  historyLoading: boolean;
  historyError: string | null;
  selectedPointId: number | null;
}) {
  const [range, setRange] = useState<QuizRange>("30");
  const points = selectedPointId === null ? quizzes.by_knowledge_point : quizzes.by_knowledge_point.filter((point) => point.knowledge_point_id === selectedPointId);
  const dated = range === "all" ? historyItems(history) : range === "7" ? quizzes.last_7_days : quizzes.last_30_days;
  const visible = range === "all" ? dated : dated.filter((item) => item.date >= daysBefore(today, range === "7" ? 7 : 30) && item.date <= today);

  return (
    <div>
      <p className="text-sm leading-6 text-slate-500">{quizzes.note}</p>
      <dl className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-5">
        {[
          ["检测次数", quizzes.count],
          ["平均成绩", quizzes.average_score],
          ["最高成绩", quizzes.highest_score],
          ["最低成绩", quizzes.lowest_score],
          ["最近一次", quizzes.latest_score],
        ].map(([label, value]) => (
          <div key={String(label)} className="rounded-2xl bg-mist px-3 py-3">
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="mt-1 font-medium">{value === null ? "暂无" : value}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-4 flex flex-wrap gap-2">
        {(
          [
            ["7", "近 7 天"],
            ["30", "近 30 天"],
            ["all", "全部历史"],
          ] as const
        ).map(([key, label]) => (
          <button key={key} type="button" onClick={() => setRange(key)} className={`rounded-full px-3 py-1.5 text-sm ${range === key ? "bg-ink text-white" : "bg-mist text-slate-600"}`}>
            {label}
          </button>
        ))}
      </div>
      <p className="mt-2 text-xs text-slate-500">
        成绩统计是已提交检测。下面的列表按这里选择的时间范围显示，和页面上方的活动范围相互独立。
        {selectedPointId === null ? "" : " 所选知识点只收窄下方的成绩对比。检测列表没有知识点编号，所以仍显示范围内的全部试卷。"}
      </p>
      {range === "all" && historyLoading ? <p className="mt-3 text-sm text-slate-500">正在读取全部检测历史…</p> : null}
      {range === "all" && historyError ? <p className="mt-3 text-sm text-rose-700">{historyError}</p> : null}
      {visible.length === 0 && !(range === "all" && historyLoading) ? <p className="mt-4 text-sm text-slate-500">这个时间范围里没有检测记录。</p> : null}
      {visible.length > 0 ? (
        <div className="mt-4 h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={visible.map((item) => ({ ...item, label: formatDate(item.date) }))}>
              <CartesianGrid stroke="#e2e8f0" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} width={32} label={{ value: "分数", angle: -90, position: "insideLeft", fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="score" name="成绩" fill="#0f766e" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : null}
      <ul className="mt-4 space-y-2">
        {visible.map((item) => (
          <li key={`${item.id}-${item.date}`} className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-200 px-4 py-3 text-sm">
            <div>
              <p className="font-medium">{item.title}</p>
              <p className="mt-1 text-slate-500">
                {formatDate(item.date)} · {item.score ?? "暂无"} 分
              </p>
            </div>
            {item.id > 0 ? (
              <Link to={`/quiz/${item.id}`} className="font-medium text-accent">
                查看报告
              </Link>
            ) : (
              <span className="text-slate-400">没有检测编号</span>
            )}
          </li>
        ))}
      </ul>
      <h3 className="mt-6 text-sm font-semibold">知识点成绩对比</h3>
      {points.every((point) => point.count === 0) ? <p className="mt-2 text-sm text-slate-500">还没有按知识点分开的检测分数。</p> : <PointBars points={points.filter((point) => point.count > 0)} />}
    </div>
  );
}

function historyItems(history: QuizHistoryItem[]): GrowthQuizItem[] {
  return history
    .filter((item) => item.submitted_at)
    .map((item) => ({
      id: item.id,
      goal_id: item.goal_id,
      title: item.title,
      date: localDateKey(item.submitted_at ?? ""),
      score: item.score,
    }));
}

function PointBars({ points }: { points: GrowthQuizPoint[] }) {
  return (
    <div className="mt-3 h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={points} layout="vertical" margin={{ left: 16 }}>
          <CartesianGrid stroke="#e2e8f0" horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} label={{ value: "平均分", position: "insideBottom", fontSize: 11 }} />
          <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Bar dataKey="average_score" name="平均分" fill="#115e59" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
