import { Link, useOutletContext } from "react-router-dom";

import { HealthCard } from "../components/HealthCard.tsx";
import type { HealthState } from "../hooks/useHealth.ts";
import { useGoals } from "../hooks/useGoals.ts";
import { usePlanDashboard } from "../hooks/usePlans.ts";
import { useAnalytics } from "../hooks/useAnalytics.ts";
import { useReviewQueue } from "../hooks/useReviewQueue.ts";

const planStateLabels = {
  none: "今天还没有计划",
  not_started: "尚未开始",
  in_progress: "进行中",
  completed: "今天的任务已处理完",
};

export function DashboardPage() {
  const health = useOutletContext<HealthState>();
  const { goals, loading, error, reload } = useGoals();
  const plan = usePlanDashboard();
  const analytics = useAnalytics();
  const reviews = useReviewQueue();
  const counts = [
    { label: "学习目标总数", value: goals.length },
    { label: "正在进行", value: goals.filter((goal) => goal.status === "active").length },
    { label: "已完成", value: goals.filter((goal) => goal.status === "completed").length },
    { label: "已暂停", value: goals.filter((goal) => goal.status === "paused").length },
  ];

  return (
    <div className="mx-auto max-w-5xl">
      <p className="text-sm font-medium text-accent">学习概览</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink md:text-4xl">
        今天的学习目标
      </h1>
      <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
        目标数量和今日计划都来自数据库。打开首页不会调用 DeepSeek。
      </p>

      <div className="mt-8 grid gap-4 lg:grid-cols-2">
        <HealthCard
          health={health.health}
          error={health.error}
          loading={health.loading}
          onReload={health.reload}
        />

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-slate-500">学习目标</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight">
                {loading ? "正在读取" : error ? "暂时无法读取" : "来自数据库"}
              </h2>
            </div>
            <Link to="/goals" className="text-sm font-medium text-accent">
              去管理
            </Link>
          </div>
          {loading && <p className="mt-5 text-sm text-slate-500">正在读取学习目标…</p>}
          {!loading && error && (
            <div className="mt-5 text-sm leading-6 text-rose-700">
              <p>{error}</p>
              <button type="button" onClick={reload} className="mt-3 rounded-full bg-ink px-4 py-2 text-white">
                重新读取
              </button>
            </div>
          )}
          {!loading && !error && (
            <dl className="mt-5 grid grid-cols-2 gap-3">
              {counts.map((item) => (
                <div key={item.label} className="rounded-2xl bg-mist px-4 py-3">
                  <dt className="text-sm text-slate-500">{item.label}</dt>
                  <dd className="mt-1 text-2xl font-semibold">{item.value}</dd>
                </div>
              ))}
            </dl>
          )}
        </section>
      </div>

      <section className="mt-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-slate-500">今日计划</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">
              {plan.loading && "正在读取"}
              {!plan.loading && plan.error && "暂时无法读取"}
              {!plan.loading && !plan.error && plan.dashboard?.recent_goal?.title}
              {!plan.loading && !plan.error && !plan.dashboard?.recent_goal && "还没有学习目标"}
            </h2>
          </div>
          <Link to={plan.dashboard?.recent_goal ? `/plans?goal_id=${plan.dashboard.recent_goal.id}` : "/plans"} className="text-sm font-medium text-accent">
            打开计划
          </Link>
        </div>
        {plan.loading && <p className="mt-4 text-sm text-slate-500">正在读取今日计划…</p>}
        {!plan.loading && plan.error && <p className="mt-4 text-sm text-rose-700">{plan.error}</p>}
        {!plan.loading && !plan.error && plan.dashboard && !plan.dashboard.has_plan && (
          <p className="mt-4 text-sm leading-6 text-slate-600">{planStateLabels.none}。需要你在计划页确认后才会生成。</p>
        )}
        {!plan.loading && !plan.error && plan.dashboard?.has_plan && (
          <div className="mt-4">
            <p className="text-sm text-slate-600">{plan.dashboard.plan_title}</p>
            <p className="mt-2 text-sm text-slate-500">
              {planStateLabels[plan.dashboard.plan_state]} · 完成 {plan.dashboard.completed_tasks} / {plan.dashboard.total_tasks}
              {plan.dashboard.plan_version ? ` · 第 ${plan.dashboard.plan_version} 版` : ""}
            </p>
            <div className="mt-3 h-2 rounded-full bg-slate-100">
              <div className="h-2 rounded-full bg-accent" style={{ width: `${Math.round(plan.dashboard.progress * 100)}%` }} />
            </div>
          </div>
        )}
      </section>

      <section className="mt-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-slate-500">今日复习</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">到期的知识点</h2>
          </div>
          <Link to="/reviews" className="text-sm font-medium text-accent">
            打开复习
          </Link>
        </div>
        {reviews.loading && <p className="mt-4 text-sm text-slate-500">正在读取复习队列…</p>}
        {reviews.error && <p className="mt-4 text-sm text-rose-700">{reviews.error}</p>}
        {reviews.queue && (
          <>
            <dl className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
              {[
                ["今日待复习", String(reviews.queue.due_count)],
                ["已逾期", String(reviews.queue.overdue_count)],
                ["高风险", String(reviews.queue.high_risk.length)],
                ["今日已完成", String(reviews.queue.completed_today)],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl bg-mist px-4 py-3">
                  <dt className="text-sm text-slate-500">{label}</dt>
                  <dd className="mt-1 text-2xl font-semibold">{value}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-4 h-2 rounded-full bg-slate-100">
              <div
                className="h-2 rounded-full bg-accent"
                style={{
                  width: `${
                    reviews.queue.due_count + reviews.queue.overdue_count + reviews.queue.completed_today === 0
                      ? 0
                      : Math.round(
                          (reviews.queue.completed_today /
                            (reviews.queue.due_count + reviews.queue.overdue_count + reviews.queue.completed_today)) *
                            100,
                        )
                  }%`,
                }}
              />
            </div>
            {reviews.queue.high_risk.length > 0 && (
              <ul className="mt-4 space-y-2 text-sm leading-6 text-slate-600">
                {reviews.queue.high_risk.slice(0, 3).map((item) => (
                  <li key={item.id}>
                    <span className="font-medium text-ink">{item.name}：</span>
                    {item.risk_reason}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>

      <section className="mt-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-slate-500">学习效果</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">检测之后才更新掌握度</h2>
          </div>
          <Link to="/progress" className="text-sm font-medium text-accent">
            查看掌握情况
          </Link>
        </div>
        {analytics.loading && <p className="mt-4 text-sm text-slate-500">正在读取学习效果…</p>}
        {analytics.error && <p className="mt-4 text-sm text-rose-700">{analytics.error}</p>}
        {analytics.analytics && (
          <>
            <dl className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3">
              {[
                ["完成任务", String(analytics.analytics.completed_tasks)],
                ["检测次数", String(analytics.analytics.quiz_count)],
                ["平均成绩", analytics.analytics.average_score === null ? "—" : String(analytics.analytics.average_score)],
                ["已掌握", String(analytics.analytics.mastered_count)],
                ["需要巩固", String(analytics.analytics.needs_review_count)],
                ["最近检测", analytics.analytics.latest_score === null ? "—" : String(analytics.analytics.latest_score)],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl bg-mist px-4 py-3">
                  <dt className="text-sm text-slate-500">{label}</dt>
                  <dd className="mt-1 text-2xl font-semibold">{value}</dd>
                </div>
              ))}
            </dl>
            {analytics.analytics.points.length > 0 && (
              <ul className="mt-4 space-y-3">
                {analytics.analytics.points.slice(0, 4).map((point) => (
                  <li key={point.id}>
                    <div className="flex justify-between text-sm">
                      <span className="font-medium">{point.name}</span>
                      <span className="text-slate-500">
                        {point.mastery_assessed ? `${point.mastery_level} · ${point.status_label}` : "尚未评估"}
                      </span>
                    </div>
                    <div className="mt-2 h-2 rounded-full bg-slate-100">
                      <div className="h-2 rounded-full bg-accent" style={{ width: `${point.mastery_assessed ? point.mastery_level ?? 0 : 0}%` }} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>
    </div>
  );
}
