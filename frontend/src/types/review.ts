export type ReviewRisk = "low" | "medium" | "high";

export type ReviewScheduleCard = {
  id: number;
  goal_id: number;
  goal_title?: string | null;
  knowledge_point_id: number;
  name: string;
  last_reviewed_at?: string | null;
  mastery_level: number | null;
  mastery_assessed: boolean;
  status_label: string;
  last_score: number | null;
  next_review_date: string;
  interval_days: number;
  stage_label: string;
  risk: ReviewRisk;
  risk_label: string;
  risk_reason: string;
  reason: string;
  postpone_count: number;
  overdue_days: number;
  queue: string;
  open_quiz_id: number | null;
};

export type ReviewQueue = {
  review_date: string;
  due: ReviewScheduleCard[];
  overdue: ReviewScheduleCard[];
  upcoming: ReviewScheduleCard[];
  due_count: number;
  overdue_count: number;
  upcoming_count: number;
  completed_today: number;
  high_risk: { id: number; name: string; risk_reason: string }[];
};

export type MemoryProfile = {
  first_seen_at: string | null;
  last_studied_at: string | null;
  last_quiz_at: string | null;
  study_count: number;
  quiz_count: number;
  average_score: number | null;
  latest_score: number | null;
  mastery_level: number | null;
  mastery_assessed: boolean;
  status_label: string;
  correct_streak: number;
  weak_points: string[];
  next_review_date: string | null;
  interval_days: number | null;
  stage_label: string;
  review_reason: string;
};

export type ReviewDetail = ReviewScheduleCard & {
  memory: MemoryProfile | null;
};

export type ReviewRecordItem = {
  id: number;
  knowledge_point_id: number;
  name: string;
  quiz_id: number | null;
  reviewed_at: string;
  due_date: string | null;
  score: number | null;
  result: string;
  error_summary: string;
  previous_mastery: number | null;
  new_mastery: number | null;
  next_interval: number;
  next_review_date: string;
  reason: string;
};

export type TrendPoint = {
  date: string;
  mastery_level: number;
  quiz_score: number;
};

export type TrendSeries = {
  knowledge_point_id: number;
  name: string;
  sufficient: boolean;
  points: TrendPoint[];
};

export type LearningTrends = {
  sufficient: boolean;
  series: TrendSeries[];
};

export type ReviewStatistics = {
  sufficient: boolean;
  review_count: number;
  week_count: number;
  due_count: number;
  overdue_count: number;
  completed_today: number;
  average_score: number | null;
  on_time_ratio: number | null;
  weak_points: ReviewScheduleCard[];
  most_improved: { name: string; from_level: number; to_level: number; delta: number }[];
  recent_improved: { name: string; delta: number; mastery_level: number }[];
  still_weak: { name: string; mastery_level: number }[];
};

export type ForgettingRiskReport = {
  items: ReviewScheduleCard[];
};
