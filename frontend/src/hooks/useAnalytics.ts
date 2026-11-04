import { useCallback, useEffect, useRef, useState } from "react";

import { fetchAnalytics } from "../services/quizzes.ts";
import type { LearningAnalytics } from "../types/quiz.ts";
import { getErrorMessage } from "../utils/apiError.ts";

export function useAnalytics() {
  const [analytics, setAnalytics] = useState<LearningAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback((id: number) => {
    fetchAnalytics()
      .then((data) => {
        if (requestId.current !== id) {
          return;
        }
        setAnalytics(data);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (requestId.current !== id) {
          return;
        }
        setError(getErrorMessage(reason, "读取学习效果失败"));
      });
  }, []);

  const reload = useCallback(() => {
    const id = requestId.current + 1;
    requestId.current = id;
    setError(null);
    load(id);
  }, [load]);

  useEffect(() => {
    const id = requestId.current + 1;
    requestId.current = id;
    load(id);
  }, [load]);

  return {
    analytics,
    loading: analytics === null && error === null,
    error,
    reload,
  };
}
