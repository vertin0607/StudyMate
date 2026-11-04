import { api } from "./api.ts";

export type JudgeCase = {
  id: number;
  test_case_id: number;
  status: string;
  execution_time_ms: number;
  actual_output: string;
  expected_output: string;
  error_message: string;
};

export type JudgeAnalysis = {
  likely_cause: string;
  location: string;
  explanation: string;
  direction: string;
  patch_example: string;
  confidence_note: string;
};

export type JudgeResult = {
  id: number;
  submission_id: number;
  problem_id: number;
  status: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  compile_output: string;
  error_message: string;
  execution_time_ms: number;
  memory_used_kb: number;
  judged_at: string | null;
  ai_analysis: JudgeAnalysis | null;
  ai_analysis_error: string;
  cases?: JudgeCase[];
};

const labels: Record<string, string> = {
  unjudged: "尚未判题",
  judging: "正在判题",
  accepted: "Accepted，全部测试通过",
  wrong_answer: "Wrong Answer",
  compile_error: "Compile Error",
  time_limit_exceeded: "Time Limit Exceeded",
  runtime_error: "Runtime Error",
  system_error: "判题系统异常",
};

export function judgeStatusLabel(status: string): string {
  return labels[status] ?? status;
}

export async function requestJudge(submissionId: number): Promise<JudgeResult> {
  const { data } = await api.post<JudgeResult>(`/api/submissions/${submissionId}/judge`);
  return data;
}

export async function fetchJudgeResult(submissionId: number): Promise<JudgeResult> {
  const { data } = await api.get<JudgeResult>(`/api/submissions/${submissionId}/judge-result`);
  return data;
}

export async function requestJudgeAnalysis(submissionId: number): Promise<JudgeResult> {
  const { data } = await api.post<JudgeResult>(`/api/submissions/${submissionId}/ai-analysis`, null, { timeout: 70000 });
  return data;
}

export async function waitForJudge(submissionId: number, isCurrent: () => boolean): Promise<JudgeResult | null> {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const current = await fetchJudgeResult(submissionId);
    if (!isCurrent()) {
      return null;
    }
    if (current.status !== "judging") {
      return current;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 700));
    if (!isCurrent()) {
      return null;
    }
  }
  return fetchJudgeResult(submissionId);
}
