import { api } from "./api.ts";

export type CodeDraft = {
  problem_id: number;
  language: string;
  source_code: string;
  updated_at: string | null;
  saved: boolean;
};

export type SubmissionSummary = {
  id: number;
  problem_id: number;
  language: string;
  status: string;
  code_length: number;
  submitted_at: string;
  judged: boolean;
  message: string;
};

export type SubmissionDetail = SubmissionSummary & {
  source_code: string;
};

export async function fetchDraft(problemId: number): Promise<CodeDraft> {
  const { data } = await api.get<CodeDraft>(`/api/problems/${problemId}/draft`);
  return data;
}

export async function saveDraft(problemId: number, sourceCode: string): Promise<CodeDraft> {
  const { data } = await api.put<CodeDraft>(`/api/problems/${problemId}/draft`, {
    source_code: sourceCode,
    language: "cpp",
  });
  return data;
}

export async function createSubmission(problemId: number, sourceCode: string): Promise<SubmissionDetail> {
  const { data } = await api.post<SubmissionDetail>(`/api/problems/${problemId}/submissions`, {
    source_code: sourceCode,
    language: "cpp",
  });
  return data;
}

export async function fetchSubmissions(problemId: number): Promise<SubmissionSummary[]> {
  const { data } = await api.get<{ submissions: SubmissionSummary[] }>(`/api/problems/${problemId}/submissions`);
  return data.submissions;
}

export async function fetchSubmission(submissionId: number): Promise<SubmissionDetail> {
  const { data } = await api.get<SubmissionDetail>(`/api/submissions/${submissionId}`);
  return data;
}
