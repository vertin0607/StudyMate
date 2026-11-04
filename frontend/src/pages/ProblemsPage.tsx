import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { fetchPracticeStatistics, fetchPracticeTrends } from "../services/practice.ts";
import { fetchProblemStatistics, fetchProblems, fetchTopics } from "../services/problems.ts";
import type { ProblemQuery } from "../services/problems.ts";
import type { ProblemStatistics, ProblemSummary, TopicGroup } from "../types/problem.ts";
import { learningStatusLabels, type LearningStatusName, type PracticeStatistics, type PracticeTrendDay } from "../types/practice.ts";
import { getErrorMessage } from "../utils/apiError.ts";

const difficultyLabels: Record<string, string> = { unknown: "未设置", easy: "简单", medium: "中等", hard: "困难" };
const analysisLabels: Record<string, string> = { pending: "待分析", analyzing: "分析中", completed: "已分析", failed: "分析失败" };

export function ProblemsPage() {
  const [stats, setStats] = useState<ProblemStatistics | null>(null);
  const [practiceStats, setPracticeStats] = useState<PracticeStatistics | null>(null);
  const [trends, setTrends] = useState<PracticeTrendDay[]>([]);
  const [problems, setProblems] = useState<ProblemSummary[]>([]);
  const [topics, setTopics] = useState<TopicGroup[]>([]);
  const [query, setQuery] = useState<ProblemQuery>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback((id: number, next: ProblemQuery) => {
    Promise.all([fetchProblemStatistics(), fetchPracticeStatistics(), fetchPracticeTrends(), fetchProblems(next), fetchTopics()])
      .then(([statistics, practice, days, rows, groups]) => {
        if (requestId.current !== id) {
          return;
        }
        setStats(statistics);
        setPracticeStats(practice);
        setTrends(days);
        setProblems(rows);
        setTopics(groups);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (requestId.current !== id) {
          return;
        }
        setError(getErrorMessage(reason, "读取题库失败"));
      })
      .finally(() => {
        if (requestId.current === id) {
          setLoading(false);
        }
      });
  }, []);

  useEffect(() => {
    const id = requestId.current + 1;
    requestId.current = id;
    load(id, query);
  }, [load, query]);

  function updateQuery(patch: ProblemQuery) {
    setQuery((current) => ({ ...current, ...patch }));
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-accent">题库</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">我的题库</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">题目和测试数据由你粘贴保存。打开这个页面不会调用 DeepSeek。</p>
        </div>
        <div className="flex gap-2">
          <Link to="/problems/wrong" className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm">
            错题本
          </Link>
          <Link to="/problems/topics" className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm">
            知识点分类
          </Link>
          <Link to="/problems/import" className="rounded-full bg-ink px-4 py-2 text-sm text-white">
            导入题目
          </Link>
        </div>
      </div>
      {loading && <p className="mt-6 text-sm text-slate-500">正在读取题库…</p>}
      {error && <p className="mt-6 text-sm text-rose-700">{error}</p>}
      {stats && (
        <dl className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-5">
          {[
            ["题目总数", stats.total],
            ["已分析", stats.analyzed],
            ["待分析", stats.pending],
            ["已通过", stats.passed],
            ["待复习", stats.to_review],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded-2xl bg-white px-4 py-3">
              <dt className="text-sm text-slate-500">{label}</dt>
              <dd className="mt-1 text-2xl font-semibold">{value}</dd>
            </div>
          ))}
        </dl>
      )}
      <p className="mt-3 text-xs text-slate-500">上方题库统计里的「已通过」和「待复习」仍是旧字段，固定为 0。真实判题结果看下面的练习统计。用户自评完成和系统判题通过分开计数。</p>
      {practiceStats && (
        <dl className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            ["待练习", practiceStats.todo],
            ["练习中", practiceStats.attempting],
            ["已开始练习", practiceStats.started_problems],
            ["用户自评完成", practiceStats.self_completed],
            ["系统判题通过", practiceStats.accepted],
            ["系统判题未通过", practiceStats.wrong_answer],
            ["编译失败", practiceStats.compile_error],
            ["运行超时", practiceStats.time_limit_exceeded],
            ["运行异常", practiceStats.runtime_error],
            ["错题", practiceStats.wrong_count],
            ["累计提交", practiceStats.submission_count],
            ["累计练习", practiceStats.practice_total],
            ["今日练习", practiceStats.practice_today],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded-2xl bg-white px-4 py-3">
              <dt className="text-sm text-slate-500">{label}</dt>
              <dd className="mt-1 text-2xl font-semibold">{value}</dd>
            </div>
          ))}
        </dl>
      )}
      {trends.length > 0 && (
        <p className="mt-3 text-sm text-slate-500">
          近 7 日练习 {trends.map((day) => day.practice_count).join(" / ")} 次，提交 {trends.map((day) => day.submission_count).join(" / ")} 次。
        </p>
      )}
      <form className="mt-6 grid gap-3 md:grid-cols-3" onSubmit={(event) => event.preventDefault()}>
        <input value={query.keyword ?? ""} onChange={(event) => updateQuery({ keyword: event.target.value })} placeholder="搜索标题或题号" className="rounded-2xl border border-slate-200 px-4 py-2 text-sm" />
        <select value={query.difficulty ?? ""} onChange={(event) => updateQuery({ difficulty: event.target.value })} className="rounded-2xl border border-slate-200 px-4 py-2 text-sm">
          <option value="">全部难度</option>
          <option value="easy">简单</option>
          <option value="medium">中等</option>
          <option value="hard">困难</option>
          <option value="unknown">未设置</option>
        </select>
        <select value={query.analysis_status ?? ""} onChange={(event) => updateQuery({ analysis_status: event.target.value })} className="rounded-2xl border border-slate-200 px-4 py-2 text-sm">
          <option value="">全部分析状态</option>
          <option value="pending">待分析</option>
          <option value="completed">已分析</option>
          <option value="failed">分析失败</option>
        </select>
        <select value={query.topic_id ?? ""} onChange={(event) => updateQuery({ topic_id: event.target.value ? Number(event.target.value) : undefined })} className="rounded-2xl border border-slate-200 px-4 py-2 text-sm">
          <option value="">全部知识点</option>
          {topics.flatMap((group) => group.topics).map((topic) => (
            <option key={topic.id} value={topic.id}>{topic.name}</option>
          ))}
        </select>
        <input value={query.course ?? ""} onChange={(event) => updateQuery({ course: event.target.value })} placeholder="课程名称" className="rounded-2xl border border-slate-200 px-4 py-2 text-sm" />
        <input value={query.source_platform ?? ""} onChange={(event) => updateQuery({ source_platform: event.target.value })} placeholder="OJ 来源" className="rounded-2xl border border-slate-200 px-4 py-2 text-sm" />
      </form>
      {!loading && problems.length === 0 && <p className="mt-6 rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-8 text-sm text-slate-600">还没有题目。可以把 OJ 题面粘贴进来。</p>}
      <ul className="mt-4 space-y-3">
        {problems.map((problem) => (
          <li key={problem.id}>
            <Link to={`/problems/${problem.id}`} className="block rounded-3xl border border-slate-200 bg-white p-5">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h2 className="text-lg font-semibold">{problem.title}</h2>
                <span className="text-sm text-slate-500">{analysisLabels[problem.analysis_status] ?? problem.analysis_status}</span>
              </div>
              <p className="mt-2 text-sm text-slate-600">
                {problem.source_platform}
                {problem.source_problem_id ? ` · ${problem.source_problem_id}` : ""}
                {problem.course ? ` · ${problem.course}` : ""}
                {` · ${difficultyLabels[problem.difficulty] ?? problem.difficulty}`}
                {` · ${learningStatusLabels[(problem.learning_status ?? "todo") as LearningStatusName] ?? "待练习"}`}
              </p>
              {problem.topics.length > 0 && <p className="mt-2 text-sm text-slate-500">{problem.topics.map((topic) => topic.name).join("、")}</p>}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
