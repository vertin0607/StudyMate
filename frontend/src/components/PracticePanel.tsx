import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  addWrongProblem,
  completePractice,
  deleteWrongProblem,
  fetchLearningStatus,
  fetchPracticeHistory,
  fetchWrongProblems,
  startPractice,
  updateLearningStatus,
  updateWrongProblem,
} from "../services/practice.ts";
import { fetchSubmissions, type SubmissionSummary } from "../services/submissions.ts";
import { judgeStatusLabel } from "../services/judge.ts";
import { completionLabels, learningStatusLabels, reasonLabels, type LearningStatus, type PracticeRecord, type WrongProblem } from "../types/practice.ts";
import { getErrorMessage } from "../utils/apiError.ts";
import { formatServerTime } from "../utils/format.ts";

const manualStatuses = ["todo", "attempting", "self_completed"] as const;

export function PracticePanel({ problemId }: { problemId: number }) {
  const [status, setStatus] = useState<LearningStatus | null>(null);
  const [records, setRecords] = useState<PracticeRecord[]>([]);
  const [wrong, setWrong] = useState<WrongProblem | null>(null);
  const [submissions, setSubmissions] = useState<SubmissionSummary[]>([]);
  const [completionType, setCompletionType] = useState("independent");
  const [note, setNote] = useState("");
  const [reasonType, setReasonType] = useState("algorithm");
  const [reasonDetail, setReasonDetail] = useState("");
  const [submissionId, setSubmissionId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const requestId = useRef(0);

  useEffect(() => {
    const id = requestId.current + 1;
    requestId.current = id;
    Promise.all([fetchLearningStatus(problemId), fetchPracticeHistory(problemId), fetchWrongProblems(), fetchSubmissions(problemId)])
      .then(([nextStatus, history, wrongs, codes]) => {
        if (requestId.current !== id) {
          return;
        }
        const current = wrongs.find((item) => item.problem_id === problemId) ?? null;
        setStatus(nextStatus);
        setRecords(history);
        setWrong(current);
        setSubmissions(codes);
        if (current) {
          setReasonType(current.reason_type);
          setReasonDetail(current.reason_detail);
          setSubmissionId(current.related_submission_id ? String(current.related_submission_id) : "");
        }
        setError(null);
      })
      .catch((reason: unknown) => {
        if (requestId.current === id) {
          setError(getErrorMessage(reason, "读取练习记录失败"));
        }
      });
  }, [problemId]);

  const openRecord = records.find((item) => item.open) ?? null;

  async function refresh() {
    const [nextStatus, history, wrongs] = await Promise.all([
      fetchLearningStatus(problemId),
      fetchPracticeHistory(problemId),
      fetchWrongProblems(),
    ]);
    setStatus(nextStatus);
    setRecords(history);
    setWrong(wrongs.find((item) => item.problem_id === problemId) ?? null);
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await refresh();
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "保存练习记录失败"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">练习记录</h2>
          <p className="mt-1 text-sm text-slate-500">这里只记录你怎么练。不会判断代码对错，用户自评完成也不是系统判题通过。</p>
        </div>
        <p className="text-sm text-slate-600">{status ? learningStatusLabels[status.status] : "正在读取"}</p>
      </div>
      {error && <p className="mt-3 text-sm text-rose-700">{error}</p>}
      {status?.locked ? (
        <p className="mt-3 text-sm text-slate-600">这道题已有系统判题结果，手动状态不能覆盖它。</p>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          {manualStatuses.map((item) => (
            <button key={item} type="button" disabled={busy} onClick={() => void run(() => updateLearningStatus(problemId, item).then(() => undefined))} className="rounded-full border border-slate-200 px-3 py-1.5 text-sm">
              {learningStatusLabels[item]}
            </button>
          ))}
        </div>
      )}
      <div className="mt-4">
        {openRecord ? (
          <form
            className="space-y-2"
            onSubmit={(event) => {
              event.preventDefault();
              void run(async () => {
                await completePractice(problemId, openRecord.id, completionType, note);
                setNote("");
              });
            }}
          >
            <p className="text-sm text-slate-600">本次练习从 {formatServerTime(openRecord.started_at)} 开始，还没有结束。</p>
            <select value={completionType} onChange={(event) => setCompletionType(event.target.value)} className="w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm">
              {Object.entries(completionLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={3} placeholder="这次练习的笔记" className="w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm" />
            <button type="submit" disabled={busy} className="rounded-full bg-ink px-4 py-2 text-sm text-white disabled:opacity-60">结束本次练习</button>
          </form>
        ) : (
          <button type="button" disabled={busy} onClick={() => void run(() => startPractice(problemId).then(() => undefined))} className="rounded-full bg-ink px-4 py-2 text-sm text-white disabled:opacity-60">
            开始练习
          </button>
        )}
      </div>
      <div className="mt-5">
        <h3 className="text-base font-semibold">历史练习</h3>
        {records.length === 0 ? <p className="mt-2 text-sm text-slate-500">还没有练习记录。</p> : (
          <ul className="mt-2 space-y-2">
            {records.map((item) => (
              <li key={item.id} className="rounded-2xl border border-slate-200 px-3 py-2 text-sm">
                <p>{item.open ? "进行中" : completionLabels[item.completion_type] ?? item.completion_type} · {formatServerTime(item.started_at)}</p>
                {item.note && <p className="mt-1 text-slate-600">{item.note}</p>}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="mt-5">
        <h3 className="text-base font-semibold">错题标记</h3>
        <p className="mt-1 text-sm text-slate-500">只有你主动标记才会进入错题。尚未判题的提交不会自动变成错题。</p>
        <form
          className="mt-2 space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            const selected = submissionId ? Number(submissionId) : null;
            void run(async () => {
              if (wrong) {
                await updateWrongProblem(problemId, reasonType, reasonDetail, selected);
              } else {
                await addWrongProblem(problemId, reasonType, reasonDetail, selected);
              }
            });
          }}
        >
          <select value={reasonType} onChange={(event) => setReasonType(event.target.value)} className="w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm">
            {Object.entries(reasonLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <textarea value={reasonDetail} onChange={(event) => setReasonDetail(event.target.value)} rows={2} placeholder="错误原因" className="w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm" />
          <select value={submissionId} onChange={(event) => setSubmissionId(event.target.value)} className="w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm">
            <option value="">不关联提交记录</option>
            {submissions.map((item) => <option key={item.id} value={item.id}>提交 #{item.id} · {judgeStatusLabel(item.status)}</option>)}
          </select>
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={busy} className="rounded-full border border-slate-200 px-4 py-2 text-sm">{wrong ? "保存错题原因" : "加入错题"}</button>
            {wrong && <button type="button" disabled={busy} onClick={() => void run(() => deleteWrongProblem(problemId))} className="rounded-full border border-slate-200 px-4 py-2 text-sm">移出错题</button>}
            <Link to="/problems/wrong" className="rounded-full border border-slate-200 px-4 py-2 text-sm">打开错题本</Link>
          </div>
        </form>
      </div>
    </section>
  );
}
