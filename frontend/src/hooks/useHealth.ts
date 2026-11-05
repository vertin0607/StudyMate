import { useCallback, useEffect, useRef, useState } from "react";

import { fetchHealth } from "../services/api.ts";
import type { HealthStatus } from "../types/health.ts";

const connectionError =
  "后端健康检查失败。请确认运行 StudyMate 的电脑上，后端已经启动，并查看后端终端中的报错。";

export function useHealth() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const requestId = useRef(0);

  // 只在异步结果返回后更新状态，避免效果函数里同步 setState。
  const load = useCallback((id: number) => {
    fetchHealth()
      .then((data) => {
        if (requestId.current !== id) {
          return;
        }
        setHealth(data);
        setError(null);
      })
      .catch(() => {
        if (requestId.current !== id) {
          return;
        }
        setHealth(null);
        setError(connectionError);
      })
      .finally(() => {
        if (requestId.current === id) {
          setLoading(false);
        }
      });
  }, []);

  const reload = useCallback(() => {
    const id = requestId.current + 1;
    requestId.current = id;
    setLoading(true);
    setError(null);
    load(id);
  }, [load]);

  useEffect(() => {
    const id = requestId.current + 1;
    requestId.current = id;
    load(id);
  }, [load]);

  return { health, error, loading, reload };
}

export type HealthState = ReturnType<typeof useHealth>;
