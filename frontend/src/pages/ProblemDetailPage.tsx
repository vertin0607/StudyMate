import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ConfirmDialog } from "../components/ConfirmDialog.tsx";
import { ProblemMarkdown } from "../components/ProblemMarkdown.tsx";
import { PracticePanel } from "../components/PracticePanel.tsx";
import { ProblemWorkspace } from "../components/ProblemWorkspace.tsx";
import {
  addTestCase,
  analyzeProblem,
  confirmTopic,
  deleteProblem,
  deleteTestCase,
  fetchProblem,
  fetchTopics,
  saveClassification,
  saveProblemNote,
  updateProblem,
  updateTestCase,
} from "../services/problems.ts";
import type { ProblemDetail, ProblemTestCase, TopicGroup } from "../types/problem.ts";
import { getErrorMessage } from "../utils/apiError.ts";

const difficultyLabels: Record<string, string> = { unknown: "未设置", easy: "简单", medium: "中等", hard: "困难" };

export function ProblemDetailPage() {
  const params = useParams();
  const problemId = Number(params.problemId);
  const navigate = useNavigate();
  const [problem, setProblem] = useState<ProblemDetail | null>(null);
  const [topics, setTopics] = useState<TopicGroup[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const requestId = useRef(0);

  useEffect(() => {
    if (!Number.isInteger(problemId) || problemId < 1) {
      return;
    }
    const id = requestId.current + 1;
    requestId.current = id;
    Promise.all([fetchProblem(problemId), fetchTopics()])
      .then(([detail, groups]) => {
        if (requestId.current !== id) {
          return;
        }
        setProblem(detail);
        setTopics(groups);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (requestId.current !== id) {
          return;
        }
        setError(getErrorMessage(reason, "读取题目失败"));
      })
      .finally(() => {
        if (requestId.current === id) {
          setLoading(false);
        }
      });
  }, [problemId]);

  async function analyze() {
    setAnalyzing(true);
    setError(null);
    try {
      setProblem(await analyzeProblem(problemId));
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "分析失败，原题和测试数据仍保留"));
      const latest = await fetchProblem(problemId).catch(() => null);
      if (latest) {
        setProblem(latest);
      }
    } finally {
      setAnalyzing(false);
    }
  }

  async function remove() {
    setDeleting(true);
    try {
      await deleteProblem(problemId);
      navigate("/problems");
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "删除题目失败"));
      setDeleting(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-slate-500">正在读取题目…</p>;
  }
  if (!problem) {
    return <p className="text-sm text-rose-700">{error ?? "题目不存在"}</p>;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/problems" className="text-sm font-medium text-accent">返回题库</Link>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">{problem.title}</h1>
          <p className="mt-2 text-sm text-slate-600">
            {problem.source_platform}
            {problem.source_problem_id ? ` · ${problem.source_problem_id}` : ""}
            {problem.source_url ? ` · ${problem.source_url}` : ""}
          </p>
        </div>
        <button type="button" onClick={() => setConfirmDelete(true)} className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm">
          删除题目
        </button>
      </div>
      {error && <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
      <ProblemTextEditor problem={problem} onChange={setProblem} />
      <section className="max-h-[32rem] overflow-y-auto rounded-3xl border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-semibold">原始题目</h2>
        <div className="mt-3"><ProblemMarkdown content={problem.description || "还没有题面。"} /></div>
        {problem.input_description && <Block title="输入格式" text={problem.input_description} />}
        {problem.output_description && <Block title="输出格式" text={problem.output_description} />}
        {problem.constraints && <Block title="数据范围" text={problem.constraints} />}
        {problem.sample_input && <Block title="样例输入" text={problem.sample_input} mono />}
        {problem.sample_output && <Block title="样例输出" text={problem.sample_output} mono />}
      </section>
      <ProblemWorkspace key={problem.id} problemId={problem.id} />
      <PracticePanel key={`practice-${problem.id}`} problemId={problem.id} />
      <section className="rounded-3xl border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">AI 分析</h2>
          <button type="button" onClick={() => void analyze()} disabled={analyzing} className="rounded-full bg-ink px-4 py-2 text-sm text-white disabled:opacity-60">
            {analyzing ? "正在分析…" : "AI 分析题目"}
          </button>
        </div>
        {problem.analysis_status === "failed" && <p className="mt-3 text-sm text-rose-700">{problem.analysis_error || "分析失败，可以重新分析。"}</p>}
        {problem.analysis_status === "pending" && <p className="mt-3 text-sm text-slate-500">这道题还没有分析。</p>}
        {problem.analysis && <AnalysisView analysis={problem.analysis} problemId={problemId} onChange={setProblem} />}
        <ClassificationEditor key={`${problem.updated_at}-${problem.topics.map((item) => item.topic_id).join("-")}`} problem={problem} topics={topics} onChange={setProblem} />
      </section>
      <TestCaseEditor problem={problem} onChange={setProblem} />
      <NoteEditor key={problem.note_record.updated_at ?? "empty-note"} problem={problem} onChange={setProblem} />
      {confirmDelete && (
        <ConfirmDialog
          title="删除这道题目"
          description="题目、测试数据、代码草稿、提交记录、练习记录、错题标记、分类关联和笔记会一起删除。学习目标和掌握度不会改变。"
          confirmLabel={deleting ? "正在删除…" : "删除"}
          busy={deleting}
          onCancel={() => setConfirmDelete(false)}
          onConfirm={() => void remove()}
        />
      )}
    </div>
  );
}

function ProblemTextEditor({ problem, onChange }: { problem: ProblemDetail; onChange: (problem: ProblemDetail) => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(problem.title);
  const [description, setDescription] = useState(problem.description);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      onChange(await updateProblem(problem.id, {
        title,
        description,
        source_platform: problem.source_platform,
        source_problem_id: problem.source_problem_id,
        source_url: problem.source_url,
        input_description: problem.input_description,
        output_description: problem.output_description,
        sample_input: problem.sample_input,
        sample_output: problem.sample_output,
        constraints: problem.constraints,
        note: problem.note,
        status: problem.status === "draft" ? "draft" : "ready",
        test_cases: [],
      }));
      setOpen(false);
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "保存题目失败"));
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return <button type="button" onClick={() => setOpen(true)} className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm">编辑题面</button>;
  }
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5">
      <h2 className="text-lg font-semibold">编辑题面</h2>
      <p className="mt-1 text-sm text-slate-500">这里只改题目原文。已经单独保存的测试数据不会被这次保存覆盖。</p>
      {error && <p className="mt-2 text-sm text-rose-700">{error}</p>}
      <input value={title} onChange={(event) => setTitle(event.target.value)} className="mt-3 w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm" />
      <textarea value={description} rows={8} onChange={(event) => setDescription(event.target.value)} className="mt-2 w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm" />
      <div className="mt-3 flex gap-2">
        <button type="button" onClick={() => void save()} disabled={saving} className="rounded-full bg-ink px-4 py-2 text-sm text-white disabled:opacity-60">{saving ? "正在保存…" : "保存题面"}</button>
        <button type="button" onClick={() => setOpen(false)} className="rounded-full border border-slate-200 px-4 py-2 text-sm">取消</button>
      </div>
    </section>
  );
}

function Block({ title, text, mono = false }: { title: string; text: string; mono?: boolean }) {
  return (
    <div className="mt-4">
      <h3 className="text-sm font-medium text-slate-500">{title}</h3>
      <pre className={mono ? "io-block mt-2" : "mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700"}>{text}</pre>
    </div>
  );
}

function AnalysisView({
  analysis,
  problemId,
  onChange,
}: {
  analysis: NonNullable<ProblemDetail["analysis"]>;
  problemId: number;
  onChange: (problem: ProblemDetail) => void;
}) {
  return (
    <div className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
      <p>课程：{analysis.course} · 难度：{difficultyLabels[analysis.difficulty] ?? analysis.difficulty}</p>
      <p>算法类型：{analysis.algorithm_types.join("、")}</p>
      <p>核心能力：{analysis.core_abilities.join("、")}</p>
      <p>{analysis.solution_idea}</p>
      <ol className="list-decimal pl-5">{analysis.algorithm_steps.map((step) => <li key={step}>{step}</li>)}</ol>
      <p>时间复杂度 {analysis.time_complexity}，空间复杂度 {analysis.space_complexity}。</p>
      <p>{analysis.complexity_reason}</p>
      <p>易错点：{analysis.common_mistakes.join("；")}</p>
      <p>复习建议：{analysis.review_suggestions.join("；")}</p>
      {analysis.suggested_new_topics.length > 0 && (
        <div>
          <p className="font-medium">建议新增的知识点</p>
          {analysis.suggested_new_topics.map((item) => (
            <button
              key={item.name}
              type="button"
              className="mt-2 mr-2 rounded-full border border-slate-200 px-3 py-1"
              onClick={() => {
                void confirmTopic(problemId, item.name, item.relevance, item.reason).then(onChange);
              }}
            >
              确认添加 {item.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ClassificationEditor({ problem, topics, onChange }: { problem: ProblemDetail; topics: TopicGroup[]; onChange: (problem: ProblemDetail) => void }) {
  const [course, setCourse] = useState(problem.course);
  const [difficulty, setDifficulty] = useState(problem.difficulty);
  const [links, setLinks] = useState(problem.topics);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggle(topicId: number, name: string) {
    setLinks((current) => {
      const exists = current.some((item) => item.topic_id === topicId);
      if (exists) {
        return current.filter((item) => item.topic_id !== topicId);
      }
      return [...current, { id: 0, topic_id: topicId, name, relevance: "secondary", reason: "" }];
    });
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      onChange(await saveClassification(problem.id, {
        course,
        difficulty,
        links: links.map((item) => ({ topic_id: item.topic_id, relevance: item.relevance, reason: item.reason })),
      }));
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "保存分类失败"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mt-5 border-t border-slate-100 pt-4">
      <h3 className="text-sm font-semibold">手动调整分类</h3>
      <p className="mt-1 text-sm text-slate-500">保存后，再次分析不会覆盖你改过的课程、难度和知识点。</p>
      {error && <p className="mt-2 text-sm text-rose-700">{error}</p>}
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <input value={course} onChange={(event) => setCourse(event.target.value)} placeholder="课程" className="rounded-2xl border border-slate-200 px-3 py-2 text-sm" />
        <select value={difficulty} onChange={(event) => setDifficulty(event.target.value)} className="rounded-2xl border border-slate-200 px-3 py-2 text-sm">
          <option value="unknown">未设置</option>
          <option value="easy">简单</option>
          <option value="medium">中等</option>
          <option value="hard">困难</option>
        </select>
      </div>
      <ul className="mt-3 space-y-2">
        {topics.flatMap((group) => group.topics).map((topic) => {
          const selected = links.find((item) => item.topic_id === topic.id);
          return (
            <li key={topic.id} className="flex flex-wrap items-center gap-2 text-sm">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={Boolean(selected)} onChange={() => toggle(topic.id, topic.name)} />
                {topic.name}
              </label>
              {selected && (
                <select
                  value={selected.relevance}
                  onChange={(event) => setLinks((current) => current.map((item) => item.topic_id === topic.id ? { ...item, relevance: event.target.value as "primary" | "secondary" } : item))}
                  className="rounded-full border border-slate-200 px-2 py-1"
                >
                  <option value="primary">主要考点</option>
                  <option value="secondary">次要考点</option>
                </select>
              )}
            </li>
          );
        })}
      </ul>
      <button type="button" onClick={() => void save()} disabled={saving} className="mt-3 rounded-full border border-slate-200 px-4 py-2 text-sm disabled:opacity-60">
        {saving ? "正在保存…" : "保存分类"}
      </button>
    </div>
  );
}

function TestCaseEditor({ problem, onChange }: { problem: ProblemDetail; onChange: (problem: ProblemDetail) => void }) {
  const [draft, setDraft] = useState({ name: "新测试", input_data: "", expected_output: "", note: "" });
  const [editing, setEditing] = useState<ProblemTestCase | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    onChange(await fetchProblem(problem.id));
  }

  async function createCase() {
    setError(null);
    try {
      await addTestCase(problem.id, { ...draft, case_type: "custom", is_public: false });
      setDraft({ name: "新测试", input_data: "", expected_output: "", note: "" });
      await refresh();
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "添加测试数据失败"));
    }
  }

  async function saveEdit() {
    if (!editing) {
      return;
    }
    setError(null);
    try {
      await updateTestCase(problem.id, editing.id, editing);
      setEditing(null);
      await refresh();
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "保存测试数据失败"));
    }
  }

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5">
      <h2 className="text-lg font-semibold">测试数据</h2>
      <p className="mt-1 text-sm text-slate-500">输入和输出按原文保存。编辑时先写入下方文本框，确认后再保存。</p>
      {error && <p className="mt-2 text-sm text-rose-700">{error}</p>}
      <ul className="mt-4 space-y-3">
        {problem.test_cases.map((item) => (
          <li key={item.id} className="rounded-2xl bg-mist p-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-medium">{item.name} · {item.case_type === "sample" ? "样例" : "自定义"} · {item.is_public ? "公开" : "不公开"}</p>
              <div className="flex gap-2">
                <button type="button" className="text-accent" onClick={() => setEditing(item)}>编辑</button>
                <button type="button" className="text-rose-700" onClick={() => void deleteTestCase(problem.id, item.id).then(refresh)}>删除</button>
              </div>
            </div>
            <pre className="io-block mt-2">{item.input_data || "（空输入）"}</pre>
            <pre className="io-block mt-2">{item.expected_output || "（空输出）"}</pre>
          </li>
        ))}
      </ul>
      {editing && (
        <div className="mt-4 rounded-2xl border border-slate-200 p-3">
          <p className="text-sm font-medium">正在编辑 {editing.name}。离开页面前请先保存，否则这次修改只留在当前页面。</p>
          <textarea value={editing.input_data} rows={4} onChange={(event) => setEditing({ ...editing, input_data: event.target.value })} className="mt-2 w-full rounded-2xl border border-slate-200 px-3 py-2 font-mono text-sm" />
          <textarea value={editing.expected_output} rows={4} onChange={(event) => setEditing({ ...editing, expected_output: event.target.value })} className="mt-2 w-full rounded-2xl border border-slate-200 px-3 py-2 font-mono text-sm" />
          <button type="button" onClick={() => void saveEdit()} className="mt-2 rounded-full bg-ink px-4 py-2 text-sm text-white">保存这组测试数据</button>
        </div>
      )}
      <div className="mt-4 grid gap-2">
        <input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} className="rounded-2xl border border-slate-200 px-3 py-2 text-sm" />
        <textarea value={draft.input_data} rows={3} placeholder="输入数据" onChange={(event) => setDraft({ ...draft, input_data: event.target.value })} className="rounded-2xl border border-slate-200 px-3 py-2 font-mono text-sm" />
        <textarea value={draft.expected_output} rows={3} placeholder="预期输出" onChange={(event) => setDraft({ ...draft, expected_output: event.target.value })} className="rounded-2xl border border-slate-200 px-3 py-2 font-mono text-sm" />
        <button type="button" onClick={() => void createCase()} className="rounded-full border border-slate-200 px-4 py-2 text-sm">添加测试数据</button>
      </div>
    </section>
  );
}

function NoteEditor({ problem, onChange }: { problem: ProblemDetail; onChange: (problem: ProblemDetail) => void }) {
  const [content, setContent] = useState(problem.note_record.content);
  const [idea, setIdea] = useState(problem.note_record.solution_idea);
  const [saving, setSaving] = useState(false);

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5">
      <h2 className="text-lg font-semibold">个人学习记录</h2>
      <p className="mt-1 text-sm text-slate-500">做题记录会在后续阶段接入。这里先保存笔记和你自己的思路。</p>
      <textarea value={content} rows={4} onChange={(event) => setContent(event.target.value)} placeholder="笔记" className="mt-3 w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm" />
      <textarea value={idea} rows={4} onChange={(event) => setIdea(event.target.value)} placeholder="个人解题思路" className="mt-2 w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm" />
      <button
        type="button"
        disabled={saving}
        onClick={() => {
          setSaving(true);
          void saveProblemNote(problem.id, content, idea)
            .then(() => fetchProblem(problem.id))
            .then(onChange)
            .finally(() => setSaving(false));
        }}
        className="mt-3 rounded-full bg-ink px-4 py-2 text-sm text-white disabled:opacity-60"
      >
        {saving ? "正在保存…" : "保存笔记"}
      </button>
    </section>
  );
}
