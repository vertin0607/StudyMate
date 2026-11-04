import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import type { DiagnosisEvidence, DiagnosisItem, DiagnosisReport, GrowthChange, GrowthEvidence } from "../../types/growth.ts";
import { formatDate } from "../../utils/format.ts";
import { categoryLabels, diagnosisStatusLabels, localDateKey } from "../../utils/growthDisplay.ts";

export function WeaknessEvolution({
  diagnosis,
  improved,
  stillPresent,
  note,
}: {
  diagnosis: DiagnosisReport;
  improved: GrowthChange[];
  stillPresent: GrowthChange[];
  note: string;
}) {
  const flat = Object.values(diagnosis.by_category).flat();
  const ongoing = flat.filter((item) => item.status === "confirmed" || item.status === "suspected");
  const unknown = flat.filter((item) => item.status === "insufficient_data");
  const ongoingCards = [
    ...ongoing.map((item, index) => (
      <DiagnosisCard key={`${item.category}-${item.knowledge_point_id ?? "topic"}-${index}`} item={item} />
    )),
    ...stillPresent.map((item) => <ChangeCard key={`still-${item.subject}-${item.name}-${item.later.id}`} item={item} />),
  ];
  return (
    <div className="space-y-6">
      <p className="text-sm leading-6 text-slate-500">{note} 完成训练建议不会把薄弱点标成已改善。</p>
      <Group title="持续存在的薄弱点" empty="目前没有已确认、初步发现，或最近一次仍未通过的记录。">
        {ongoingCards}
      </Group>
      <Group title="已经改善的薄弱点" empty="还没有同一知识点或同一题目的前后证据可以标成已改善。">
        {improved.map((item) => (
          <ChangeCard key={`${item.subject}-${item.name}-${item.later.id}`} item={item} />
        ))}
      </Group>
      <Group title="证据不足" empty="没有证据不足的诊断项。">
        {unknown.length > 0 ? (
          <details className="rounded-2xl border border-slate-200 px-4 py-3 text-sm">
            <summary className="cursor-pointer font-medium">证据不足 {unknown.length} 项</summary>
            <ul className="mt-3 space-y-3">
              {unknown.map((item, index) => (
                <DiagnosisCard key={`unknown-${item.category}-${index}`} item={item} />
              ))}
            </ul>
          </details>
        ) : null}
      </Group>
    </div>
  );
}

function Group({ title, empty, children }: { title: string; empty: string; children: ReactNode }) {
  const list = Array.isArray(children) ? children : [children];
  const present = list.some(Boolean);
  return (
    <div>
      <h3 className="text-sm font-semibold">{title}</h3>
      {present ? <div className="mt-2 space-y-2">{children}</div> : <p className="mt-2 text-sm text-slate-500">{empty}</p>}
    </div>
  );
}

function DiagnosisCard({ item }: { item: DiagnosisItem }) {
  const [open, setOpen] = useState(false);
  const name = item.knowledge_point_name || item.problem_topics.map((topic) => topic.name).join("、") || "未命名";
  return (
    <article className="rounded-2xl border border-slate-200 px-4 py-3 text-sm">
      <p className="font-medium">{name}</p>
      <p className="mt-1 text-slate-500">
        {categoryLabels[item.category] ?? item.category} · {diagnosisStatusLabels[item.status] ?? item.status}
      </p>
      <p className="mt-2 leading-6 text-slate-600">{item.reason}</p>
      <button type="button" onClick={() => setOpen((value) => !value)} className="mt-2 font-medium text-accent">
        {open ? "收起证据" : "查看证据"}
      </button>
      {open ? <EvidenceList evidence={item.evidence} /> : null}
    </article>
  );
}

function ChangeCard({ item }: { item: GrowthChange }) {
  const same = item.earlier.id === item.later.id && item.earlier.source === item.later.source;
  const improved = item.status === "improved";
  return (
    <article className="rounded-2xl border border-slate-200 px-4 py-3 text-sm">
      <p className="font-medium">{item.name}</p>
      <p className="mt-1 text-slate-500">
        {item.subject === "problem" ? "同一道题" : "同一个知识点"} · {improved ? "已改善" : "最近一次仍未通过"}
      </p>
      {same && !improved ? (
        <p className="mt-2 leading-6 text-slate-600">目前的失败记录：{describeEvidence(item.later)} 最近一次结果仍未通过，所以不算已改善。</p>
      ) : (
        <>
          <p className="mt-2 leading-6 text-slate-600">之前：{describeEvidence(item.earlier)}</p>
          <p className="mt-1 leading-6 text-slate-600">{improved ? "之后" : "最近一次"}：{describeEvidence(item.later)}</p>
        </>
      )}
      {item.problem_id ? (
        <Link to={`/problems/${item.problem_id}`} className="mt-2 inline-block font-medium text-accent">
          打开题目
        </Link>
      ) : null}
    </article>
  );
}

function EvidenceList({ evidence }: { evidence: DiagnosisEvidence[] }) {
  if (evidence.length === 0) {
    return <p className="mt-2 text-slate-500">这条诊断没有附带证据明细。</p>;
  }
  return (
    <ul className="mt-2 space-y-2">
      {evidence.map((item, index) => (
        <li key={`${item.type ?? "evidence"}-${index}`} className="rounded-xl bg-mist px-3 py-2 leading-6 text-slate-600">
          <p>{describeDiagnosisEvidence(item)}</p>
          {typeof item.problem_id === "number" ? (
            <Link to={`/problems/${item.problem_id}`} className="font-medium text-accent">
              打开题目
            </Link>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function describeEvidence(evidence: GrowthEvidence): string {
  const when = formatDate(evidence.date);
  if (evidence.source === "quiz") {
    return `${when} 检测 ${evidence.quiz_score ?? "—"} 分。这条记录没有检测编号，所以不跳转报告。`;
  }
  if (evidence.source === "review") {
    return `${when} 复习结果 ${evidence.review_result ?? "—"}，分数 ${evidence.score ?? "—"}。`;
  }
  if (evidence.source === "judge") {
    return `${when} 本地判题 ${evidence.judge_status ?? "—"}。`;
  }
  return when;
}

function describeDiagnosisEvidence(item: DiagnosisEvidence): string {
  const pieces = [item.type ?? "记录"];
  if (typeof item.score === "number") {
    pieces.push(`${item.score} 分`);
  }
  if (item.at) {
    pieces.push(formatDate(localDateKey(item.at)));
  }
  if (item.below_60) {
    pieces.push("低于 60 分");
  }
  if (item.status) {
    pieces.push(item.status);
  }
  return pieces.join(" · ");
}
