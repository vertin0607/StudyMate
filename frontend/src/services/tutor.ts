import type { TutorReply, TutorSessionDetail, TutorSessionSummary } from "../types/tutor.ts";
import { api } from "./api.ts";

const aiTimeout = 70000;

export async function fetchTutorSessions(): Promise<TutorSessionSummary[]> {
  const { data } = await api.get<{ sessions: TutorSessionSummary[] }>("/api/tutor/sessions");
  return data.sessions;
}

export async function createTutorSession(goalId: number | null): Promise<TutorSessionDetail> {
  const { data } = await api.post<TutorSessionDetail>("/api/tutor/sessions", { goal_id: goalId });
  return data;
}

export async function fetchTutorSession(sessionId: number): Promise<TutorSessionDetail> {
  const { data } = await api.get<TutorSessionDetail>(`/api/tutor/sessions/${sessionId}`);
  return data;
}

export async function deleteTutorSession(sessionId: number): Promise<void> {
  await api.delete(`/api/tutor/sessions/${sessionId}`);
}

export async function sendTutorMessage(sessionId: number, content: string): Promise<TutorReply> {
  const { data } = await api.post<TutorReply>(`/api/tutor/sessions/${sessionId}/messages`, { content }, { timeout: aiTimeout });
  return data;
}
