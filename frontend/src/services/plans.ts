import type { PlanDashboard, PlanHistory, StudyPlan, TaskStatus, TodayPlan } from "../types/plan.ts";
import { api } from "./api.ts";

const generationTimeout = 70000;

export async function fetchTodayPlan(goalId: number): Promise<TodayPlan> {
  const { data } = await api.get<TodayPlan>("/api/plans/today", {
    params: { goal_id: goalId, generate: false },
  });
  return data;
}

export async function fetchPlan(planId: number): Promise<StudyPlan> {
  const { data } = await api.get<StudyPlan>(`/api/plans/${planId}`);
  return data;
}

export async function fetchPlanHistory(planId: number): Promise<PlanHistory> {
  const { data } = await api.get<PlanHistory>(`/api/plans/${planId}/history`);
  return data;
}

export async function fetchPlanDashboard(): Promise<PlanDashboard> {
  const { data } = await api.get<PlanDashboard>("/api/plans/dashboard");
  return data;
}

export async function generatePlan(goalId: number): Promise<TodayPlan> {
  const { data } = await api.post<TodayPlan>(
    "/api/plans/generate",
    { goal_id: goalId },
    { timeout: generationTimeout },
  );
  return data;
}

export async function regeneratePlan(planId: number, instruction: string): Promise<TodayPlan> {
  const { data } = await api.post<TodayPlan>(
    `/api/plans/${planId}/regenerate`,
    { instruction },
    { timeout: generationTimeout },
  );
  return data;
}

export async function updateTaskStatus(taskId: number, status: TaskStatus): Promise<void> {
  await api.patch(`/api/tasks/${taskId}/status`, { status });
}
