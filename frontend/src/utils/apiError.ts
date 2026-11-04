import axios from "axios";

/** 把后端返回的 detail 转成页面上的一句说明。 */
export function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (!error.response) {
      return "无法连接后端。请确认 FastAPI 已在 127.0.0.1:8000 启动。";
    }
  }
  return fallback;
}
