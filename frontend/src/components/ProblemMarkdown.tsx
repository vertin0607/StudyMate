import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function ProblemMarkdown({ content }: { content: string }) {
  return (
    <div className="problem-markdown text-sm leading-7 text-slate-700">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
