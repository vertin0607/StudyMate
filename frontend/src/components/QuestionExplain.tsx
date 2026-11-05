import { useState } from "react";

import { TutorMarkdown } from "./TutorMarkdown.tsx";
import { explainQuizQuestion } from "../services/quizzes.ts";
import { getErrorMessage } from "../utils/apiError.ts";

export function QuestionExplain({ quizId, questionId }: { quizId: number; questionId: number }) {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await explainQuizQuestion(quizId, questionId);
      setContent(data.content);
      setOpen(true);
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "生成讲解失败"));
      setOpen(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => {
          if (content) {
            setOpen((value) => !value);
            return;
          }
          void load();
        }}
        disabled={loading}
        className="rounded-full border border-line px-4 py-2 text-sm disabled:opacity-60"
      >
        {loading ? "正在生成讲解…" : content ? (open ? "收起 AI 讲解" : "展开 AI 讲解") : "AI 讲解"}
      </button>
      {open && error && (
        <div className="mt-3 text-sm text-rose-700">
          <p>{error}</p>
          <button type="button" onClick={() => void load()} className="mt-2 rounded-full bg-accent px-4 py-2 text-on-accent">
            重试
          </button>
        </div>
      )}
      {open && content && (
        <div className="mt-3 rounded-2xl border border-line bg-soft px-4 py-3">
          <TutorMarkdown content={content} />
        </div>
      )}
    </div>
  );
}
