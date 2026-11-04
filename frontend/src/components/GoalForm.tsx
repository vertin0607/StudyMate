import { useState, type FormEvent } from "react";

import type { GoalInput } from "../types/goal.ts";

type GoalFormProps = {
  initial: GoalInput;
  submitLabel: string;
  submitting: boolean;
  error: string | null;
  onSubmit: (value: GoalInput) => void;
  onCancel: () => void;
};

type FormState = {
  title: string;
  description: string;
  target_date: string;
  daily_minutes: string;
};

function toFormState(initial: GoalInput): FormState {
  return {
    title: initial.title,
    description: initial.description,
    target_date: initial.target_date,
    daily_minutes: initial.daily_minutes > 0 ? String(initial.daily_minutes) : "",
  };
}

function validate(form: FormState): string | null {
  if (!form.title.trim()) {
    return "学习目标名称不能为空";
  }
  if (!form.description.trim()) {
    return "目标描述不能为空";
  }
  if (!form.target_date) {
    return "请选择预计完成日期";
  }
  const minutes = Number(form.daily_minutes);
  if (!Number.isInteger(minutes) || minutes < 1 || minutes > 720) {
    return "每日学习时间需要在 1 到 720 分钟之间";
  }
  return null;
}

const fieldClass =
  "mt-2 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-ink outline-none transition focus:border-accent";

export function GoalForm({ initial, submitLabel, submitting, error, onSubmit, onCancel }: GoalFormProps) {
  const [form, setForm] = useState<FormState>(() => toFormState(initial));
  const [localError, setLocalError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = validate(form);
    if (message) {
      setLocalError(message);
      return;
    }
    setLocalError(null);
    onSubmit({
      title: form.title.trim(),
      description: form.description.trim(),
      target_date: form.target_date,
      daily_minutes: Number(form.daily_minutes),
    });
  }

  const visibleError = localError ?? error;

  return (
    <form onSubmit={handleSubmit} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="block text-sm font-medium text-slate-700 md:col-span-2">
          学习目标名称
          <input
            value={form.title}
            onChange={(event) => setForm({ ...form, title: event.target.value })}
            maxLength={80}
            className={fieldClass}
            placeholder="例如：DeCLIP 研究学习"
          />
        </label>
        <label className="block text-sm font-medium text-slate-700 md:col-span-2">
          目标描述
          <textarea
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
            maxLength={2000}
            rows={4}
            className={fieldClass}
            placeholder="写下你希望学会什么"
          />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          预计完成日期
          <input
            type="date"
            value={form.target_date}
            onChange={(event) => setForm({ ...form, target_date: event.target.value })}
            className={fieldClass}
          />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          每日学习时间（分钟）
          <input
            type="number"
            min={1}
            max={720}
            step={1}
            value={form.daily_minutes}
            onChange={(event) => setForm({ ...form, daily_minutes: event.target.value })}
            className={fieldClass}
            placeholder="例如 25"
          />
        </label>
      </div>
      {visibleError && (
        <p className="mt-4 text-sm leading-6 text-rose-700" role="alert">
          {visibleError}
        </p>
      )}
      <div className="mt-5 flex flex-wrap gap-3">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-full bg-ink px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "正在保存…" : submitLabel}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={submitting}
          className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-60"
        >
          取消
        </button>
      </div>
    </form>
  );
}
