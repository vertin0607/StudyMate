import type { EditorView } from "@codemirror/view";
import { useEffect, useRef, useState } from "react";

import { fetchJudgeResult, judgeStatusLabel, requestJudge, requestJudgeAnalysis, waitForJudge, type JudgeResult } from "../services/judge.ts";
import { addWrongProblem } from "../services/practice.ts";
import { createSubmission, fetchDraft, fetchSubmission, fetchSubmissions, saveDraft, type SubmissionDetail, type SubmissionSummary } from "../services/submissions.ts";
import { formatServerTime } from "../utils/format.ts";
import { CPP_TEMPLATE, DraftSaveQueue, canSubmitCode, initialEditorCode, type SavePhase } from "../utils/draftSave.ts";
import { getErrorMessage } from "../utils/apiError.ts";
import { replaceEditorCode, selectEditorCode } from "../utils/cppEditor.ts";
import { CppEditor } from "./CppEditor.tsx";

const SAVE_WAIT_MS = 800;

const phaseLabel: Record<SavePhase, string> = {
  idle: "已保存",
  saving: "正在保存",
  saved: "已保存",
  failed: "保存失败",
};

export function ProblemWorkspace({ problemId }: { problemId: number }) {
  const [readyCode, setReadyCode] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [phase, setPhase] = useState<SavePhase>("idle");
  const [usingTemplate, setUsingTemplate] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const [history, setHistory] = useState<SubmissionSummary[]>([]);
  const [opened, setOpened] = useState<SubmissionDetail | null>(null);
  const [openingId, setOpeningId] = useState<number | null>(null);
  const [judge, setJudge] = useState<JudgeResult | null>(null);
  const [showCases, setShowCases] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const codeRef = useRef("");
  const touchedRef = useRef(false);
  const viewRef = useRef<EditorView | null>(null);
  const queueRef = useRef<DraftSaveQueue | null>(null);
  const timerRef = useRef<number | null>(null);
  const requestId = useRef(0);
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
    };
  }, []);

  if (queueRef.current === null) {
    queueRef.current = new DraftSaveQueue(async (source) => {
      await saveDraft(problemId, source);
    });
  }

  useEffect(() => {
    const id = requestId.current + 1;
    requestId.current = id;
    Promise.all([fetchDraft(problemId), fetchSubmissions(problemId)])
      .then(([draft, submissions]) => {
        if (requestId.current !== id) {
          return;
        }
        const code = initialEditorCode(draft);
        codeRef.current = code;
        setUsingTemplate(!draft.saved);
        if (draft.saved) {
          queueRef.current?.markSaved(draft.source_code);
          setPhase("saved");
        }
        setHistory(submissions);
        setReadyCode(code);
        setLoadError(null);
      })
      .catch((reason: unknown) => {
        if (requestId.current === id) {
          setLoadError(getErrorMessage(reason, "读取代码失败"));
        }
      });
  }, [problemId]);

  useEffect(() => {
    const queue = queueRef.current;
    return () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
      }
      if (touchedRef.current && queue?.hasUnsaved(codeRef.current)) {
        void queue.flush();
      }
    };
  }, [problemId]);

  useEffect(() => {
    function leave() {
      const queue = queueRef.current;
      if (!touchedRef.current || !queue?.hasUnsaved(codeRef.current)) {
        return;
      }
      const base = import.meta.env.VITE_API_BASE_URL ?? "";
      void fetch(`${base}/api/problems/${problemId}/draft`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_code: codeRef.current, language: "cpp" }),
        keepalive: true,
      });
    }
    window.addEventListener("beforeunload", leave);
    return () => window.removeEventListener("beforeunload", leave);
  }, [problemId]);

  function syncPhase() {
    const queue = queueRef.current;
    if (queue) {
      setPhase(queue.phase);
    }
  }

  function scheduleSave() {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
    }
    timerRef.current = window.setTimeout(() => {
      void queueRef.current?.flush().then(syncPhase);
    }, SAVE_WAIT_MS);
  }

  function onEdit(code: string) {
    touchedRef.current = true;
    setUsingTemplate(false);
    codeRef.current = code;
    queueRef.current?.note(code);
    setPhase("saving");
    scheduleSave();
  }

  async function saveNow() {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
    }
    touchedRef.current = true;
    queueRef.current?.note(codeRef.current);
    setPhase("saving");
    await queueRef.current?.flush();
    syncPhase();
  }

  function applyCode(code: string) {
    const view = viewRef.current;
    if (!view) {
      return;
    }
    replaceEditorCode(view, code);
  }

  async function submit() {
    if (!canSubmitCode(codeRef.current)) {
      setActionError("代码不能为空");
      setConfirmSubmit(false);
      return;
    }
    setSubmitting(true);
    setActionError(null);
    try {
      const created = await createSubmission(problemId, codeRef.current);
      setOpened(created);
      setJudge(null);
      setShowCases(false);
      setNotice("正在判题");
      setHistory(await fetchSubmissions(problemId));
      const started = await requestJudge(created.id);
      let result = started;
      if (started.status === "judging") {
        const finished = await waitForJudge(created.id, () => aliveRef.current);
        if (finished === null) {
          return;
        }
        result = finished;
      }
      if (!aliveRef.current) {
        return;
      }
      setJudge(result);
      setNotice(judgeStatusLabel(result.status));
      setHistory(await fetchSubmissions(problemId));
      setOpened(await fetchSubmission(created.id));
    } catch (reason: unknown) {
      setActionError(getErrorMessage(reason, "提交失败，编辑器里的代码还在"));
    } finally {
      setSubmitting(false);
      setConfirmSubmit(false);
    }
  }

  async function openSubmission(submissionId: number) {
    setOpeningId(submissionId);
    setActionError(null);
    try {
      const detail = await fetchSubmission(submissionId);
      setOpened(detail);
      if (detail.status === "unjudged") {
        setJudge(null);
      } else {
        setJudge(await fetchJudgeResult(submissionId));
      }
      setShowCases(false);
    } catch (reason: unknown) {
      setActionError(getErrorMessage(reason, "读取提交记录失败"));
    } finally {
      setOpeningId(null);
    }
  }

  async function analyze() {
    if (!judge) {
      return;
    }
    setAnalyzing(true);
    setActionError(null);
    try {
      setJudge(await requestJudgeAnalysis(judge.submission_id));
    } catch (reason: unknown) {
      setActionError(getErrorMessage(reason, "分析失败，判题结果没有改变"));
    } finally {
      setAnalyzing(false);
    }
  }

  async function markWrong() {
    if (!judge) {
      return;
    }
    setActionError(null);
    try {
      await addWrongProblem(problemId, "implementation", judgeStatusLabel(judge.status), judge.submission_id);
      setNotice("已加入错题。代码和判题结果都没有被改写。");
    } catch (reason: unknown) {
      setActionError(getErrorMessage(reason, "加入错题失败"));
    }
  }

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(codeRef.current);
      setNotice("已复制当前代码");
    } catch {
      setActionError("复制失败，可以在编辑器里手动复制");
    }
  }

  if (loadError && readyCode === null) {
    return <p className="text-sm text-rose-700">{loadError}</p>;
  }
  if (readyCode === null) {
    return <p className="text-sm text-slate-500">正在读取代码草稿…</p>;
  }

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">开始做题</h2>
          <p className="mt-1 text-sm text-slate-500">C++ 草稿会自动保存。提交后在隔离环境里编译运行，不会改掉编辑器或以前的提交。</p>
        </div>
        <p className={`text-sm ${phase === "failed" ? "text-rose-700" : "text-slate-500"}`}>
          {usingTemplate ? "尚未保存" : phaseLabel[phase]}
        </p>
      </div>
      {actionError && <p className="mt-3 text-sm text-rose-700">{actionError}</p>}
      {notice && <p className="mt-3 text-sm text-accent">{notice}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" onClick={() => void copyCode()} className="rounded-full border border-slate-200 px-3 py-1.5 text-sm">复制</button>
        <button type="button" onClick={() => viewRef.current && selectEditorCode(viewRef.current)} className="rounded-full border border-slate-200 px-3 py-1.5 text-sm">全选</button>
        <button type="button" onClick={() => applyCode("")} className="rounded-full border border-slate-200 px-3 py-1.5 text-sm">清空</button>
        <button type="button" onClick={() => applyCode(CPP_TEMPLATE)} className="rounded-full border border-slate-200 px-3 py-1.5 text-sm">恢复默认模板</button>
        <button type="button" onClick={() => void saveNow()} className="rounded-full border border-slate-200 px-3 py-1.5 text-sm">保存草稿</button>
        <button
          type="button"
          onClick={() => {
            if (!canSubmitCode(codeRef.current)) {
              setActionError("代码不能为空");
              return;
            }
            setActionError(null);
            setConfirmSubmit(true);
          }}
          disabled={submitting}
          className="rounded-full bg-ink px-3 py-1.5 text-sm text-white disabled:opacity-60"
        >
          {submitting ? "正在提交…" : "提交代码"}
        </button>
      </div>
      <div className="mt-3">
        <CppEditor
          initialCode={readyCode}
          onChange={onEdit}
          onReady={(view) => {
            viewRef.current = view;
          }}
        />
      </div>
      <div className="mt-6">
        <h3 className="text-base font-semibold">提交记录</h3>
        <p className="mt-1 text-sm text-slate-500">历史代码只读。修改上面的草稿不会改变这些记录。</p>
        {history.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">还没有提交。</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {history.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => void openSubmission(item.id)}
                  className="flex w-full flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-200 px-3 py-2 text-left text-sm hover:bg-slate-50"
                >
                  <span>#{item.id} · C++ · {item.code_length} 字符</span>
                  <span className="text-slate-500">{formatServerTime(item.submitted_at)} · {judgeStatusLabel(item.status)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {openingId !== null && <p className="mt-3 text-sm text-slate-500">正在读取提交 #{openingId}…</p>}
        {opened && (
          <div className="mt-3">
            <p className="text-sm text-slate-600">提交 #{opened.id} 的代码，只读。{judgeStatusLabel(opened.status)}</p>
            <pre className="io-block mt-2 max-h-72 overflow-auto">{opened.source_code}</pre>
          </div>
        )}
        {judge && <JudgePanel problemId={problemId} result={judge} showCases={showCases} analyzing={analyzing} onToggle={() => setShowCases((value) => !value)} onAnalyze={() => void analyze()} onWrong={() => void markWrong()} />}
      </div>
      {confirmSubmit && (
        <div className="fixed inset-0 z-20 flex items-end justify-center bg-ink/40 p-4 sm:items-center">
          <div role="dialog" aria-modal="true" className="w-full max-w-md rounded-3xl bg-white p-6 shadow-xl">
            <h3 className="text-xl font-semibold">提交当前代码</h3>
            <p className="mt-3 text-sm leading-6 text-slate-600">会新增一条提交记录，并在隔离环境中编译运行。编辑器里的草稿会保留，之前的提交也不会被覆盖。是否正确由测试数据决定。</p>
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button type="button" onClick={() => setConfirmSubmit(false)} disabled={submitting} className="rounded-full border border-slate-200 px-4 py-2 text-sm">取消</button>
              <button type="button" onClick={() => void submit()} disabled={submitting} className="rounded-full bg-ink px-4 py-2 text-sm text-white disabled:opacity-60">
                {submitting ? "正在提交…" : "确认提交"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

const explainable = new Set(["wrong_answer", "compile_error", "time_limit_exceeded", "runtime_error"]);

function JudgePanel({
  problemId,
  result,
  showCases,
  analyzing,
  onToggle,
  onAnalyze,
  onWrong,
}: {
  problemId: number;
  result: JudgeResult;
  showCases: boolean;
  analyzing: boolean;
  onToggle: () => void;
  onAnalyze: () => void;
  onWrong: () => void;
}) {
  return (
    <div className="mt-4 rounded-2xl border border-slate-200 p-4">
      <p className="text-base font-semibold">{judgeStatusLabel(result.status)}</p>
      <p className="mt-2 text-sm text-slate-600">通过 {result.passed_cases} / {result.total_cases} 组测试 · 执行时间 {result.execution_time_ms} ms · 内存 {result.memory_used_kb > 0 ? `${result.memory_used_kb} KB` : "本次没有取得内存数据"}</p>
      {result.error_message && <p className="mt-2 text-sm text-slate-700">{result.error_message}</p>}
      {result.compile_output && <pre className="io-block mt-2 max-h-48 overflow-auto">{result.compile_output}</pre>}
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" onClick={onToggle} className="rounded-full border border-slate-200 px-3 py-1.5 text-sm">{showCases ? "收起详细信息" : "查看详细信息"}</button>
        {explainable.has(result.status) && (
          <button type="button" onClick={onAnalyze} disabled={analyzing} className="rounded-full border border-slate-200 px-3 py-1.5 text-sm disabled:opacity-60">
            {analyzing ? "正在分析…" : "AI 分析错误"}
          </button>
        )}
        {explainable.has(result.status) && (
          <button type="button" onClick={onWrong} className="rounded-full border border-slate-200 px-3 py-1.5 text-sm">加入错题</button>
        )}
      </div>
      {showCases && (
        <ul className="mt-3 space-y-3">
          {(result.cases ?? []).map((item, index) => (
            <li key={item.id} className="rounded-2xl bg-slate-50 p-3 text-sm">
              <p>第 {index + 1} 组 · {judgeStatusLabel(item.status)} · {item.execution_time_ms} ms</p>
              {item.error_message && <p className="mt-1 text-slate-600">{item.error_message}</p>}
              <p className="mt-2 text-slate-500">预期输出</p>
              <pre className="io-block mt-1">{item.expected_output || "（空）"}</pre>
              <p className="mt-2 text-slate-500">实际输出</p>
              <pre className="io-block mt-1">{item.actual_output || "（空）"}</pre>
            </li>
          ))}
          {(result.cases ?? []).length === 0 && <li className="text-sm text-slate-500">没有可展示的测试结果。</li>}
        </ul>
      )}
      {result.ai_analysis && (
        <div className="mt-4 space-y-2 text-sm leading-6 text-slate-700">
          <p><span className="font-medium">可能原因：</span>{result.ai_analysis.likely_cause}</p>
          <p><span className="font-medium">位置：</span>{result.ai_analysis.location}</p>
          <p><span className="font-medium">解释：</span>{result.ai_analysis.explanation}</p>
          <p><span className="font-medium">修改方向：</span>{result.ai_analysis.direction}</p>
          <pre className="io-block">{result.ai_analysis.patch_example}</pre>
          <p className="text-slate-500">{result.ai_analysis.confidence_note}</p>
          <p className="text-xs text-slate-400">题目 #{problemId} 的这段分析不会写回编辑器。</p>
        </div>
      )}
      {result.ai_analysis_error && <p className="mt-3 text-sm text-rose-700">{result.ai_analysis_error}</p>}
    </div>
  );
}
