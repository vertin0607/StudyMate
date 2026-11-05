import type { HealthStatus } from "../types/health.ts";

type HealthCardProps = {
  health: HealthStatus | null;
  error: string | null;
  loading: boolean;
  onReload: () => void;
};

export function HealthCard({ health, error, loading, onReload }: HealthCardProps) {
  const online = health?.status === "ok";

  return (
    <section className="rounded-3xl border border-line bg-surface p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-muted">后端连接</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">
            {loading ? "正在检测" : online ? "后端运行正常" : "后端未连接"}
          </h2>
        </div>
        <span
          className={`inline-flex shrink-0 items-center gap-2 rounded-full px-3 py-1 text-sm ${
            loading
              ? "bg-soft text-muted"
              : online
                ? "bg-accent-soft text-accent"
                : "bg-rose-50 text-rose-700"
          }`}
        >
          <span
            className={`h-2 w-2 rounded-full ${
              loading ? "bg-muted" : online ? "bg-accent" : "bg-rose-500"
            }`}
          />
          {loading ? "检测中" : online ? "在线" : "离线"}
        </span>
      </div>

      <div className="mt-5 min-h-16 text-sm leading-6 text-muted" aria-live="polite">
        {loading && <p>正在请求 /api/health。</p>}
        {!loading && online && health && (
          <p>
            服务 {health.service} {health.version}，当前为第 {health.phase} 阶段。
            这次响应来自 FastAPI，页面没有使用写死的成功状态。
          </p>
        )}
        {!loading && error && <p>{error}</p>}
      </div>

      <button
        type="button"
        onClick={onReload}
        disabled={loading}
        className="mt-4 rounded-full bg-accent px-4 py-2 text-sm font-medium text-on-accent transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "检测中…" : "重新检测"}
      </button>
    </section>
  );
}
