import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

import type { HealthStatus } from "../types/health.ts";

/**
 * 所有接口都请求 StudyMate 后端。
 * 开发环境下 Vite 会把 /api 代理到 127.0.0.1:8000。
 * 登录凭证只放在 HttpOnly Cookie 里，这里只读取 CSRF Cookie。
 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "",
  timeout: 8000,
  withCredentials: true,
});

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const CSRF_COOKIE = "studymate_csrf";
const CSRF_DETAIL = "缺少或无效的 CSRF 令牌";

type RetryConfig = InternalAxiosRequestConfig & { csrfRetried?: boolean };

let csrfMemory: string | null = null;
let csrfRequest: Promise<string> | null = null;
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

export function clearCsrf(): void {
  csrfMemory = null;
}

function readCsrfCookie(): string | null {
  const prefix = `${CSRF_COOKIE}=`;
  for (const part of document.cookie.split("; ")) {
    if (part.startsWith(prefix)) {
      return decodeURIComponent(part.slice(prefix.length));
    }
  }
  return null;
}

export async function ensureCsrf(force = false): Promise<string> {
  if (!force && csrfMemory) {
    return csrfMemory;
  }
  if (!force) {
    const cookie = readCsrfCookie();
    if (cookie) {
      csrfMemory = cookie;
      return cookie;
    }
  }
  if (!csrfRequest) {
    csrfRequest = api
      .get<{ csrf_token: string }>("/api/auth/csrf")
      .then((response) => {
        csrfMemory = response.data.csrf_token;
        return response.data.csrf_token;
      })
      .finally(() => {
        csrfRequest = null;
      });
  }
  return csrfRequest;
}

/** 给离开页面前的原生 fetch 使用。只附带 CSRF，不读取会话 Cookie 的值。 */
export function mutationHeaders(): HeadersInit {
  const token = csrfMemory ?? readCsrfCookie();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers["X-CSRF-Token"] = token;
  }
  return headers;
}

function isSessionProbe(url: string | undefined): boolean {
  if (!url) {
    return false;
  }
  return ["/api/auth/login", "/api/auth/register", "/api/auth/csrf", "/api/auth/me"].some((path) => url.includes(path));
}

api.interceptors.request.use(async (config) => {
  const method = (config.method ?? "get").toUpperCase();
  if (!UNSAFE.has(method)) {
    return config;
  }
  const token = await ensureCsrf();
  config.headers.set("X-CSRF-Token", token);
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetryConfig | undefined;
    const status = error.response?.status;
    const detail = error.response?.data && typeof error.response.data === "object" ? (error.response.data as { detail?: unknown }).detail : undefined;
    if (status === 403 && detail === CSRF_DETAIL && config && !config.csrfRetried) {
      config.csrfRetried = true;
      csrfMemory = null;
      const token = await ensureCsrf(true);
      config.headers.set("X-CSRF-Token", token);
      return api.request(config);
    }
    if (status === 401 && !isSessionProbe(config?.url)) {
      onUnauthorized?.();
    }
    return Promise.reject(error);
  },
);

export async function fetchHealth(): Promise<HealthStatus> {
  const { data } = await api.get<HealthStatus>("/api/health");
  return data;
}
