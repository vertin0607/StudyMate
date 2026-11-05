import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/useAuth.ts";
import { getErrorMessage } from "../utils/apiError.ts";

const fieldClass =
  "mt-2 w-full rounded-2xl border border-line bg-surface px-4 py-3 text-sm text-ink outline-none transition focus:border-accent";

function passwordProblem(username: string, password: string): string | null {
  if (password.length < 8 || password.length > 128) {
    return "密码需要 8 到 128 位";
  }
  const hasLetter = [...password].some((character) => /\p{L}/u.test(character));
  const hasDigit = [...password].some((character) => character >= "0" && character <= "9");
  if (!hasLetter || !hasDigit) {
    return "密码需要同时包含字母和数字";
  }
  if (password.toLowerCase() === username.trim().toLowerCase()) {
    return "密码不能与用户名相同";
  }
  return null;
}

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const name = username.trim();
    if (!name || /\s/.test(name) || name.length > 50) {
      setError("用户名需要 1 到 50 个字符，且不能包含空白");
      return;
    }
    const mail = email.trim();
    if (mail && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(mail)) {
      setError("邮箱格式不正确");
      return;
    }
    if (password !== confirm) {
      setError("两次输入的密码不一致");
      return;
    }
    const passwordError = passwordProblem(name, password);
    if (passwordError) {
      setError(passwordError);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await register({ username: name, password, email: mail || null });
      navigate("/login", { replace: true, state: { registered: name } });
    } catch (reason) {
      setError(getErrorMessage(reason, "注册失败，请稍后再试"));
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
            <p className="text-xs text-muted">注册一个独立的学习账号</p>
          </div>
        </div>
        <h1 className="text-2xl font-semibold text-ink">注册</h1>
        <form onSubmit={(event) => void onSubmit(event)} className="mt-6 space-y-4">
          <label className="block text-sm font-medium text-ink">
            用户名
            <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" className={`${fieldClass} ${error ? "border-red-300" : ""}`} />
          </label>
          <label className="block text-sm font-medium text-ink">
            邮箱
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              placeholder="可以不填"
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
                autoComplete="new-password"
                className={`${fieldClass} mt-0 pr-16 ${error ? "border-red-300" : ""}`}
              />
              <button type="button" onClick={() => setShowPassword((value) => !value)} className="absolute top-1/2 right-3 -translate-y-1/2 text-xs text-muted">
                {showPassword ? "隐藏" : "显示"}
              </button>
            </span>
          </label>
          <label className="block text-sm font-medium text-ink">
            确认密码
            <input
              type={showPassword ? "text" : "password"}
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              autoComplete="new-password"
              className={`${fieldClass} ${error ? "border-red-300" : ""}`}
            />
          </label>
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          <button type="submit" disabled={submitting} className="w-full rounded-2xl bg-accent px-4 py-3 text-sm font-medium text-on-accent disabled:opacity-60">
            {submitting ? "正在注册" : "注册"}
          </button>
        </form>
        <p className="mt-5 text-sm text-muted">
          已有账号？{" "}
          <Link to="/login" className="font-medium text-accent">
            登录
          </Link>
        </p>
      </div>
    </div>
  );
}
