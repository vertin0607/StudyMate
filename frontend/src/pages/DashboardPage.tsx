import { useOutletContext } from "react-router-dom";

import { HealthCard } from "../components/HealthCard.tsx";
import type { HealthState } from "../hooks/useHealth.ts";

const readyItems = [
  "FastAPI 健康检查可以返回状态和服务器时间",
  "React 页面可以通过 /api 访问后端",
  "主要页面的路由已经留好",
];

const laterItems = [
  { phase: "第二阶段", text: "用 SQLite 保存学习目标" },
  { phase: "第三阶段", text: "由后端调用 DeepSeek，密钥不进入浏览器" },
  { phase: "第四阶段", text: "按学习记录生成当天计划，同一天不重复生成" },
  { phase: "第五阶段", text: "生成课程和测试，并保存答题结果" },
  { phase: "第六阶段", text: "记录学习档案，并在确认后调整计划" },
];

export function DashboardPage() {
  const health = useOutletContext<HealthState>();

  return (
    <div className="mx-auto max-w-5xl">
      <p className="text-sm font-medium text-accent">第一阶段</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink md:text-4xl">
        今天先确认系统已经跑起来
      </h1>
      <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
        首页目前只检查前后端是否连通。学习目标、今日任务和测试记录会在接入数据库之后出现在这里。
      </p>

      <div className="mt-8 grid gap-4 lg:grid-cols-2">
        <HealthCard
          health={health.health}
          error={health.error}
          loading={health.loading}
          onReload={health.reload}
        />

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-slate-500">学习数据</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">还没有学习记录</h2>
          <dl className="mt-5 space-y-3 text-sm">
            <div className="flex items-center justify-between gap-4 border-b border-slate-100 pb-3">
              <dt className="text-slate-500">当前学习目标</dt>
              <dd className="font-medium">尚未创建</dd>
            </div>
            <div className="flex items-center justify-between gap-4 border-b border-slate-100 pb-3">
              <dt className="text-slate-500">今日任务</dt>
              <dd className="font-medium">尚未生成</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-slate-500">数据库</dt>
              <dd className="font-medium">第二阶段接入</dd>
            </div>
          </dl>
        </section>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold">这一阶段已经完成</h2>
          <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-600">
            {readyItems.map((item) => (
              <li key={item} className="flex gap-3">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-3xl bg-ink p-6 text-white shadow-sm">
          <h2 className="text-lg font-semibold">接下来会做</h2>
          <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-200">
            {laterItems.map((item) => (
              <li key={item.phase}>
                <span className="text-teal-200">{item.phase}</span>
                <span className="mx-2 text-slate-500">/</span>
                {item.text}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
