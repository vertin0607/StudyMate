import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { safeNextPath } from "../auth/paths.ts";
import { useAuth } from "../auth/useAuth.ts";
import { getErrorMessage } from "../utils/apiError.ts";

const fieldClass =
  "mt-2 w-full rounded-2xl border border-line bg-surface px-4 py-3 text-sm text-ink outline-none transition focus:border-accent";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const registered = (location.state as { registered?: unknown } | null)?.registered;
  const next = safeNextPath((location.state as { from?: unknown } | null)?.from);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const name = username.trim();
    if (!name || !password) {
      setError("请填写用户名和密码");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await login(name, password);
      navigate(next, { replace: true });
    } catch (reason) {
      setError(getErrorMessage(reason, "登录失败，请稍后再试"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-mist px-4 py-10">
      <div className="w-full max-w-md rounded-3xl border border-line bg-surface p-6 shadow-sm md:p-8">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-accent text-sm font-semibold text-on-accent">S</div>
          <div>
            <p className="text-sm font-semibold text-ink">StudyMate</p>
            <p className="text-xs text-muted">登录后继续学习</p>
          </div>
        </div>
        <h1 className="text-2xl font-semibold text-ink">登录</h1>
        {typeof registered === "string" && registered ? (
          <p className="mt-3 rounded-2xl bg-accent-soft px-4 py-3 text-sm text-accent">账号 {registered} 已注册，请登录。</p>
        ) : null}
        <form onSubmit={(event) => void onSubmit(event)} className="mt-6 space-y-4">
          <label className="block text-sm font-medium text-ink">
            用户名
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              className={`${fieldClass} ${error ? "border-red-300" : ""}`}
            />
          </label>
          <label className="block text-sm font-medium text-ink">
            密码
            <span className="relative mt-2 block">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                className={`${fieldClass} mt-0 pr-16 ${error ? "border-red-300" : ""}`}
              />
              <button
                type="button"
                onClick={() => setShowPassword((value) => !value)}
                className="absolute top-1/2 right-3 -translate-y-1/2 text-xs text-muted"
              >
                {showPassword ? "隐藏" : "显示"}
              </button>
            </span>
          </label>
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-2xl bg-accent px-4 py-3 text-sm font-medium text-on-accent disabled:opacity-60"
          >
            {submitting ? "正在登录" : "登录"}
          </button>
        </form>
        <p className="mt-5 text-sm text-muted">
          还没有账号？{" "}
          <Link to="/register" className="font-medium text-accent">
            注册
          </Link>
        </p>
      </div>
    </div>
  );
}
