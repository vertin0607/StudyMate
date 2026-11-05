import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "./useAuth.ts";
import { safeNextPath } from "./paths.ts";

export function AuthStatus({ message, action }: { message: string; action?: { label: string; onClick: () => void } }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-mist px-4">
      <div className="w-full max-w-sm rounded-3xl border border-line bg-surface p-8 text-center shadow-sm">
        <p className="text-sm text-muted">{message}</p>
        {action ? (
          <button
            type="button"
            onClick={action.onClick}
            className="mt-5 rounded-2xl bg-accent px-4 py-2 text-sm font-medium text-on-accent"
          >
            {action.label}
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function RequireAuth() {
  const { user, isLoading, bootError, refreshUser } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <AuthStatus message="正在确认登录状态" />;
  }
  if (bootError) {
    return <AuthStatus message={bootError} action={{ label: "重试", onClick: () => void refreshUser() }} />;
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />;
  }
  return <Outlet />;
}

export function GuestOnly() {
  const { user, isLoading, bootError, refreshUser } = useAuth();
  const location = useLocation();
  const next = safeNextPath((location.state as { from?: unknown } | null)?.from);

  if (isLoading) {
    return <AuthStatus message="正在确认登录状态" />;
  }
  if (bootError) {
    return <AuthStatus message={bootError} action={{ label: "重试", onClick: () => void refreshUser() }} />;
  }
  if (user) {
    return <Navigate to={next} replace />;
  }
  return <Outlet />;
}
