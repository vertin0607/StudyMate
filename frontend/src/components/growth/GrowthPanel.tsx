import type { ReactNode } from "react";

export function GrowthPanel({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 md:p-6">
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      {hint ? <p className="mt-1 text-sm leading-6 text-slate-500">{hint}</p> : null}
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function PanelMessage({ tone, children, onRetry }: { tone: "loading" | "empty" | "error"; children: string; onRetry?: () => void }) {
  const className = tone === "error" ? "text-rose-700" : "text-slate-500";
  return (
    <div className={`text-sm leading-6 ${className}`}>
      <p>{children}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="mt-3 rounded-full bg-ink px-4 py-2 text-white">
          重新读取
        </button>
      ) : null}
    </div>
  );
}
