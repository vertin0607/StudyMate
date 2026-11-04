import type { ReviewScheduleCard } from "./review.ts";

export type QuestionType = "single" | "multiple" | "true_false" | "short" | "scenario";
export type QuestionDifficulty = "basic" | "medium" | "advanced";

export type QuizOption = {
  key: string;
  text: string;
};

export type QuizQuestion = {
  id: number;
  sort_order?: number;
  question_type: QuestionType;
  difficulty: QuestionDifficulty;
  stem: string;
  options: QuizOption[];
  knowledge_point_name: string | null;
};

export type QuizPaper = {
  id: number;
  goal_id: number;
  task_id: number | null;
  title: string;
  status: string;
  question_count: number;
  questions: QuizQuestion[];
};

export type GradedQuestion = QuizQuestion & {
  user_answer: string;
  correct_answer: string;
  explanation: string;
  is_correct: boolean;
  score: number;
  error_reason: string;
  suggestion: string;
};

export type MasteryUpdate = {
  knowledge_point_id: number;
  name: string;
  previous_level: number | null;
  new_level: number;
  quiz_score: number;
  status: string;
  status_label: string;
  reason: string;
};

export type QuizResult = {
  id: number;
  goal_id: number;
  title: string;
  status: string;
  score: number;
  correct_count: number;
  wrong_count: number;
  level_label: string;
  suggestion: string;
  submitted_at: string | null;
  questions: GradedQuestion[];
  mastery_updates: MasteryUpdate[];
  reviews?: ReviewScheduleCard[];
};

export type KnowledgePointSummary = {
  id: number;
  goal_id: number;
  name: string;
  status: string;
  status_label: string;
  mastery_level: number | null;
  mastery_assessed: boolean;
  recent_quiz_score: number | null;
};

export type LearningAnalytics = {
  completed_tasks: number;
  quiz_count: number;
  average_score: number | null;
  mastered_count: number;
  needs_review_count: number;
  latest_score: number | null;
  points: KnowledgePointSummary[];
};
