export type QuestionExplanation = {
  question_id: number;
  quiz_id: number;
  content: string;
  created_at: string;
};

export type KnowledgeExplainMessage = {
  id: number;
  role: "user" | "assistant" | string;
  content: string;
  created_at: string;
};

export type KnowledgeExplainSession = {
  session_id: number | null;
  knowledge_point_id: number;
  name: string;
  messages: KnowledgeExplainMessage[];
};
