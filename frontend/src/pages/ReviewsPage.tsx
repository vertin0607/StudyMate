import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useReviewQueue } from "../hooks/useReviewQueue.ts";
import { startReview } from "../services/reviews.ts";
import type { ReviewScheduleCard } from "../types/review.ts";
import { getErrorMessage } from "../utils/apiError.ts";
import { formatDate } from "../utils/format.ts";

const riskClass = {
  low: "bg-emerald-50 text-emerald-700",
  medium: "bg-amber-50 text-amber-800",
  high: "bg-rose-50 text-rose-700",
};

export function ReviewsPage() {
  const { queue, loading, error, reload, postpone, postponingId } = useReviewQueue();
  const [startingId, setStartingId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const navigate = useNavigate();

  async function begin(scheduleId: number) {
    setStartingId(scheduleId);
    setActionError(null);
    try {
      const paper = await startReview(scheduleId);
      navigate(`/quiz/${paper.id}`);
    } catch (reason: unknown) {
      setActionError(getErrorMessage(reason, "开始复习失败"));
    } finally {
      setStartingId(null);
    }
  }

  const sections = queue
    ? [
        { title: "已逾期", items: queue.overdue, canStart: true },
        { title: "今日待复习", items: queue.due, canStart: true },
        { title: "即将到期", items: queue.upcoming, canStart: false },
      ]
    : [];

  return (
    <div className="mx-auto max-w-3xl">
      <p className="text-sm font-medium text-accent">间隔复习</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">今天该复习什么</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        复习时间由已有检测记录计算。打开这个页面只读取数据库，不会调用 DeepSeek。点击「开始复习」才会出题。
      </p>
      {loading && <p className="mt-6 text-sm text-slate-500">正在读取复习队列…</p>}
      {(error || actionError) && (
        <div className="mt-6 text-sm text-rose-700">
          <p>{actionError ?? error}</p>
          <button type="button" onClick={reload} className="mt-3 rounded-full bg-ink px-4 py-2 text-white">
            重新读取
          </button>
        </div>
      )}
      {queue && queue.due_count + queue.overdue_count + queue.upcoming_count === 0 && (
        <p className="mt-6 rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-8 text-sm leading-6 text-slate-600">
          还没有到期的复习。完成知识检测后，系统会根据成绩安排下一次复习。未评估的知识点不会进入队列。
        </p>
      )}
      {queue && (
        <p className="mt-4 text-sm text-slate-500">
          {formatDate(queue.review_date)} · 今日完成 {queue.completed_today} 次 · 逾期 {queue.overdue_count} · 今日 {queue.due_count}
        </p>
      )}
      {sections.map((section) =>
        section.items.length === 0 ? null : (
          <section key={section.title} className="mt-6">
            <h2 className="text-lg font-semibold">{section.title}</h2>
            <ul className="mt-3 space-y-3">
              {section.items.map((item) => (
                <ReviewCard
                  key={item.id}
                  item={item}
                  canStart={section.canStart}
                  postponing={postponingId === item.id}
                  starting={startingId === item.id}
                  onPostpone={() => postpone(item.id)}
                  onStart={() => begin(item.id)}
                />
              ))}
            </ul>
          </section>
        ),
      )}
    </div>
  );
}

function ReviewCard({
  item,
  canStart,
  postponing,
  starting,
  onPostpone,
  onStart,
}: {
  item: ReviewScheduleCard;
  canStart: boolean;
  postponing: boolean;
  starting: boolean;
  onPostpone: () => void;
  onStart: () => void;
}) {
  return (
    <li className="rounded-3xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">{item.name}</h3>
          <p className="mt-1 text-sm text-slate-500">{item.stage_label}</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${riskClass[item.risk]}`}>{item.risk_label}</span>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{item.risk_reason}</p>
      <p className="mt-2 text-sm text-slate-600">{item.reason}</p>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
        <div>
          <dt className="text-slate-500">掌握度</dt>
          <dd className="mt-1 font-medium">{item.mastery_assessed ? item.mastery_level : "尚未评估"}</dd>
        </div>
        <div>
          <dt className="text-slate-500">上次检测</dt>
          <dd className="mt-1 font-medium">{item.last_score === null ? "—" : `${item.last_score} 分`}</dd>
        </div>
        <div>
          <dt className="text-slate-500">下次复习</dt>
          <dd className="mt-1 font-medium">{formatDate(item.next_review_date)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">间隔</dt>
          <dd className="mt-1 font-medium">{item.interval_days} 天</dd>
        </div>
      </dl>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link to={`/reviews/${item.id}`} className="rounded-full border border-slate-200 px-4 py-2 text-sm">
          查看档案
        </Link>
        {canStart && (
          <button type="button" onClick={onStart} disabled={starting} className="rounded-full bg-ink px-4 py-2 text-sm text-white disabled:opacity-60">
            {starting ? "正在出题…" : item.open_quiz_id ? "继续复习" : "开始复习"}
          </button>
        )}
        <button type="button" onClick={onPostpone} disabled={postponing} className="rounded-full border border-slate-200 px-4 py-2 text-sm disabled:opacity-60">
          {postponing ? "正在推迟…" : "推迟 1 天"}
        </button>
      </div>
    </li>
  );
}
