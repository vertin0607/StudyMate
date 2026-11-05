import { useEffect, useRef, useState } from "react";

import { TutorMarkdown } from "./TutorMarkdown.tsx";
import { fetchKnowledgeExplain, followupKnowledgeExplain, startKnowledgeExplain } from "../services/reviews.ts";
import type { KnowledgeExplainSession } from "../types/explain.ts";
import { getErrorMessage } from "../utils/apiError.ts";

export function KnowledgeExplainPanel({ scheduleId, autoStart = false }: { scheduleId: number; autoStart?: boolean }) {
  const [open, setOpen] = useState(autoStart);
  const [session, setSession] = useState<KnowledgeExplainSession | null>(null);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (!open || autoStart) {
      return;
    }
    fetchKnowledgeExplain(scheduleId)
      .then((data) => {
        setSession(data);
        setError(null);
      })
      .catch((reason: unknown) => {
        setError(getErrorMessage(reason, "读取讲解失败"));
      });
  }, [open, scheduleId, autoStart]);

  useEffect(() => {
    if (!autoStart || started.current) {
      return;
    }
    started.current = true;
    setOpen(true);
    setLoading(true);
    setError(null);
    startKnowledgeExplain(scheduleId)
      .then((data) => setSession(data))
      .catch((reason: unknown) => setError(getErrorMessage(reason, "生成知识点讲解失败")))
      .finally(() => setLoading(false));
  }, [autoStart, scheduleId]);

  async function generate() {
    setOpen(true);
    setLoading(true);
    setError(null);
    try {
      const data = await startKnowledgeExplain(scheduleId);
      setSession(data);
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "生成知识点讲解失败"));
    } finally {
      setLoading(false);
    }
  }

  async function followup() {
    const content = draft.trim();
    if (!content) {
      return;
    }
    setSending(true);
    setError(null);
    try {
      const data = await followupKnowledgeExplain(scheduleId, content);
      setSession(data);
      setDraft("");
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "追问失败"));
    } finally {
      setSending(false);
    }
  }

  const messages = session?.messages ?? [];

  return (
    <section className="mt-6 rounded-3xl border border-line bg-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">AI 知识讲解</h2>
          <p className="mt-1 text-sm text-muted">讲解不会标记复习完成，也不会改写掌握度。</p>
        </div>
        <button
          type="button"
          onClick={() => {
            if (!open) {
              void generate();
              return;
            }
            setOpen(false);
          }}
          disabled={loading}
          className="rounded-full bg-accent px-4 py-2 text-sm text-on-accent disabled:opacity-60"
        >
          {loading ? "正在讲解…" : open ? "收起讲解" : "AI 讲解"}
        </button>
      </div>
      {open && error && (
        <div className="mt-4 text-sm text-rose-700">
          <p>{error}</p>
          <button type="button" onClick={() => void generate()} className="mt-3 rounded-full bg-accent px-4 py-2 text-on-accent">
            重试
          </button>
        </div>
      )}
      {open && messages.length > 0 && (
        <ul className="mt-4 space-y-3">
          {messages.map((item) => (
            <li key={item.id} className={`rounded-2xl px-4 py-3 ${item.role === "user" ? "border border-line bg-mist" : "bg-soft"}`}>
              <p className="text-xs text-muted">{item.role === "user" ? "你的追问" : "讲解"}</p>
              {item.role === "user" ? <p className="mt-1 text-sm leading-6">{item.content}</p> : <TutorMarkdown content={item.content} />}
            </li>
          ))}
        </ul>
      )}
      {open && messages.length > 0 && (
        <form
          className="mt-4"
          onSubmit={(event) => {
            event.preventDefault();
            void followup();
          }}
        >
          <label className="block text-sm text-muted" htmlFor={`explain-followup-${scheduleId}`}>
            继续追问
          </label>
          <textarea
            id={`explain-followup-${scheduleId}`}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            rows={3}
            placeholder="例如：能不能举个更简单的例子？"
            className="mt-2 w-full rounded-2xl border border-line bg-mist px-4 py-3 text-sm"
          />
          <button type="submit" disabled={sending || !draft.trim()} className="mt-3 rounded-full bg-accent px-4 py-2 text-sm text-on-accent disabled:opacity-60">
            {sending ? "正在回答…" : "发送追问"}
          </button>
        </form>
      )}
    </section>
  );
}
