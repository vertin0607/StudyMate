import type { QuizHistoryItem } from "../types/growth.ts";
import type { LearningAnalytics, QuizPaper, QuizResult } from "../types/quiz.ts";
import { api } from "./api.ts";

const aiTimeout = 70000;

export async function generateQuiz(taskId: number): Promise<QuizPaper> {
  const { data } = await api.post<QuizPaper>("/api/quizzes/generate", { task_id: taskId }, { timeout: aiTimeout });
  return data;
}

export async function fetchQuiz(quizId: number): Promise<QuizPaper | QuizResult> {
  const { data } = await api.get<QuizPaper | QuizResult>(`/api/quizzes/${quizId}`);
  return data;
}

export async function submitQuiz(quizId: number, answers: { question_id: number; answer: string }[]): Promise<QuizResult> {
  const { data } = await api.post<QuizResult>(`/api/quizzes/${quizId}/submit`, { answers }, { timeout: aiTimeout });
  return data;
}

export async function fetchQuizHistory(goalId: number): Promise<QuizHistoryItem[]> {
  const { data } = await api.get<{ quizzes: Omit<QuizHistoryItem, "goal_id">[] }>("/api/quizzes/history", {
    params: { goal_id: goalId },
  });
  return data.quizzes.map((quiz) => ({ ...quiz, goal_id: goalId }));
}

export async function fetchAnalytics(): Promise<LearningAnalytics> {
  const { data } = await api.get<LearningAnalytics>("/api/learning/analytics");
  return data;
}

export function isQuizResult(value: QuizPaper | QuizResult): value is QuizResult {
  return value.status === "completed";
}
