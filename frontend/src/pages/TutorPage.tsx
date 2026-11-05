import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ConfirmDialog } from "../components/ConfirmDialog.tsx";
import { TutorMarkdown } from "../components/TutorMarkdown.tsx";
import { fetchGoals } from "../services/goals.ts";
import { createTutorSession, deleteTutorSession, fetchTutorSession, fetchTutorSessions, sendTutorMessage } from "../services/tutor.ts";
import type { Goal } from "../types/goal.ts";
import type { TutorMessage, TutorSessionDetail, TutorSessionSummary } from "../types/tutor.ts";
import { getErrorMessage } from "../utils/apiError.ts";

export function TutorPage() {
  const params = useParams();
  const sessionId = params.sessionId ? Number(params.sessionId) : null;
  const navigate = useNavigate();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [sessions, setSessions] = useState<TutorSessionSummary[]>([]);
  const [detail, setDetail] = useState<TutorSessionDetail | null>(null);
  const [goalId, setGoalId] = useState<number | "">("");
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const listRequest = useRef(0);
  const detailRequest = useRef(0);

  const loadLists = useCallback((id: number) => {
    Promise.all([fetchGoals(), fetchTutorSessions()])
      .then(([goalRows, sessionRows]) => {
        if (listRequest.current !== id) {
          return;
        }
        setGoals(goalRows);
        setSessions(sessionRows);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (listRequest.current !== id) {
          return;
        }
        setError(getErrorMessage(reason, "读取教学会话失败"));
      })
      .finally(() => {
        if (listRequest.current === id) {
          setLoading(false);
        }
      });
  }, []);

  useEffect(() => {
    const id = listRequest.current + 1;
    listRequest.current = id;
    loadLists(id);
  }, [loadLists]);

  useEffect(() => {
    if (!sessionId || !Number.isInteger(sessionId)) {
      return;
    }
    const id = detailRequest.current + 1;
    detailRequest.current = id;
    fetchTutorSession(sessionId)
      .then((data) => {
        if (detailRequest.current !== id) {
          return;
        }
        setDetail(data);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (detailRequest.current !== id) {
          return;
        }
        setDetail(null);
        setError(getErrorMessage(reason, "读取对话失败"));
      });
  }, [sessionId]);

  async function startSession() {
    setCreating(true);
    setError(null);
    try {
      const created = await createTutorSession(goalId === "" ? null : goalId);
      setSessions((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      navigate(`/tutor/${created.id}`);
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "创建对话失败"));
    } finally {
      setCreating(false);
    }
  }

  async function send() {
    if (!sessionId || !draft.trim() || sending) {
      return;
    }
    const content = draft.trim();
    setSending(true);
    setError(null);
    try {
      const reply = await sendTutorMessage(sessionId, content);
      setDraft("");
      setDetail((current) =>
        current
          ? { ...current, title: current.title === "新的对话" ? content.slice(0, 24) : current.title, messages: [...current.messages, reply.user_message, reply.assistant_message] }
          : current,
      );
      setSessions((current) =>
        current.map((item) =>
          item.id === sessionId ? { ...item, title: item.title === "新的对话" ? content.slice(0, 24) : item.title, message_count: item.message_count + 2 } : item,
        ),
      );
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "发送失败，这次回复没有保存"));
    } finally {
      setSending(false);
    }
  }

  async function removeSession() {
    if (!sessionId) {
      return;
    }
    setDeleting(true);
    try {
      await deleteTutorSession(sessionId);
      setSessions((current) => current.filter((item) => item.id !== sessionId));
      setDetail(null);
      setConfirmDelete(false);
      navigate("/tutor");
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "删除对话失败"));
    } finally {
      setDeleting(false);
    }
  }

  const points = detail?.points ?? [];

  return (
    <div className="mx-auto grid max-w-6xl gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside className="space-y-4">
        <section className="rounded-3xl border border-line bg-surface p-4">
          <h1 className="text-lg font-semibold">AI 导师</h1>
          <p className="mt-2 text-sm leading-6 text-muted">打开页面只读取已有目标和对话。发送消息时才会调用 DeepSeek。</p>
          <label className="mt-4 block text-sm text-muted" htmlFor="tutor-goal">
            关联学习目标
          </label>
          <select
            id="tutor-goal"
            value={goalId}
            onChange={(event) => setGoalId(event.target.value ? Number(event.target.value) : "")}
            className="mt-2 w-full rounded-2xl border border-line px-3 py-2 text-sm"
          >
            <option value="">不关联目标</option>
            {goals.map((goal) => (
              <option key={goal.id} value={goal.id}>
                {goal.title}
              </option>
            ))}
          </select>
          <button type="button" onClick={startSession} disabled={creating} className="mt-3 w-full rounded-full bg-accent px-4 py-2 text-sm text-on-accent disabled:opacity-60">
            {creating ? "正在创建…" : "开始这次对话"}
          </button>
        </section>
        <section className="rounded-3xl border border-line bg-surface p-4">
          <h2 className="text-sm font-semibold">历史会话</h2>
          {loading && <p className="mt-3 text-sm text-muted">正在读取…</p>}
          {!loading && sessions.length === 0 && <p className="mt-3 text-sm text-muted">还没有对话。</p>}
          <ul className="mt-3 space-y-2">
            {sessions.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => navigate(`/tutor/${item.id}`)}
                  className={`w-full rounded-2xl px-3 py-2 text-left text-sm ${item.id === sessionId ? "bg-accent-soft" : "bg-mist"}`}
                >
                  <span className="block font-medium">{item.title}</span>
                  <span className="mt-1 block text-muted">{item.goal_title ?? "未关联目标"}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
        <section className="rounded-3xl border border-line bg-surface p-4">
          <h2 className="text-sm font-semibold">相关知识点</h2>
          {points.length === 0 && <p className="mt-3 text-sm text-muted">选择一个已有目标的对话后，这里显示掌握度。</p>}
          <ul className="mt-3 space-y-3">
            {points.map((point) => (
              <li key={point.id} className="text-sm">
                <p className="font-medium">{point.name}</p>
                <p className="mt-1 text-muted">
                  {point.mastery_assessed ? `${point.status_label} · ${point.mastery_level}` : "尚未评估"}
                  {point.latest_score === null ? "" : ` · 最近 ${point.latest_score} 分`}
                </p>
              </li>
            ))}
          </ul>
        </section>
      </aside>
      <section className="flex min-h-[70vh] flex-col rounded-3xl border border-line bg-surface p-4 md:p-6">
        {error && <p className="mb-4 rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
        {!sessionId && <p className="text-sm leading-6 text-muted">从左侧开始一次对话。之后的问题会留在同一次会话里，刷新后可以继续。</p>}
        {sessionId && detail && (
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold">{detail.title}</h2>
              <p className="mt-1 text-sm text-muted">{detail.goal_title ?? "这次对话没有关联学习目标"}</p>
            </div>
            <button type="button" onClick={() => setConfirmDelete(true)} className="rounded-full border border-line px-3 py-1 text-sm">
              删除
            </button>
          </div>
        )}
        <div className="mt-4 flex-1 space-y-4">
          {detail?.messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {sending && <p className="text-sm text-muted">正在组织讲解…</p>}
        </div>
        {sessionId && (
          <form
            className="mt-4 flex flex-col gap-2 sm:flex-row"
            onSubmit={(event) => {
              event.preventDefault();
              void send();
            }}
          >
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              rows={3}
              placeholder="问一个现在想弄清的问题"
              className="min-w-0 flex-1 rounded-2xl border border-line px-4 py-3 text-sm"
            />
            <button type="submit" disabled={sending || !draft.trim()} className="rounded-full bg-accent px-5 py-2 text-sm text-on-accent disabled:opacity-60">
              {sending ? "发送中…" : "发送"}
            </button>
          </form>
        )}
      </section>
      {confirmDelete && (
        <ConfirmDialog
          title="删除这次对话"
          description="对话记录会从数据库中删除。学习目标和掌握度不会改变。"
          confirmLabel={deleting ? "正在删除…" : "删除"}
          busy={deleting}
          onCancel={() => setConfirmDelete(false)}
          onConfirm={() => void removeSession()}
        />
      )}
    </div>
  );
}

function MessageBubble({ message }: { message: TutorMessage }) {
  const mine = message.role === "user";
  return (
    <article className={`max-w-[95%] rounded-3xl px-4 py-3 ${mine ? "ml-auto bg-accent text-on-accent" : "bg-mist"}`}>
      <p className={`text-xs ${mine ? "text-on-accent/70" : "text-muted"}`}>{mine ? "我" : "导师"}</p>
      {mine ? <p className="mt-2 whitespace-pre-wrap text-sm leading-7">{message.content}</p> : <TutorMarkdown content={message.content} />}
    </article>
  );
}
