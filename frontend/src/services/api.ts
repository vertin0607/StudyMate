import axios from "axios";

import type { HealthStatus } from "../types/health.ts";

/**
 * 所有接口都请求 StudyMate 后端。
 * 开发环境下 Vite 会把 /api 代理到 127.0.0.1:8000。
 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "",
  timeout: 8000,
});

export async function fetchHealth(): Promise<HealthStatus> {
  const { data } = await api.get<HealthStatus>("/api/health");
  return data;
}
