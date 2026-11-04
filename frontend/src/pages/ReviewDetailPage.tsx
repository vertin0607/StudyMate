import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { fetchReview, postponeReview, startReview } from "../services/reviews.ts";
import type { ReviewDetail } from "../types/review.ts";
import { getErrorMessage } from "../utils/apiError.ts";
import { formatDate, formatServerTime } from "../utils/format.ts";

export function ReviewDetailPage() {
  const params = useParams();
  const scheduleId = Number(params.scheduleId);
  const [detail, setDetail] = useState<ReviewDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [postponing, setPostponing] = useState(false);
  const requestId = useRef(0);
  const navigate = useNavigate();

  useEffect(() => {
    if (!Number.isInteger(scheduleId) || scheduleId < 1) {
      return;
    }
    const id = requestId.current + 1;
    requestId.current = id;
    fetchReview(scheduleId)
      .then((data) => {
        if (requestId.current !== id) {
          return;
        }
        setDetail(data);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (requestId.current !== id) {
          return;
        }
        setError(getErrorMessage(reason, "读取复习详情失败"));
      })
      .finally(() => {
        if (requestId.current === id) {
          setLoading(false);
        }
      });
  }, [scheduleId]);

  async function begin() {
    setStarting(true);
    setError(null);
    try {
      const paper = await startReview(scheduleId);
      navigate(`/quiz/${paper.id}`);
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "开始复习失败"));
    } finally {
      setStarting(false);
    }
  }

  async function postpone() {
    setPostponing(true);
    setError(null);
    try {
      const data = await postponeReview(scheduleId, 1);
      setDetail(data);
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "推迟复习失败"));
    } finally {
      setPostponing(false);
    }
  }

  const memory = detail?.memory;
  const canStart = detail ? detail.queue === "due" || detail.queue === "overdue" : false;

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/reviews" className="text-sm font-medium text-accent">
        返回复习列表
      </Link>
      {loading && <p className="mt-6 text-sm text-slate-500">正在读取复习档案…</p>}
      {error && <p className="mt-6 text-sm text-rose-700">{error}</p>}
      {detail && (
        <>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight">{detail.name}</h1>
          <p className="mt-3 text-sm leading-6 text-slate-600">{detail.risk_reason}</p>
          <p className="mt-2 text-sm text-slate-600">
            {detail.risk_label} · {detail.stage_label} · 下次复习 {formatDate(detail.next_review_date)}
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            {canStart && (
              <button type="button" onClick={begin} disabled={starting} className="rounded-full bg-ink px-4 py-2 text-sm text-white disabled:opacity-60">
                {starting ? "正在出题…" : "开始复习"}
              </button>
            )}
            <button type="button" onClick={postpone} disabled={postponing} className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm disabled:opacity-60">
              {postponing ? "正在推迟…" : "推迟 1 天"}
            </button>
          </div>
          {memory && (
            <dl className="mt-6 grid grid-cols-2 gap-3 text-sm md:grid-cols-3">
              {[
                ["首次学习", memory.first_seen_at ? formatServerTime(memory.first_seen_at) : "—"],
                ["最近学习", memory.last_studied_at ? formatServerTime(memory.last_studied_at) : "—"],
                ["最近检测", memory.last_quiz_at ? formatServerTime(memory.last_quiz_at) : "—"],
                ["学习次数", String(memory.study_count)],
                ["检测次数", String(memory.quiz_count)],
                ["平均成绩", memory.average_score === null ? "—" : String(memory.average_score)],
                ["最近成绩", memory.latest_score === null ? "—" : String(memory.latest_score)],
                ["掌握度", memory.mastery_assessed ? `${memory.mastery_level} · ${memory.status_label}` : "尚未评估"],
                ["连续达标", String(memory.correct_streak)],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl bg-white px-4 py-3">
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="mt-1 font-medium">{value}</dd>
                </div>
              ))}
            </dl>
          )}
          {memory && memory.weak_points.length > 0 && (
            <section className="mt-4 rounded-3xl border border-slate-200 bg-white p-5">
              <h2 className="text-lg font-semibold">历史薄弱点</h2>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                {memory.weak_points.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          )}
          {memory && memory.weak_points.length === 0 && (
            <p className="mt-4 text-sm text-slate-500">还没有记录到反复出错的地方。</p>
          )}
        </>
      )}
    </div>
  );
}
