import type { AuthUser } from "../types/auth.ts";
import { api, clearCsrf, ensureCsrf } from "./api.ts";

export async function fetchCurrentUser(): Promise<AuthUser> {
  const { data } = await api.get<AuthUser>("/api/auth/me");
  return data;
}

export async function registerAccount(input: { username: string; password: string; email: string | null }): Promise<AuthUser> {
  const { data } = await api.post<AuthUser>("/api/auth/register", input);
  return data;
}

export async function loginAccount(username: string, password: string): Promise<AuthUser> {
  await api.post<AuthUser>("/api/auth/login", { username, password });
  // 登录会换发 CSRF Cookie。重新领取后，后续修改请求才和 Cookie 一致。
  await ensureCsrf(true);
  return fetchCurrentUser();
}

export async function logoutAccount(): Promise<void> {
  await api.post("/api/auth/logout");
  clearCsrf();
}
