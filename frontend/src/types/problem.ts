export type ProblemTopicLink = {
  id: number;
  topic_id: number;
  name: string;
  relevance: "primary" | "secondary";
  reason: string;
};

export type ProblemSummary = {
  id: number;
  title: string;
  source_platform: string;
  source_problem_id: string;
  source_url: string;
  difficulty: string;
  course: string;
  status: string;
  analysis_status: string;
  learning_status?: string;
  created_at: string;
  updated_at: string;
  topics: ProblemTopicLink[];
};

export type ProblemTestCase = {
  id: number;
  problem_id: number;
  name: string;
  input_data: string;
  expected_output: string;
  case_type: "sample" | "custom";
  is_public: boolean;
  note: string;
};

export type ProblemAnalysis = {
  course: string;
  difficulty: string;
  solution_idea: string;
  algorithm_steps: string[];
  algorithm_types: string[];
  core_abilities: string[];
  time_complexity: string;
  space_complexity: string;
  complexity_reason: string;
  common_mistakes: string[];
  review_suggestions: string[];
  suggested_new_topics: { name: string; relevance: "primary" | "secondary"; reason: string }[];
};

export type ProblemDetail = ProblemSummary & {
  description: string;
  input_description: string;
  output_description: string;
  sample_input: string;
  sample_output: string;
  constraints: string;
  note: string;
  analysis_error: string;
  classification_locked: boolean;
  analysis: ProblemAnalysis | null;
  test_cases: ProblemTestCase[];
  note_record: { content: string; solution_idea: string; updated_at: string | null };
};

export type ProblemStatistics = {
  total: number;
  analyzed: number;
  pending: number;
  failed: number;
  passed: number;
  to_review: number;
};

export type TopicGroup = {
  name: string;
  topics: { id: number; name: string; category: string }[];
};

export type ProblemWriteInput = {
  title: string;
  description: string;
  source_platform: string;
  source_problem_id: string;
  source_url: string;
  input_description: string;
  output_description: string;
  sample_input: string;
  sample_output: string;
  constraints: string;
  note: string;
  status: "draft" | "ready";
  test_cases: {
    name: string;
    input_data: string;
    expected_output: string;
    case_type: "sample" | "custom";
    is_public: boolean;
    note: string;
  }[];
};
