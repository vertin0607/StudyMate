import { useCallback, useEffect, useRef, useState } from "react";

import { fetchGoal, fetchGoals } from "../services/goals.ts";
import type { Goal } from "../types/goal.ts";
import { getErrorMessage } from "../utils/apiError.ts";

export function useGoals() {
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback((id: number) => {
    fetchGoals()
      .then((data) => {
        if (requestId.current !== id) {
          return;
        }
        setGoals(data);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (requestId.current !== id) {
          return;
        }
        setError(getErrorMessage(reason, "读取学习目标失败"));
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
    goals: goals ?? [],
    loading: goals === null && error === null,
    error,
    reload,
  };
}

export function useGoal(goalId: number | null) {
  const [goal, setGoal] = useState<Goal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback((id: number, currentGoalId: number) => {
    fetchGoal(currentGoalId)
      .then((data) => {
        if (requestId.current !== id) {
          return;
        }
        setGoal(data);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (requestId.current !== id) {
          return;
        }
        setGoal(null);
        setError(getErrorMessage(reason, "读取学习目标失败"));
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

  return {
    goal,
    setGoal,
    loading: goalId !== null && goal === null && error === null,
    error,
    reload,
  };
}
