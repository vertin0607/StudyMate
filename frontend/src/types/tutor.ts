export type TutorPoint = {
  id: number;
  name: string;
  mastery_level: number | null;
  mastery_assessed: boolean;
  status_label: string;
  latest_score: number | null;
  weak_points: string[];
};

export type TutorMessage = {
  id: number;
  session_id: number;
  role: "user" | "assistant";
  content: string;
  knowledge_point_ids: number[];
  created_at: string;
};

export type TutorSessionSummary = {
  id: number;
  title: string;
  goal_id: number | null;
  goal_title: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
};

export type TutorSessionDetail = TutorSessionSummary & {
  points: TutorPoint[];
  messages: TutorMessage[];
};

export type TutorReply = {
  user_message: TutorMessage;
  assistant_message: TutorMessage;
};
