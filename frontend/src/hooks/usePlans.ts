import { useCallback, useEffect, useRef, useState } from "react";

import { fetchPlanDashboard, fetchTodayPlan } from "../services/plans.ts";
import type { PlanDashboard, TodayPlan } from "../types/plan.ts";
import { getErrorMessage } from "../utils/apiError.ts";

export function useTodayPlan(goalId: number | null) {
  const [today, setToday] = useState<TodayPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback((id: number, currentGoalId: number) => {
    fetchTodayPlan(currentGoalId)
      .then((data) => {
        if (requestId.current !== id) {
          return;
        }
        setToday(data);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (requestId.current !== id) {
          return;
        }
        setError(getErrorMessage(reason, "读取今日计划失败"));
      });
  }, []);

  const reload = useCallback(() => {
    if (goalId === null) {
      return;
    }
    const id = requestId.current + 1;
    requestId.current = id;
    setError(null);
    load(id, goalId);
  }, [goalId, load]);

  useEffect(() => {
    if (goalId === null) {
      return;
    }
    const id = requestId.current + 1;
    requestId.current = id;
    load(id, goalId);
  }, [goalId, load]);

  const matches = today?.goal_id === goalId;
  return {
    today: matches ? today : null,
    loading: goalId !== null && !matches && error === null,
    error,
    reload,
  };
}

export function usePlanDashboard() {
  const [dashboard, setDashboard] = useState<PlanDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback((id: number) => {
    fetchPlanDashboard()
      .then((data) => {
        if (requestId.current !== id) {
          return;
        }
        setDashboard(data);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (requestId.current !== id) {
          return;
        }
        setError(getErrorMessage(reason, "读取今日计划失败"));
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
    dashboard,
    loading: dashboard === null && error === null,
    error,
    reload,
  };
}
