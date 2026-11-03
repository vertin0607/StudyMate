/** 后端 GET /api/health 的响应。 */
export type HealthStatus = {
  status: string;
  service: string;
  version: string;
  phase: number;
  server_time: string;
};
