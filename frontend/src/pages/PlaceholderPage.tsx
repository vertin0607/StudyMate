type PlaceholderPageProps = {
  title: string;
  phase: string;
  summary: string;
};

/** 只说明该页面将在哪一阶段实现，不展示虚构的学习数据。 */
export function PlaceholderPage({ title, phase, summary }: PlaceholderPageProps) {
  return (
    <section className="mx-auto max-w-3xl">
      <p className="text-sm font-medium text-accent">{phase}</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">{title}</h1>
      <p className="mt-4 max-w-2xl text-base leading-7 text-muted">{summary}</p>
      <div className="mt-8 rounded-3xl border border-dashed border-line bg-surface px-6 py-10 text-sm leading-6 text-muted">
        路由已经可以打开。对应的数据表、接口和页面交互会在该阶段编写并测试。
      </div>
    </section>
  );
}
