import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { fetchQuiz, isQuizResult, submitQuiz } from "../services/quizzes.ts";
import type { QuestionType, QuizPaper, QuizResult } from "../types/quiz.ts";
import { getErrorMessage } from "../utils/apiError.ts";
import { formatDate } from "../utils/format.ts";

const typeLabels: Record<QuestionType, string> = {
  single: "单选题",
  multiple: "多选题",
  true_false: "判断题",
  short: "简答题",
  scenario: "场景题",
};

const difficultyLabels = {
  basic: "基础",
  medium: "中等",
  advanced: "提高",
};

export function QuizPage() {
  const params = useParams();
  const quizId = Number(params.quizId);
  const [paper, setPaper] = useState<QuizPaper | null>(null);
  const [result, setResult] = useState<QuizResult | null>(null);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [index, setIndex] = useState(0);
  const [reviewing, setReviewing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  useEffect(() => {
    if (!Number.isInteger(quizId) || quizId < 1) {
      return;
    }
    const id = requestId.current + 1;
    requestId.current = id;
    fetchQuiz(quizId)
      .then((data) => {
        if (requestId.current !== id) {
          return;
        }
        if (isQuizResult(data)) {
          setResult(data);
        } else {
          setPaper(data);
        }
        setError(null);
      })
      .catch((reason: unknown) => {
        if (requestId.current !== id) {
          return;
        }
        setError(getErrorMessage(reason, "读取检测失败"));
      })
      .finally(() => {
        if (requestId.current === id) {
          setLoading(false);
        }
      });
  }, [quizId]);

  const questions = paper?.questions ?? [];
  const current = questions[index];

  function setAnswer(questionId: number, value: string) {
    setAnswers((previous) => ({ ...previous, [questionId]: value }));
  }

  function toggleOption(questionId: number, key: string) {
    const selected = new Set((answers[questionId] ?? "").split(",").filter(Boolean));
    if (selected.has(key)) {
      selected.delete(key);
    } else {
      selected.add(key);
    }
    setAnswer(questionId, [...selected].sort().join(","));
  }

  async function handleSubmit() {
    if (!paper) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const next = await submitQuiz(
        paper.id,
        paper.questions.map((question) => ({
          question_id: question.id,
          answer: answers[question.id] ?? "",
        })),
      );
      setResult(next);
      setReviewing(false);
    } catch (reason) {
      setError(getErrorMessage(reason, "提交答卷失败"));
    } finally {
      setSubmitting(false);
    }
  }

  if (!Number.isInteger(quizId) || quizId < 1) {
    return <p className="text-sm text-rose-700">检测编号不正确。</p>;
  }

  return (
    <div className="mx-auto max-w-3xl">
      <p className="text-sm font-medium text-accent">知识检测</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">{result?.title ?? paper?.title ?? "本次检测"}</h1>
      {loading && <p className="mt-6 text-sm text-slate-500">正在读取题目…</p>}
      {error && !submitting && <p className="mt-4 text-sm text-rose-700">{error}</p>}
      {result && <ResultView result={result} />}
      {paper && current && !result && !reviewing && (
        <section className="mt-6">
          <div className="flex items-center justify-between text-sm text-slate-500">
            <span>
              {index + 1}/{questions.length}
            </span>
            <span>
              {typeLabels[current.question_type]} · {difficultyLabels[current.difficulty]}
            </span>
          </div>
          <div className="mt-3 h-2 rounded-full bg-slate-100">
            <div className="h-2 rounded-full bg-accent" style={{ width: `${((index + 1) / questions.length) * 100}%` }} />
          </div>
          <article className="mt-5 rounded-3xl border border-slate-200 bg-white p-5">
            <p className="text-sm text-slate-500">{current.knowledge_point_name}</p>
            <h2 className="mt-2 text-xl font-semibold leading-8">{current.stem}</h2>
            <AnswerEditor
              questionId={current.id}
              questionType={current.question_type}
              options={current.options}
              value={answers[current.id] ?? ""}
              onChange={setAnswer}
              onToggle={toggleOption}
            />
          </article>
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" disabled={index === 0} onClick={() => setIndex((value) => value - 1)} className="rounded-full border border-slate-200 px-4 py-2 text-sm disabled:opacity-40">
              上一题
            </button>
            {index < questions.length - 1 ? (
              <button type="button" onClick={() => setIndex((value) => value + 1)} className="rounded-full bg-ink px-4 py-2 text-sm font-medium text-white">
                下一题
              </button>
            ) : (
              <button type="button" onClick={() => setReviewing(true)} className="rounded-full bg-ink px-4 py-2 text-sm font-medium text-white">
                检查答案
              </button>
            )}
          </div>
        </section>
      )}
      {paper && reviewing && !result && (
        <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-5">
          <h2 className="text-xl font-semibold">提交前检查</h2>
          <ul className="mt-4 space-y-3">
            {paper.questions.map((question, questionIndex) => (
              <li key={question.id} className="rounded-2xl bg-mist px-4 py-3 text-sm">
                <p className="font-medium">
                  {questionIndex + 1}. {question.stem}
                </p>
                <p className="mt-1 text-slate-600">你的答案：{answers[question.id] || "还没有填写"}</p>
                <button type="button" onClick={() => { setIndex(questionIndex); setReviewing(false); }} className="mt-2 text-accent">
                  修改这道题
                </button>
              </li>
            ))}
          </ul>
          {error && <p className="mt-4 text-sm text-rose-700">{error}</p>}
          <button type="button" onClick={() => void handleSubmit()} disabled={submitting} className="mt-5 rounded-full bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
            {submitting ? "正在评分…" : "提交答卷"}
          </button>
        </section>
      )}
    </div>
  );
}

function AnswerEditor({
  questionId,
  questionType,
  options,
  value,
  onChange,
  onToggle,
}: {
  questionId: number;
  questionType: QuestionType;
  options: { key: string; text: string }[];
  value: string;
  onChange: (questionId: number, value: string) => void;
  onToggle: (questionId: number, key: string) => void;
}) {
  if (questionType === "short" || questionType === "scenario") {
    return (
      <textarea
        value={value}
        onChange={(event) => onChange(questionId, event.target.value)}
        rows={5}
        placeholder="用自己的话写出关键点"
        className="mt-4 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm"
      />
    );
  }
  const selected = new Set(value.split(",").filter(Boolean));
  return (
    <div className="mt-4 space-y-2">
      {options.map((option) => (
        <label key={option.key} className="flex cursor-pointer gap-3 rounded-2xl border border-slate-200 px-4 py-3 text-sm">
          <input
            type={questionType === "multiple" ? "checkbox" : "radio"}
            name={`question-${questionId}`}
            checked={selected.has(option.key)}
            onChange={() => {
              if (questionType === "multiple") {
                onToggle(questionId, option.key);
                return;
              }
              onChange(questionId, option.key);
            }}
          />
          <span>
            {option.key}. {option.text}
          </span>
        </label>
      ))}
    </div>
  );
}

function ResultView({ result }: { result: QuizResult }) {
  return (
    <section className="mt-6">
      <div className="rounded-3xl border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-500">本次检测</p>
        <p className="mt-2 text-3xl font-semibold">{result.score} 分</p>
        <p className="mt-2 text-sm text-slate-600">
          {result.level_label} · 答对 {result.correct_count} 题 · 答错 {result.wrong_count} 题
        </p>
        <p className="mt-3 text-sm leading-6 text-slate-600">{result.suggestion}</p>
        <p className="mt-3 text-sm text-slate-500">这次分数只说明本次检测。长期掌握度会结合历史成绩逐步调整，一次高分不会直接记成熟练掌握。</p>
      </div>
      {result.reviews && result.reviews.length > 0 && (
        <ul className="mt-4 space-y-2">
          {result.reviews.map((item) => (
            <li key={item.id} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm">
              <p className="font-medium">
                {item.name} · {item.interval_days} 天后复习 · {formatDate(item.next_review_date)}
              </p>
              <p className="mt-1 text-slate-600">{item.reason}</p>
              <p className="mt-1 text-slate-500">{item.risk_reason}</p>
            </li>
          ))}
        </ul>
      )}
      {result.mastery_updates.length > 0 && (
        <ul className="mt-4 space-y-2">
          {result.mastery_updates.map((item) => (
            <li key={item.knowledge_point_id} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm">
              <p className="font-medium">
                {item.name} · {item.status_label} · {item.new_level}
              </p>
              <p className="mt-1 text-slate-600">{item.reason}</p>
            </li>
          ))}
        </ul>
      )}
      <ol className="mt-4 space-y-3">
        {result.questions.map((question, questionIndex) => (
          <li key={question.id} className="rounded-3xl border border-slate-200 bg-white p-5 text-sm leading-6">
            <p className="text-slate-500">
              {questionIndex + 1}. {question.is_correct ? "正确" : "需要再看"} · {question.score} 分
            </p>
            <p className="mt-2 font-medium text-base">{question.stem}</p>
            <p className="mt-2 text-slate-600">你的答案：{question.user_answer || "未作答"}</p>
            <p>正确答案：{question.correct_answer}</p>
            <p className="text-slate-600">{question.explanation}</p>
            {question.error_reason && <p className="text-rose-700">错误原因：{question.error_reason}</p>}
            {question.suggestion && <p className="text-slate-600">建议：{question.suggestion}</p>}
          </li>
        ))}
      </ol>
      <div className="mt-5 flex gap-4 text-sm font-medium">
        <Link to="/reviews" className="text-accent">
          查看复习安排
        </Link>
        <Link to="/progress" className="text-accent">
          查看知识掌握
        </Link>
      </div>
    </section>
  );
}
