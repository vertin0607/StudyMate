import type { LearningStatus, PracticeRecord, PracticeStatistics, PracticeTrendDay, WrongProblem } from "../types/practice.ts";
import { api } from "./api.ts";

export async function fetchLearningStatus(problemId: number): Promise<LearningStatus> {
  const { data } = await api.get<LearningStatus>(`/api/problems/${problemId}/learning-status`);
  return data;
}

export async function updateLearningStatus(problemId: number, status: "todo" | "attempting" | "self_completed"): Promise<LearningStatus> {
  const { data } = await api.patch<LearningStatus>(`/api/problems/${problemId}/learning-status`, { status });
  return data;
}

export async function startPractice(problemId: number): Promise<{ created: boolean; record: PracticeRecord }> {
  const { data } = await api.post<{ created: boolean; record: PracticeRecord }>(`/api/problems/${problemId}/practice/start`);
  return data;
}

export async function completePractice(problemId: number, recordId: number, completionType: string, note: string): Promise<PracticeRecord> {
  const { data } = await api.post<PracticeRecord>(`/api/problems/${problemId}/practice/${recordId}/complete`, {
    completion_type: completionType,
    note,
  });
  return data;
}

export async function fetchPracticeHistory(problemId: number): Promise<PracticeRecord[]> {
  const { data } = await api.get<{ records: PracticeRecord[] }>(`/api/problems/${problemId}/practice-history`);
  return data.records;
}

export async function fetchPracticeStatistics(): Promise<PracticeStatistics> {
  const { data } = await api.get<PracticeStatistics>("/api/problems/practice-statistics");
  return data;
}

export async function fetchPracticeTrends(): Promise<PracticeTrendDay[]> {
  const { data } = await api.get<{ days: PracticeTrendDay[] }>("/api/problems/practice-trends");
  return data.days;
}

export async function fetchWrongProblems(query: { topic_id?: number; difficulty?: string } = {}): Promise<WrongProblem[]> {
  const { data } = await api.get<{ problems: WrongProblem[] }>("/api/problems/wrong", { params: query });
  return data.problems;
}

export async function addWrongProblem(problemId: number, reasonType: string, reasonDetail: string, submissionId: number | null): Promise<void> {
  await api.post(`/api/problems/${problemId}/wrong`, {
    reason_type: reasonType,
    reason_detail: reasonDetail,
    related_submission_id: submissionId,
  });
}

export async function updateWrongProblem(problemId: number, reasonType: string, reasonDetail: string, submissionId: number | null): Promise<void> {
  await api.put(`/api/problems/${problemId}/wrong`, {
    reason_type: reasonType,
    reason_detail: reasonDetail,
    related_submission_id: submissionId,
  });
}

export async function deleteWrongProblem(problemId: number): Promise<void> {
  await api.delete(`/api/problems/${problemId}/wrong`);
}
