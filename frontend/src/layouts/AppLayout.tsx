import { useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/useAuth.ts";
import { useHealth } from "../hooks/useHealth.ts";
import { getErrorMessage } from "../utils/apiError.ts";
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
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { health, error, loading } = healthState;
  const serverTime = health ? formatServerTime(health.server_time) : null;
  const [leaving, setLeaving] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const displayName = user?.nickname || user?.username || "已登录";

  async function onLogout() {
    setLeaving(true);
    setLogoutError(null);
    try {
      await logout();
      navigate("/login", { replace: true });
    } catch (reason) {
      setLogoutError(getErrorMessage(reason, "退出失败，请稍后再试"));
    } finally {
      setLeaving(false);
    }
  }

  return (
    <div className="min-h-screen md:grid md:grid-cols-[248px_minmax(0,1fr)]">
      <aside className="bg-sidebar text-[color:var(--app-sidebar-text)] md:sticky md:top-0 md:h-screen">
        <div className="flex items-center gap-3 px-5 py-5 md:px-6 md:py-7">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-accent text-sm font-semibold text-on-accent">
            S
          </div>
          <div>
            <p className="text-sm font-semibold tracking-wide">StudyMate</p>
            <p className="text-xs text-sidebar-muted">AI 学习监督</p>
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
                    ? "bg-[var(--app-sidebar-active)] text-[color:var(--app-sidebar-text)]"
                    : "text-sidebar-muted hover:bg-[var(--app-sidebar-active)] hover:text-[color:var(--app-sidebar-text)]"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="min-w-0">
        <header className="flex flex-col gap-1 border-b border-line bg-surface/80 px-4 py-4 backdrop-blur md:flex-row md:items-center md:justify-between md:px-8">
          <div>
            <p className="text-xs font-medium tracking-wide text-muted">服务器时间</p>
            <p className="text-sm font-medium text-ink">
              {loading && "正在读取"}
              {!loading && serverTime}
              {!loading && !serverTime && "暂时无法读取"}
            </p>
          </div>
          <div className="flex flex-col items-start gap-1 md:items-end">
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-sm text-muted">{error ? `${displayName} · 后端未连接` : displayName}</p>
              <Link to="/settings" className="rounded-xl border border-line px-3 py-1.5 text-sm text-ink">
                外观设置
              </Link>
              <button
                type="button"
                onClick={() => void onLogout()}
                disabled={leaving}
                className="rounded-xl border border-line px-3 py-1.5 text-sm text-ink disabled:opacity-60"
              >
                {leaving ? "正在退出" : "退出登录"}
              </button>
            </div>
            {logoutError ? <p className="text-sm text-red-600">{logoutError}</p> : null}
          </div>
        </header>
        <main className="px-4 py-6 md:px-8 md:py-8">
          <Outlet context={healthState} />
        </main>
      </div>
    </div>
  );
}
