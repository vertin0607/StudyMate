import type { Goal, GoalInput, GoalStatus } from "../types/goal.ts";
import { api } from "./api.ts";

export async function fetchGoals(): Promise<Goal[]> {
  const { data } = await api.get<Goal[]>("/api/goals");
  return data;
}

export async function fetchGoal(goalId: number): Promise<Goal> {
  const { data } = await api.get<Goal>(`/api/goals/${goalId}`);
  return data;
}

export async function createGoal(input: GoalInput): Promise<Goal> {
  const { data } = await api.post<Goal>("/api/goals", input);
  return data;
}

export async function updateGoal(goalId: number, input: GoalInput): Promise<Goal> {
  const { data } = await api.put<Goal>(`/api/goals/${goalId}`, input);
  return data;
}

export async function updateGoalStatus(goalId: number, status: GoalStatus): Promise<Goal> {
  const { data } = await api.patch<Goal>(`/api/goals/${goalId}/status`, { status });
  return data;
}

export async function deleteGoal(goalId: number): Promise<void> {
  await api.delete(`/api/goals/${goalId}`);
}
