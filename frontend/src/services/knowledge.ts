import type { KnowledgeHistoryEvent, KnowledgeListPoint } from "../types/growth.ts";
import { api } from "./api.ts";

export async function fetchKnowledgePoints(goalId: number | null): Promise<KnowledgeListPoint[]> {
  const { data } = await api.get<{ points: KnowledgeListPoint[] }>("/api/knowledge", {
    params: goalId === null ? undefined : { goal_id: goalId },
  });
  return data.points;
}

export async function fetchKnowledgeHistory(knowledgeId: number): Promise<KnowledgeHistoryEvent[]> {
  const { data } = await api.get<{ events: KnowledgeHistoryEvent[] }>(`/api/knowledge/${knowledgeId}/history`);
  return data.events;
}
