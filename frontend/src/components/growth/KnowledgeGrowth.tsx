import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { fetchKnowledgeHistory } from "../../services/knowledge.ts";
import type { GrowthMasteryPoint, KnowledgeHistoryEvent, KnowledgeListPoint } from "../../types/growth.ts";
import { getErrorMessage } from "../../utils/apiError.ts";
import { formatDate } from "../../utils/format.ts";
import { directionLabels, localDateKey } from "../../utils/growthDisplay.ts";

export function KnowledgeGrowth({
  points,
  labels,
  selectedId,
}: {
  points: GrowthMasteryPoint[];
  labels: KnowledgeListPoint[];
  selectedId: number | null;
}) {
  const visible = selectedId === null ? points : points.filter((point) => point.knowledge_point_id === selectedId);
  if (visible.length === 0) {
    return <p className="text-sm text-slate-500">这个范围里还没有知识点。生成学习计划后，这里会列出需要追踪的内容。</p>;
  }
  return (
    <ul className="space-y-3">
      {visible.map((point) => (
        <KnowledgeCard key={point.knowledge_point_id} point={point} label={labels.find((item) => item.id === point.knowledge_point_id)} />
      ))}
    </ul>
  );
}

function KnowledgeCard({ point, label }: { point: GrowthMasteryPoint; label: KnowledgeListPoint | undefined }) {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<KnowledgeHistoryEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const enough = point.history.length >= 2 && point.direction !== "insufficient";

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (!next || events) {
      return;
    }
    try {
      setEvents(await fetchKnowledgeHistory(point.knowledge_point_id));
    } catch (reason) {
      setError(getErrorMessage(reason, "读取掌握度历史失败"));
    }
  }

  return (
    <li className="rounded-2xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">{point.name}</h3>
          <p className="mt-1 text-sm text-slate-500">{label?.status_label ?? "状态暂时没有读到"}</p>
        </div>
        <p className="text-sm text-slate-600">{point.mastery_assessed ? `掌握度 ${point.current_mastery}` : "尚未评估"}</p>
      </div>
      {point.mastery_assessed ? (
        <div className="mt-3 h-2 rounded-full bg-slate-100">
          <div className="h-2 rounded-full bg-accent" style={{ width: `${point.current_mastery ?? 0}%` }} />
        </div>
      ) : null}
      <p className="mt-3 text-sm text-slate-600">
        趋势：{enough ? directionLabels[point.direction] : "数据不足"} · 历史记录 {point.history.length} 条
        {point.history.length < 2 ? "。只有一次或还没有检测，不能判断进步或退步。" : ""}
      </p>
      <button type="button" onClick={() => void toggle()} className="mt-3 text-sm font-medium text-accent">
        {open ? "收起历史" : "展开历史曲线"}
      </button>
      {open ? <HistoryChart events={events} error={error} fallback={point.history} /> : null}
    </li>
  );
}

function HistoryChart({
  events,
  error,
  fallback,
}: {
  events: KnowledgeHistoryEvent[] | null;
  error: string | null;
  fallback: GrowthMasteryPoint["history"];
}) {
  if (error) {
    return <p className="mt-3 text-sm text-rose-700">{error}</p>;
  }
  if (!events) {
    return <p className="mt-3 text-sm text-slate-500">正在读取历史记录…</p>;
  }
  const rows =
    events.length > 0
      ? [...events].reverse().map((event) => ({ label: formatDate(localDateKey(event.created_at)), mastery_level: event.new_level, quiz_score: event.quiz_score }))
      : fallback.map((event) => ({ label: formatDate(event.date), mastery_level: event.mastery_level, quiz_score: event.quiz_score }));
  if (rows.length < 2) {
    return <p className="mt-3 text-sm text-slate-500">{rows.length === 0 ? "还没有掌握度记录。" : `目前只有 1 条记录，分数 ${rows[0]?.quiz_score ?? "—"}。数据不足，不画趋势。`}</p>;
  }
  return (
    <div className="mt-4 h-52">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows}>
          <CartesianGrid stroke="#e2e8f0" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} width={32} label={{ value: "掌握度", angle: -90, position: "insideLeft", fontSize: 11 }} />
          <Tooltip />
          <Line type="monotone" dataKey="mastery_level" name="掌握度" stroke="#0f766e" strokeWidth={2} dot />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
