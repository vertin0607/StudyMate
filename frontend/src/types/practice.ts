export type LearningStatusName = "todo" | "attempting" | "self_completed" | "accepted" | "wrong_answer" | "compile_error" | "time_limit_exceeded" | "runtime_error";

export type LearningStatus = {
  problem_id: number;
  status: LearningStatusName;
  saved: boolean;
  locked: boolean;
  updated_at: string | null;
};

export type PracticeRecord = {
  id: number;
  problem_id: number;
  started_at: string;
  completed_at: string | null;
  completion_type: string;
  used_hint: boolean;
  viewed_solution: boolean;
  note: string;
  open: boolean;
  problem_title?: string;
};

export type WrongProblem = {
  id: number;
  problem_id: number;
  title: string;
  difficulty: string;
  reason_type: string;
  reason_detail: string;
  related_submission_id: number | null;
  topics: { topic_id: number; name: string }[];
  updated_at: string;
};

export type PracticeStatistics = {
  total: number;
  todo: number;
  attempting: number;
  self_completed: number;
  accepted: number;
  wrong_answer: number;
  compile_error: number;
  time_limit_exceeded: number;
  runtime_error: number;
  wrong_count: number;
  submission_count: number;
  practice_total: number;
  practice_today: number;
  started_problems: number;
};

export type PracticeTrendDay = {
  date: string;
  practice_count: number;
  submission_count: number;
};

export const learningStatusLabels: Record<LearningStatusName, string> = {
  todo: "待练习",
  attempting: "练习中",
  self_completed: "用户自评完成",
  accepted: "系统判题通过",
  wrong_answer: "系统判题未通过",
  compile_error: "编译失败",
  time_limit_exceeded: "运行超时",
  runtime_error: "运行异常",
};

export const completionLabels: Record<string, string> = {
  independent: "独立完成",
  with_hint: "看过提示后完成",
  with_solution: "参考题解后完成",
  unfinished: "未完成",
};

export const reasonLabels: Record<string, string> = {
  algorithm: "算法思路",
  boundary: "边界条件",
  implementation: "代码实现",
  syntax: "语法",
  complexity: "复杂度",
  other: "其他",
};
