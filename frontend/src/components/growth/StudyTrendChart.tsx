import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useChartPalette } from "../../themes/useChartPalette.ts";
import type { GrowthDay } from "../../types/growth.ts";
import { formatDate } from "../../utils/format.ts";
import { formatPracticeDuration } from "../../utils/growthDisplay.ts";

type Metric = "completed_task_count" | "completed_quiz_count" | "review_count" | "submission_count" | "duration";

const metrics: { key: Metric; label: string; unit: string; library: boolean }[] = [
  { key: "completed_task_count", label: "完成任务", unit: "个", library: false },
  { key: "completed_quiz_count", label: "完成检测", unit: "次", library: false },
  { key: "review_count", label: "复习次数", unit: "次", library: false },
  { key: "submission_count", label: "提交次数", unit: "次", library: true },
  { key: "duration", label: "实际练习时长", unit: "秒", library: true },
];

export function StudyTrendChart({ studySeries, practiceSeries, goalSelected }: { studySeries: GrowthDay[]; practiceSeries: GrowthDay[]; goalSelected: boolean }) {
  const palette = useChartPalette();
  const [metric, setMetric] = useState<Metric>("completed_task_count");
  const selected = metrics.find((item) => item.key === metric) ?? metrics[0];
  const source = selected.library ? practiceSeries : studySeries;
  const rows = source.map((day) => {
    const inactive = selected.key === "duration" ? !day.has_duration_record : !day.has_activity;
    const raw = selected.key === "duration" ? day.actual_practice_seconds : day[selected.key];
    return {
      date: day.date,
      label: formatDate(day.date).replace("年", "/").replace("月", "/").replace("日", ""),
      value: inactive ? null : raw,
      inactive,
      durationText: formatPracticeDuration(day.actual_practice_seconds),
    };
  });

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {metrics.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setMetric(item.key)}
            className={`rounded-full px-3 py-1.5 text-sm ${metric === item.key ? "bg-accent text-on-accent" : "bg-mist text-muted"}`}
          >
            {item.label}
          </button>
        ))}
      </div>
      <p className="mt-3 text-xs leading-5 text-muted">
        横轴是连续的本地日期，纵轴是{selected.label}（{selected.unit}）。没有活动的日期不画成 0。
        {selected.library ? " 提交次数和实际练习时长统计全部题库。" : goalSelected ? " 这项随当前学习目标变化。" : " 这项包含全部学习目标。"}
      </p>
      <div className="mt-4 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows}>
            <CartesianGrid stroke={palette.grid} vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: palette.tick }} interval="preserveStartEnd" />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: palette.tick }} width={36} label={{ value: selected.unit, angle: -90, position: "insideLeft", fontSize: 11, fill: palette.tick }} />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.[0]) {
                  return null;
                }
                const row = payload[0].payload as (typeof rows)[number];
                let text = `${row.value ?? 0} ${selected.unit}`;
                if (row.inactive) {
                  text = selected.key === "duration" ? "无有效时长记录" : "无活动";
                } else if (selected.key === "duration") {
                  text = row.durationText;
                }
                return (
                  <div className="rounded-xl border border-line bg-surface px-3 py-2 text-xs">
                    <p>{formatDate(row.date)}</p>
                    <p className="mt-1 font-medium">
                      {selected.label}：{text}
                    </p>
                  </div>
                );
              }}
            />
            <Bar dataKey="value" name={selected.label} fill={palette.bar} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
