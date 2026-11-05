import "katex/dist/katex.min.css";

import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { normalizeTutorMath } from "../utils/tutorMath.ts";

const katexOptions = {
  throwOnError: false,
  strict: "ignore" as const,
  output: "html" as const,
};

export function TutorMarkdown({ content }: { content: string }) {
  return (
    <div className="tutor-markdown text-sm leading-7 text-ink">
      <ReactMarkdown
        remarkPlugins={[[remarkMath, { singleDollarTextMath: true }], remarkGfm]}
        rehypePlugins={[[rehypeKatex, katexOptions]]}
      >
        {normalizeTutorMath(content)}
      </ReactMarkdown>
    </div>
  );
}
