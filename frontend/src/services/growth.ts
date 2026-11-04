import type { GrowthDays, GrowthReport } from "../types/growth.ts";
import { api } from "./api.ts";

export async function fetchGrowth(goalId: number | null, days: GrowthDays): Promise<GrowthReport> {
  const { data } = await api.get<GrowthReport>("/api/learning/growth", {
    params: { days, ...(goalId === null ? {} : { goal_id: goalId }) },
  });
  return data;
}
