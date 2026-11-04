import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { fetchProblemsByTopic, fetchTopics } from "../services/problems.ts";
import type { ProblemSummary, TopicGroup } from "../types/problem.ts";
import { getErrorMessage } from "../utils/apiError.ts";

export function ProblemTopicsPage() {
  const [groups, setGroups] = useState<TopicGroup[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [problems, setProblems] = useState<ProblemSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  useEffect(() => {
    const id = requestId.current + 1;
    requestId.current = id;
    fetchTopics()
      .then((data) => {
        if (requestId.current === id) {
          setGroups(data);
        }
      })
      .catch((reason: unknown) => {
        if (requestId.current === id) {
          setError(getErrorMessage(reason, "读取分类失败"));
        }
      });
  }, []);

  async function choose(topicId: number, name: string) {
    setSelected(topicId);
    setTitle(name);
    setError(null);
    try {
      const data = await fetchProblemsByTopic(topicId);
      setProblems(data.problems);
    } catch (reason: unknown) {
      setError(getErrorMessage(reason, "读取题目失败"));
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <Link to="/problems" className="text-sm font-medium text-accent">返回题库</Link>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">知识点分类</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">分类来自固定目录。新的名称需要你在题目详情里确认后才会出现。</p>
      {error && <p className="mt-4 text-sm text-rose-700">{error}</p>}
      <div className="mt-6 grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="space-y-4">
          {groups.map((group) => (
            <section key={group.name} className="rounded-3xl border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-semibold">{group.name}</h2>
              <ul className="mt-2 space-y-1">
                {group.topics.map((topic) => (
                  <li key={topic.id}>
                    <button type="button" onClick={() => void choose(topic.id, topic.name)} className={`w-full rounded-xl px-3 py-2 text-left text-sm ${selected === topic.id ? "bg-accent-soft" : ""}`}>
                      {topic.name}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
        <section className="rounded-3xl border border-slate-200 bg-white p-5">
          {!selected && <p className="text-sm text-slate-600">选择左侧的知识点后，这里显示关联题目。</p>}
          {selected && <h2 className="text-lg font-semibold">{title}</h2>}
          {selected && problems.length === 0 && <p className="mt-3 text-sm text-slate-500">这个知识点下还没有题目。</p>}
          <ul className="mt-3 space-y-2">
            {problems.map((problem) => (
              <li key={problem.id}>
                <Link to={`/problems/${problem.id}`} className="text-sm font-medium text-accent">{problem.title}</Link>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
