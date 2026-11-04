export type TaskType = "learn" | "practice" | "review" | "quiz";
export type TaskStatus = "pending" | "in_progress" | "completed" | "skipped";

export type StudyTask = {
  id: number;
  title: string;
  description: string;
  task_type: TaskType;
  estimated_minutes: number;
  sort_order: number;
  status: TaskStatus;
  knowledge_point_name: string | null;
  knowledge_status: string | null;
  mastery_level: number | null;
  mastery_assessed: boolean;
  completed_at: string | null;
};

export type StudyPlan = {
  id: number;
  goal_id: number;
  plan_date: string;
  title: string;
  description: string;
  total_minutes: number;
  status: "active" | "archived";
  version: number;
  tasks: StudyTask[];
};

export type TodayPlan = {
  goal_id: number;
  goal_title: string;
  goal_status: string;
  daily_minutes: number;
  plan_date: string;
  server_time: string;
  plan: StudyPlan | null;
};

export type PlanDashboard = {
  plan_date: string;
  recent_goal: { id: number; title: string; status: string } | null;
  has_plan: boolean;
  plan_id: number | null;
  plan_title: string | null;
  plan_version: number | null;
  total_tasks: number;
  completed_tasks: number;
  progress: number;
  plan_state: "none" | "not_started" | "in_progress" | "completed";
};

export type PlanHistory = {
  versions: {
    id: number;
    version: number;
    title: string;
    status: string;
    total_minutes: number;
    created_at: string;
  }[];
  revisions: {
    id: number;
    plan_id: number;
    reason: string;
    created_at: string;
  }[];
};
