export type GoalStatus = "active" | "paused" | "completed";

/** 与后端 GoalRead 一致，使用接口里的字段名。 */
export type Goal = {
  id: number;
  user_id: number;
  title: string;
  description: string;
  target_date: string;
  daily_minutes: number;
  status: GoalStatus;
  created_at: string;
  updated_at: string;
};

export type GoalInput = {
  title: string;
  description: string;
  target_date: string;
  daily_minutes: number;
};

export const emptyGoalInput: GoalInput = {
  title: "",
  description: "",
  target_date: "",
  daily_minutes: 0,
};
