import type { DiagnosisReport } from "../types/growth.ts";
import { api } from "./api.ts";

export async function fetchDiagnosis(goalId: number | null): Promise<DiagnosisReport> {
  const { data } = await api.get<DiagnosisReport>("/api/learning/diagnosis", {
    params: goalId === null ? undefined : { goal_id: goalId },
  });
  return data;
}
