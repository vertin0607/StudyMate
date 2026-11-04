import type { ProblemDetail, ProblemStatistics, ProblemSummary, ProblemTestCase, ProblemWriteInput, TopicGroup } from "../types/problem.ts";
import { api } from "./api.ts";

const aiTimeout = 70000;

export type ProblemQuery = {
  keyword?: string;
  course?: string;
  topic_id?: number;
  difficulty?: string;
  source_platform?: string;
  analysis_status?: string;
};

export async function fetchProblemStatistics(): Promise<ProblemStatistics> {
  const { data } = await api.get<ProblemStatistics>("/api/problems/statistics");
  return data;
}

export async function fetchTopics(): Promise<TopicGroup[]> {
  const { data } = await api.get<{ categories: TopicGroup[] }>("/api/problems/topics");
  return data.categories;
}

export async function fetchProblems(query: ProblemQuery = {}): Promise<ProblemSummary[]> {
  const { data } = await api.get<{ problems: ProblemSummary[] }>("/api/problems", { params: query });
  return data.problems;
}

export async function fetchProblemsByTopic(topicId: number): Promise<{ topic: { id: number; name: string }; problems: ProblemSummary[] }> {
  const { data } = await api.get<{ topic: { id: number; name: string }; problems: ProblemSummary[] }>(`/api/problems/knowledge/${topicId}`);
  return data;
}

export async function importProblem(input: ProblemWriteInput): Promise<{ problem: ProblemDetail; duplicate_warning: boolean }> {
  const { data } = await api.post<{ problem: ProblemDetail; duplicate_warning: boolean }>("/api/problems/import", input);
  return data;
}

export async function fetchProblem(problemId: number): Promise<ProblemDetail> {
  const { data } = await api.get<ProblemDetail>(`/api/problems/${problemId}`);
  return data;
}

export async function updateProblem(problemId: number, input: ProblemWriteInput): Promise<ProblemDetail> {
  const { data } = await api.put<ProblemDetail>(`/api/problems/${problemId}`, input);
  return data;
}

export async function deleteProblem(problemId: number): Promise<void> {
  await api.delete(`/api/problems/${problemId}`);
}

export async function analyzeProblem(problemId: number): Promise<ProblemDetail> {
  const { data } = await api.post<ProblemDetail>(`/api/problems/${problemId}/analyze`, undefined, { timeout: aiTimeout });
  return data;
}

export async function saveClassification(
  problemId: number,
  payload: { course: string; difficulty: string; links: { topic_id: number; relevance: "primary" | "secondary"; reason: string }[] },
): Promise<ProblemDetail> {
  const { data } = await api.put<ProblemDetail>(`/api/problems/${problemId}/classification`, payload);
  return data;
}

export async function confirmTopic(problemId: number, name: string, relevance: "primary" | "secondary", reason: string): Promise<ProblemDetail> {
  const { data } = await api.post<ProblemDetail>(`/api/problems/${problemId}/topics/confirm`, { name, relevance, reason });
  return data;
}

export async function addTestCase(problemId: number, payload: ProblemWriteInput["test_cases"][number]): Promise<ProblemTestCase> {
  const { data } = await api.post<ProblemTestCase>(`/api/problems/${problemId}/test-cases`, payload);
  return data;
}

export async function updateTestCase(problemId: number, caseId: number, payload: ProblemWriteInput["test_cases"][number]): Promise<ProblemTestCase> {
  const { data } = await api.put<ProblemTestCase>(`/api/problems/${problemId}/test-cases/${caseId}`, payload);
  return data;
}

export async function deleteTestCase(problemId: number, caseId: number): Promise<void> {
  await api.delete(`/api/problems/${problemId}/test-cases/${caseId}`);
}

export async function saveProblemNote(problemId: number, content: string, solutionIdea: string): Promise<void> {
  await api.post(`/api/problems/${problemId}/notes`, { content, solution_idea: solutionIdea });
}
