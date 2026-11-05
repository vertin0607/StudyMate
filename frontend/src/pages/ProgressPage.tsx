import { useMemo, useState } from "react";

import { GrowthOverview } from "../components/growth/GrowthOverview.tsx";
import { GrowthPanel, PanelMessage } from "../components/growth/GrowthPanel.tsx";
import { KnowledgeGrowth } from "../components/growth/KnowledgeGrowth.tsx";
import { PracticeGrowth } from "../components/growth/PracticeGrowth.tsx";
import { QuizPerformance } from "../components/growth/QuizPerformance.tsx";
import { StudyTrendChart } from "../components/growth/StudyTrendChart.tsx";
import { WeaknessEvolution } from "../components/growth/WeaknessEvolution.tsx";
import { useGoals } from "../hooks/useGoals.ts";
import { useDiagnosisReport, useGrowthReport, useKnowledgeList, useQuizHistory } from "../hooks/useGrowthArchive.ts";
import type { GrowthDays } from "../types/growth.ts";

const dayChoices: GrowthDays[] = [7, 30, 90];

export function ProgressPage() {
  const goals = useGoals();
  const [goalId, setGoalId] = useState<number | null>(null);
  const [days, setDays] = useState<GrowthDays>(30);
  const [pointId, setPointId] = useState<number | null>(null);
  const growth = useGrowthReport(goalId, days);
  const knowledge = useKnowledgeList(goalId);
  const diagnosis = useDiagnosisReport(goalId);
  const goalIds = useMemo(() => {
    if (goalId !== null) {
      return [goalId];
    }
    return (goals.goals ?? []).map((goal) => goal.id);
  }, [goalId, goals.goals]);
  const history = useQuizHistory(goalIds);
  const current = growth.data && growth.data.goal_id === goalId && growth.data.days === days ? growth.data : null;
  const points = current?.mastery.points ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <header>
        <p className="text-sm font-medium text-accent">学习记录</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">学习成长档案</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
          这些数字来自已经保存的任务、检测、复习和判题记录。打开页面只读取数据，不会生成计划，也不会调用模型。
        </p>
      </header>

      <div className="flex flex-col gap-3 rounded-3xl border border-line bg-surface p-4 md:flex-row md:items-end md:justify-between">
        <label className="text-sm">
          <span className="text-muted">学习目标</span>
          <select
            value={goalId ?? ""}
            onChange={(event) => {
              setGoalId(event.target.value ? Number(event.target.value) : null);
              setPointId(null);
            }}
            className="mt-1 block w-full rounded-2xl border border-line bg-surface px-3 py-2 md:w-64"
          >
            <option value="">全部目标</option>
            {(goals.goals ?? []).map((goal) => (
              <option key={goal.id} value={goal.id}>
                {goal.title}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="text-muted">知识点</span>
          <select
            value={pointId ?? ""}
            onChange={(event) => setPointId(event.target.value ? Number(event.target.value) : null)}
            className="mt-1 block w-full rounded-2xl border border-line bg-surface px-3 py-2 md:w-64"
          >
            <option value="">全部知识点</option>
            {points.map((point) => (
              <option key={point.knowledge_point_id} value={point.knowledge_point_id}>
                {point.name}
              </option>
            ))}
          </select>
        </label>
        <div>
          <p className="text-sm text-muted">活动范围</p>
          <div className="mt-1 flex gap-2">
            {dayChoices.map((choice) => (
              <button
                key={choice}
                type="button"
                onClick={() => setDays(choice)}
                className={`rounded-full px-3 py-1.5 text-sm ${days === choice ? "bg-accent text-on-accent" : "bg-mist text-muted"}`}
              >
                近 {choice} 天
              </button>
            ))}
          </div>
        </div>
      </div>
      {goals.error ? <p className="text-sm text-rose-700">{goals.error}</p> : null}

      <GrowthPanel title="学习概况" hint={goalId === null ? "任务、检测和复习包含全部目标。练习和判题是全部题库。" : "任务、检测、复习和连续天数只统计当前目标。练习和判题仍是全部题库。"}>
        {growth.loading && !growth.error ? <PanelMessage tone="loading">正在读取学习概况…</PanelMessage> : null}
        {growth.error ? <PanelMessage tone="error" onRetry={growth.reload}>{growth.error}</PanelMessage> : null}
        {current && !growth.loading ? <GrowthOverview summary={current.summary} goalSelected={goalId !== null} /> : null}
      </GrowthPanel>

      <GrowthPanel title="学习活动趋势" hint={`近 ${days} 天。日期连续排列，没有记录的日期标成无活动。`}>
        {growth.loading && !growth.error ? <PanelMessage tone="loading">正在读取趋势…</PanelMessage> : null}
        {growth.error ? <PanelMessage tone="error" onRetry={growth.reload}>{growth.error}</PanelMessage> : null}
        {current && !growth.loading ? <StudyTrendChart studySeries={current.series} practiceSeries={current.practice.series} goalSelected={goalId !== null} /> : null}
      </GrowthPanel>

      <div className="grid gap-4 xl:grid-cols-2">
        <GrowthPanel title="知识掌握成长" hint="尚未评估不会显示成 0%。少于两次记录时不判断上升或下降。">
          {growth.loading && !growth.error ? <PanelMessage tone="loading">正在读取掌握度…</PanelMessage> : null}
          {growth.error ? <PanelMessage tone="error" onRetry={growth.reload}>{growth.error}</PanelMessage> : null}
          {knowledge.error ? <p className="mb-3 text-sm text-rose-700">{knowledge.error}</p> : null}
          {current && !growth.loading ? <KnowledgeGrowth points={current.mastery.points} labels={knowledge.data ?? []} selectedId={pointId} /> : null}
        </GrowthPanel>
        <GrowthPanel title="检测成绩" hint="成绩变化只说明这些试卷的得分，不能单独证明能力提升了多少。">
          {growth.loading && !growth.error ? <PanelMessage tone="loading">正在读取检测成绩…</PanelMessage> : null}
          {growth.error ? <PanelMessage tone="error" onRetry={growth.reload}>{growth.error}</PanelMessage> : null}
          {current && !growth.loading ? (
            <QuizPerformance
              quizzes={current.quizzes}
              today={current.today}
              history={history.data ?? []}
              historyLoading={history.loading}
              historyError={history.error}
              selectedPointId={pointId}
            />
          ) : null}
        </GrowthPanel>
      </div>

      <GrowthPanel title="刷题成长">
        {growth.loading && !growth.error ? <PanelMessage tone="loading">正在读取刷题记录…</PanelMessage> : null}
        {growth.error ? <PanelMessage tone="error" onRetry={growth.reload}>{growth.error}</PanelMessage> : null}
        {current && !growth.loading ? <PracticeGrowth practice={current.practice} goalSelected={goalId !== null} /> : null}
      </GrowthPanel>

      <GrowthPanel title="薄弱点变化" hint="已确认和初步发现来自规则诊断。已改善只采用同一知识点或同一题目的前后证据。">
        {diagnosis.loading && !diagnosis.error ? <PanelMessage tone="loading">正在读取诊断…</PanelMessage> : null}
        {diagnosis.error ? <PanelMessage tone="error" onRetry={diagnosis.reload}>{diagnosis.error}</PanelMessage> : null}
        {diagnosis.data && current ? (
          <WeaknessEvolution
            diagnosis={diagnosis.data}
            improved={current.weaknesses.improved}
            stillPresent={current.weaknesses.still_present}
            note={current.weaknesses.note}
          />
        ) : null}
        {diagnosis.data && !current && !growth.loading ? (
          <WeaknessEvolution
            diagnosis={diagnosis.data}
            improved={[]}
            stillPresent={[]}
            note="成长汇总没有读到，这里只显示诊断结果，不把任何问题标成已改善。"
          />
        ) : null}
      </GrowthPanel>
    </div>
  );
}
