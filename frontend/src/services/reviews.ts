import type { KnowledgeExplainSession } from "../types/explain.ts";
import type { QuizPaper } from "../types/quiz.ts";
import type { ForgettingRiskReport, LearningTrends, ReviewDetail, ReviewQueue, ReviewRecordItem, ReviewStatistics } from "../types/review.ts";
import { api } from "./api.ts";

const aiTimeout = 120000;

export async function fetchReviewQueue(): Promise<ReviewQueue> {
  const { data } = await api.get<ReviewQueue>("/api/reviews/today");
  return data;
}

export async function fetchReview(scheduleId: number): Promise<ReviewDetail> {
  const { data } = await api.get<ReviewDetail>(`/api/reviews/${scheduleId}`);
  return data;
}

export async function postponeReview(scheduleId: number, days = 1): Promise<ReviewDetail> {
  const { data } = await api.patch<ReviewDetail>(`/api/reviews/${scheduleId}/postpone`, { days });
  return data;
}

export async function startReview(scheduleId: number): Promise<QuizPaper> {
  const { data } = await api.post<QuizPaper>(`/api/reviews/${scheduleId}/start`, undefined, { timeout: aiTimeout });
  return data;
}

export async function fetchReviewHistory(): Promise<{ records: ReviewRecordItem[] }> {
  const { data } = await api.get<{ records: ReviewRecordItem[] }>("/api/reviews/history");
  return data;
}

export async function fetchTrends(knowledgeId?: number): Promise<LearningTrends> {
  const { data } = await api.get<LearningTrends>("/api/learning/trends", {
    params: knowledgeId ? { knowledge_id: knowledgeId } : undefined,
  });
  return data;
}

export async function fetchForgettingRisk(): Promise<ForgettingRiskReport> {
  const { data } = await api.get<ForgettingRiskReport>("/api/learning/forgetting-risk");
  return data;
}

export async function fetchReviewStatistics(): Promise<ReviewStatistics> {
  const { data } = await api.get<ReviewStatistics>("/api/learning/review-statistics");
  return data;
}

export async function fetchKnowledgeExplain(scheduleId: number): Promise<KnowledgeExplainSession> {
  const { data } = await api.get<KnowledgeExplainSession>(`/api/reviews/${scheduleId}/explain`);
  return data;
}

export async function startKnowledgeExplain(scheduleId: number): Promise<KnowledgeExplainSession> {
  const { data } = await api.post<KnowledgeExplainSession>(`/api/reviews/${scheduleId}/explain`, undefined, { timeout: aiTimeout });
  return data;
}

export async function followupKnowledgeExplain(scheduleId: number, content: string): Promise<KnowledgeExplainSession> {
  const { data } = await api.post<KnowledgeExplainSession>(
    `/api/reviews/${scheduleId}/explain/messages`,
    { content },
    { timeout: aiTimeout },
  );
  return data;
}
