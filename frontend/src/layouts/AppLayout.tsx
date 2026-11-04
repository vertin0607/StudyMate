import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useHealth } from "../hooks/useHealth.ts";
import { formatServerTime } from "../utils/format.ts";
import { navItems } from "../utils/navigation.ts";

function navItemActive(pathname: string, to: string): boolean {
  if (to === "/problems/wrong") {
    return pathname.startsWith("/problems/wrong");
  }
  if (to === "/problems") {
    return pathname.startsWith("/problems") && !pathname.startsWith("/problems/wrong");
  }
  if (to === "/goals" || to === "/reviews" || to === "/tutor") {
    return pathname === to || pathname.startsWith(`${to}/`);
  }
  return pathname === to;
}

export function AppLayout() {
  const healthState = useHealth();
  const { pathname } = useLocation();
  const { health, error, loading } = healthState;
  const serverTime = health ? formatServerTime(health.server_time) : null;

  return (
    <div className="min-h-screen md:grid md:grid-cols-[248px_minmax(0,1fr)]">
      <aside className="bg-ink text-white md:sticky md:top-0 md:h-screen">
        <div className="flex items-center gap-3 px-5 py-5 md:px-6 md:py-7">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-accent text-sm font-semibold">
            S
          </div>
          <div>
            <p className="text-sm font-semibold tracking-wide">StudyMate</p>
            <p className="text-xs text-slate-400">AI 学习监督</p>
          </div>
        </div>

        <nav className="flex gap-2 overflow-x-auto px-4 pb-4 md:block md:space-y-1 md:px-3 md:pb-6">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={() =>
                `block shrink-0 rounded-xl px-3 py-2 text-sm transition ${
                  navItemActive(pathname, item.to)
                    ? "bg-white/10 text-white"
                    : "text-slate-300 hover:bg-white/5 hover:text-white"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="min-w-0">
        <header className="flex flex-col gap-1 border-b border-slate-200/80 bg-white/80 px-4 py-4 backdrop-blur md:flex-row md:items-center md:justify-between md:px-8">
          <div>
            <p className="text-xs font-medium tracking-wide text-slate-500">服务器时间</p>
            <p className="text-sm font-medium text-ink">
              {loading && "正在读取"}
              {!loading && serverTime}
              {!loading && !serverTime && "暂时无法读取"}
            </p>
          </div>
          <p className="text-sm text-slate-500">
            {error ? "后端未连接" : "个人本地使用"}
          </p>
        </header>
        <main className="px-4 py-6 md:px-8 md:py-8">
          <Outlet context={healthState} />
        </main>
      </div>
    </div>
  );
}
