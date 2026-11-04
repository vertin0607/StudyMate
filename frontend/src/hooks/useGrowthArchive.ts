import { useCallback, useEffect, useRef, useState } from "react";

import { fetchDiagnosis } from "../services/diagnosis.ts";
import { fetchGrowth } from "../services/growth.ts";
import { fetchKnowledgePoints } from "../services/knowledge.ts";
import { fetchQuizHistory } from "../services/quizzes.ts";
import type { DiagnosisReport, GrowthDays, GrowthReport, KnowledgeListPoint, QuizHistoryItem } from "../types/growth.ts";
import { getErrorMessage } from "../utils/apiError.ts";

type RequestState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
};

function useKeyedRequest<T>(key: string, loader: (key: string) => Promise<T>, fallback: string): RequestState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [seenKey, setSeenKey] = useState(key);
  const requestId = useRef(0);

  if (seenKey !== key) {
    setSeenKey(key);
    setData(null);
    setError(null);
    setLoading(true);
  }

  const run = useCallback(
    (id: number) => {
      loader(key)
        .then((next) => {
          if (requestId.current !== id) {
            return;
          }
          setData(next);
          setError(null);
          setLoading(false);
        })
        .catch((reason: unknown) => {
          if (requestId.current !== id) {
            return;
          }
          setError(getErrorMessage(reason, fallback));
          setLoading(false);
        });
    },
    [fallback, key, loader],
  );

  const reload = useCallback(() => {
    const id = requestId.current + 1;
    requestId.current = id;
    setLoading(true);
    setError(null);
    run(id);
  }, [run]);

  useEffect(() => {
    const id = requestId.current + 1;
    requestId.current = id;
    run(id);
  }, [run]);

  return { data, loading, error, reload };
}

export function useGrowthReport(goalId: number | null, days: GrowthDays): RequestState<GrowthReport> {
  const key = `${goalId ?? "all"}:${days}`;
  const loader = useCallback((requestKey: string) => {
    const [goalKey, dayKey] = requestKey.split(":");
    return fetchGrowth(goalKey === "all" ? null : Number(goalKey), Number(dayKey) as GrowthDays);
  }, []);
  return useKeyedRequest(key, loader, "读取成长汇总失败");
}

export function useKnowledgeList(goalId: number | null): RequestState<KnowledgeListPoint[]> {
  const key = goalId === null ? "all" : String(goalId);
  const loader = useCallback((requestKey: string) => fetchKnowledgePoints(requestKey === "all" ? null : Number(requestKey)), []);
  return useKeyedRequest(key, loader, "读取知识点失败");
}

export function useDiagnosisReport(goalId: number | null): RequestState<DiagnosisReport> {
  const key = goalId === null ? "all" : String(goalId);
  const loader = useCallback((requestKey: string) => fetchDiagnosis(requestKey === "all" ? null : Number(requestKey)), []);
  return useKeyedRequest(key, loader, "读取诊断失败");
}

export function useQuizHistory(goalIds: number[]): RequestState<QuizHistoryItem[]> {
  const key = goalIds.join(",");
  const loader = useCallback(async (requestKey: string) => {
    if (!requestKey) {
      return [];
    }
    const groups = await Promise.all(requestKey.split(",").map((value) => fetchQuizHistory(Number(value))));
    return groups.flat().sort((left, right) => (right.submitted_at ?? "").localeCompare(left.submitted_at ?? ""));
  }, []);
  return useKeyedRequest(key, loader, "读取检测历史失败");
}
