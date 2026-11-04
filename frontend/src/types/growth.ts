export type GrowthDays = 7 | 30 | 90;

export type GrowthDay = {
  date: string;
  has_activity: boolean;
  completed_task_count: number;
  completed_quiz_count: number;
  review_count: number;
  practice_count: number;
  submission_count: number;
  has_duration_record: boolean;
  actual_practice_seconds: number | null;
};

export type GrowthSummary = {
  study_day_count: number;
  current_streak_days: number;
  studied_today: boolean;
  completed_task_count: number;
  completed_quiz_count: number;
  review_count: number;
  practiced_problem_count: number;
  submitted_problem_count: number;
  submission_count: number;
  local_accepted_problem_count: number;
  local_accepted_submission_count: number;
  pass_rate: number | null;
  pass_rate_numerator: number;
  pass_rate_denominator: number;
  actual_practice_seconds: number | null;
  self_completed_problem_count: number;
};

export type MasteryDirection = "up" | "down" | "stable" | "insufficient";

export type MasteryEvent = {
  id: number;
  date: string;
  previous_level: number | null;
  mastery_level: number;
  quiz_score: number;
};

export type GrowthMasteryPoint = {
  knowledge_point_id: number;
  name: string;
  goal_id: number;
  mastery_assessed: boolean;
  current_mastery: number | null;
  direction: MasteryDirection;
  history: MasteryEvent[];
  review_dates: string[];
};

export type GrowthQuizItem = {
  id: number;
  goal_id: number;
  title: string;
  date: string;
  score: number | null;
};

export type GrowthQuizPoint = {
  knowledge_point_id: number;
  name: string;
  count: number;
  average_score: number | null;
  highest_score: number | null;
  lowest_score: number | null;
  scores: number[];
};

export type JudgeCounts = {
  accepted: number;
  wrong_answer: number;
  compile_error: number;
  time_limit_exceeded: number;
  runtime_error: number;
  system_error: number;
  unjudged: number;
};

export type GrowthEvidence = {
  id: number | null;
  source: string;
  date: string;
  quiz_score?: number;
  mastery_level?: number;
  review_result?: string;
  score?: number | null;
  judge_status?: string;
  submission_id?: number;
  problem_id?: number;
};

export type GrowthChange = {
  subject: "knowledge" | "problem" | string;
  status: "improved" | "still_present" | string;
  knowledge_point_id: number | null;
  problem_id: number | null;
  name: string;
  earlier: GrowthEvidence;
  later: GrowthEvidence;
};

export type GrowthReport = {
  goal_id: number | null;
  days: GrowthDays;
  today: string;
  practice_scope: string;
  scope: {
    study_activity: "all_goals" | "selected_goal" | string;
    practice: string;
    dates: string;
  };
  summary: GrowthSummary;
  series: GrowthDay[];
  mastery: {
    sufficient: boolean;
    points: GrowthMasteryPoint[];
  };
  quizzes: {
    count: number;
    average_score: number | null;
    highest_score: number | null;
    lowest_score: number | null;
    latest_score: number | null;
    note: string;
    last_7_days: GrowthQuizItem[];
    last_30_days: GrowthQuizItem[];
    by_knowledge_point: GrowthQuizPoint[];
  };
  practice: {
    scope: string;
    practice_scope: string;
    practiced_problem_count: number;
    submitted_problem_count: number;
    submission_count: number;
    local_accepted_problem_count: number;
    local_accepted_submission_count: number;
    judge_counts: JudgeCounts;
    pass_rate_numerator: number;
    pass_rate_denominator: number;
    pass_rate: number | null;
    pass_rate_note: string;
    actual_practice_seconds: number | null;
    actual_practice_record_count: number;
    duration_note: string;
    self_completed_problem_count: number;
    wrong_record_count: number;
    series: GrowthDay[];
  };
  weaknesses: {
    improved: GrowthChange[];
    still_present: GrowthChange[];
    note: string;
  };
};

export type KnowledgeListPoint = {
  id: number;
  goal_id: number;
  name: string;
  status: string;
  status_label: string;
  mastery_level: number | null;
  mastery_assessed: boolean;
  recent_quiz_score: number | null;
};

export type KnowledgeHistoryEvent = {
  id: number;
  previous_level: number | null;
  new_level: number;
  quiz_score: number;
  reason: string;
  created_at: string;
};

export type QuizHistoryItem = {
  id: number;
  title: string;
  score: number | null;
  correct_count: number;
  wrong_count: number;
  level_label: string;
  submitted_at: string | null;
  goal_id: number;
};

export type DiagnosisStatus = "confirmed" | "suspected" | "insufficient_data";

export type DiagnosisEvidence = {
  type?: string;
  knowledge_point_id?: number;
  problem_id?: number;
  score?: number;
  at?: string | null;
  below_60?: boolean;
  in_current_streak?: boolean;
  counts?: boolean;
  status?: string;
  submission_id?: number;
};

export type DiagnosisItem = {
  category: string;
  status: DiagnosisStatus;
  knowledge_point_id: number | null;
  knowledge_point_name: string | null;
  goal_id: number | null;
  problem_topics: { id: number; name: string }[];
  evidence_count: number;
  evidence: DiagnosisEvidence[];
  reason: string;
};

export type DiagnosisReport = {
  goal_id: number | null;
  summary: {
    total: number;
    confirmed: number;
    suspected: number;
    insufficient_data: number;
  };
  by_category: Record<string, DiagnosisItem[]>;
};
