import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { deleteWrongProblem, fetchWrongProblems, updateWrongProblem } from "../services/practice.ts";
import { fetchTopics } from "../services/problems.ts";
import type { TopicGroup } from "../types/problem.ts";
import { reasonLabels, type WrongProblem } from "../types/practice.ts";
import { getErrorMessage } from "../utils/apiError.ts";

const difficultyLabels: Record<string, string> = { unknown: "未设置", easy: "简单", medium: "中等", hard: "困难" };

export function WrongProblemsPage() {
  const [rows, setRows] = useState<WrongProblem[]>([]);
  const [topics, setTopics] = useState<TopicGroup[]>([]);
  const [difficulty, setDifficulty] = useState("");
  const [topicId, setTopicId] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [reasonType, setReasonType] = useState("other");
  const [reasonDetail, setReasonDetail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const requestId = useRef(0);

  useEffect(() => {
    const id = requestId.current + 1;
    requestId.current = id;
    Promise.all([
      fetchWrongProblems({ difficulty: difficulty || undefined, topic_id: topicId ? Number(topicId) : undefined }),
      fetchTopics(),
    ])
      .then(([problems, groups]) => {
        if (requestId.current !== id) {
          return;
        }
        setRows(problems);
        setTopics(groups);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (requestId.current === id) {
          setError(getErrorMessage(reason, "读取错题失败"));
        }
      })
      .finally(() => {
        if (requestId.current === id) {
          setLoading(false);
        }
      });
  }, [difficulty, topicId]);

  async function save(problemId: number) {
    setError(null);
    try {
      const current = rows.find((item) => item.problem_id === problemId);
      await updateWrongProblem(problemId, reasonType, reasonDetail, current?.related_submission_id ?? null);
      setRows(await fetchWrongProblems({ difficulty: difficulty || undefined, topic_id: topicId ? Number(topicId) : undefined }));
      setEditing(null);
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "保存错题原因失败"));
    }
  }

  async function remove(problemId: number) {
    setError(null);
    try {
      await deleteWrongProblem(problemId);
      setRows((current) => current.filter((item) => item.problem_id !== problemId));
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "移出错题失败"));
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <Link to="/problems" className="text-sm font-medium text-accent">返回题库</Link>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">错题本</h1>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">这里只显示你主动标记的错题。没有判题结果时，提交代码不会自动出现在这里。</p>
      <form className="mt-6 grid gap-3 md:grid-cols-2" onSubmit={(event) => event.preventDefault()}>
        <select value={difficulty} onChange={(event) => setDifficulty(event.target.value)} className="rounded-2xl border border-slate-200 px-4 py-2 text-sm">
          <option value="">全部难度</option>
          <option value="easy">简单</option>
          <option value="medium">中等</option>
          <option value="hard">困难</option>
          <option value="unknown">未设置</option>
        </select>
        <select value={topicId} onChange={(event) => setTopicId(event.target.value)} className="rounded-2xl border border-slate-200 px-4 py-2 text-sm">
          <option value="">全部知识点</option>
          {topics.flatMap((group) => group.topics).map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}
        </select>
      </form>
      {loading && <p className="mt-6 text-sm text-slate-500">正在读取错题…</p>}
      {error && <p className="mt-6 text-sm text-rose-700">{error}</p>}
      {!loading && rows.length === 0 && <p className="mt-6 rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-8 text-sm text-slate-600">还没有错题。</p>}
      <ul className="mt-4 space-y-3">
        {rows.map((item) => (
          <li key={item.id} className="rounded-3xl border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <Link to={`/problems/${item.problem_id}`} className="text-lg font-semibold">{item.title}</Link>
              <span className="text-sm text-slate-500">{difficultyLabels[item.difficulty] ?? item.difficulty}</span>
            </div>
            <p className="mt-2 text-sm text-slate-600">{reasonLabels[item.reason_type] ?? item.reason_type}{item.reason_detail ? ` · ${item.reason_detail}` : ""}</p>
            {item.topics.length > 0 && <p className="mt-1 text-sm text-slate-500">{item.topics.map((topic) => topic.name).join("、")}</p>}
            {item.related_submission_id && <p className="mt-1 text-sm text-slate-500">关联提交 #{item.related_submission_id}。加入错题不会改写这条提交的代码或判题结果。</p>}
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => {
                  setEditing(item.problem_id);
                  setReasonType(item.reason_type);
                  setReasonDetail(item.reason_detail);
                }}
                className="rounded-full border border-slate-200 px-3 py-1.5 text-sm"
              >
                修改原因
              </button>
              <button type="button" onClick={() => void remove(item.problem_id)} className="rounded-full border border-slate-200 px-3 py-1.5 text-sm">移出错题</button>
            </div>
            {editing === item.problem_id && (
              <form
                className="mt-3 space-y-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  void save(item.problem_id);
                }}
              >
                <select value={reasonType} onChange={(event) => setReasonType(event.target.value)} className="w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm">
                  {Object.entries(reasonLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
                <textarea value={reasonDetail} onChange={(event) => setReasonDetail(event.target.value)} rows={2} className="w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm" />
                <button type="submit" className="rounded-full bg-ink px-4 py-2 text-sm text-white">保存</button>
              </form>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
