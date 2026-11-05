import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { importProblem } from "../services/problems.ts";
import type { ProblemWriteInput } from "../types/problem.ts";
import { getErrorMessage } from "../utils/apiError.ts";

const emptyCase = { name: "自定义 1", input_data: "", expected_output: "", case_type: "custom" as const, is_public: false, note: "" };

export function ProblemImportPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<ProblemWriteInput>({
    title: "",
    description: "",
    source_platform: "南开大学校内 OJ",
    source_problem_id: "",
    source_url: "",
    input_description: "",
    output_description: "",
    sample_input: "",
    sample_output: "",
    constraints: "",
    note: "",
    status: "ready",
    test_cases: [],
  });
  const [warning, setWarning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function patch(partial: Partial<ProblemWriteInput>) {
    setForm((current) => ({ ...current, ...partial }));
  }

  async function submit(status: "draft" | "ready") {
    setSaving(true);
    setError(null);
    setWarning(null);
    try {
      const result = await importProblem({ ...form, status });
      if (result.duplicate_warning) {
        setWarning("已保存。题库里有相同标题的题目，请确认这不是重复粘贴。");
      }
      navigate(`/problems/${result.problem.id}`);
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "保存题目失败"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/problems" className="text-sm font-medium text-accent">返回题库</Link>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">导入题目</h1>
      <p className="mt-3 text-sm leading-6 text-muted">把题面和测试数据粘贴进来。这里不会访问 OJ，也不会调用 DeepSeek。</p>
      {error && <p className="mt-4 text-sm text-rose-700">{error}</p>}
      {warning && <p className="mt-4 text-sm text-amber-800">{warning}</p>}
      <form className="mt-6 space-y-4" onSubmit={(event) => event.preventDefault()}>
        <Section title="基本信息">
          <Field label="题目名称" value={form.title} onChange={(value) => patch({ title: value })} />
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="OJ 平台" value={form.source_platform} onChange={(value) => patch({ source_platform: value })} />
            <Field label="题目编号" value={form.source_problem_id} onChange={(value) => patch({ source_problem_id: value })} />
          </div>
          <Field label="原题链接" value={form.source_url} onChange={(value) => patch({ source_url: value })} />
        </Section>
        <Section title="题目描述">
          <Area label="题面" value={form.description} onChange={(value) => patch({ description: value })} rows={8} />
        </Section>
        <Section title="输入输出格式">
          <Area label="输入格式" value={form.input_description} onChange={(value) => patch({ input_description: value })} rows={3} />
          <Area label="输出格式" value={form.output_description} onChange={(value) => patch({ output_description: value })} rows={3} />
          <Area label="数据范围与约束" value={form.constraints} onChange={(value) => patch({ constraints: value })} rows={3} />
        </Section>
        <Section title="样例数据">
          <Area label="样例输入" value={form.sample_input} onChange={(value) => patch({ sample_input: value })} rows={4} mono />
          <Area label="样例输出" value={form.sample_output} onChange={(value) => patch({ sample_output: value })} rows={4} mono />
        </Section>
        <Section title="自定义测试数据">
          {form.test_cases.map((item, index) => (
            <div key={index} className="rounded-2xl border border-line p-3">
              <Field label="名称" value={item.name} onChange={(value) => updateCase(index, { name: value })} />
              <Area label="输入" value={item.input_data} onChange={(value) => updateCase(index, { input_data: value })} rows={3} mono />
              <Area label="预期输出" value={item.expected_output} onChange={(value) => updateCase(index, { expected_output: value })} rows={3} mono />
              <button type="button" className="mt-2 text-sm text-rose-700" onClick={() => patch({ test_cases: form.test_cases.filter((_, itemIndex) => itemIndex !== index) })}>
                移除这组
              </button>
            </div>
          ))}
          <button type="button" className="rounded-full border border-line px-4 py-2 text-sm" onClick={() => patch({ test_cases: [...form.test_cases, { ...emptyCase, name: `自定义 ${form.test_cases.length + 1}` }] })}>
            添加一组测试数据
          </button>
        </Section>
        <Section title="用户备注">
          <Area label="备注" value={form.note} onChange={(value) => patch({ note: value })} rows={3} />
        </Section>
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={saving} onClick={() => void submit("draft")} className="rounded-full border border-line bg-surface px-4 py-2 text-sm disabled:opacity-60">
            {saving ? "正在保存…" : "保存草稿"}
          </button>
          <button type="button" disabled={saving} onClick={() => void submit("ready")} className="rounded-full bg-accent px-4 py-2 text-sm text-on-accent disabled:opacity-60">
            {saving ? "正在保存…" : "正式导入"}
          </button>
        </div>
      </form>
    </div>
  );

  function updateCase(index: number, partial: Partial<ProblemWriteInput["test_cases"][number]>) {
    patch({ test_cases: form.test_cases.map((item, itemIndex) => (itemIndex === index ? { ...item, ...partial } : item)) });
  }
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-3xl border border-line bg-surface p-5">
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block text-sm text-muted">
      {label}
      <input value={value} onChange={(event) => onChange(event.target.value)} className="mt-1 w-full rounded-2xl border border-line px-3 py-2 text-ink" />
    </label>
  );
}

function Area({ label, value, onChange, rows, mono = false }: { label: string; value: string; onChange: (value: string) => void; rows: number; mono?: boolean }) {
  return (
    <label className="block text-sm text-muted">
      {label}
      <textarea value={value} rows={rows} onChange={(event) => onChange(event.target.value)} className={`mt-1 w-full rounded-2xl border border-line px-3 py-2 text-ink ${mono ? "font-mono" : ""}`} />
    </label>
  );
}
