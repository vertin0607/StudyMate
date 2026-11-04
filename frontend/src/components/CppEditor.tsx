import { indentWithTab } from "@codemirror/commands";
import { cpp } from "@codemirror/lang-cpp";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { basicSetup } from "codemirror";
import { useEffect, useRef } from "react";

type CppEditorProps = {
  initialCode: string;
  onChange: (code: string) => void;
  onReady: (view: EditorView) => void;
};

export function CppEditor({ initialCode, onChange, onReady }: CppEditorProps) {
  const host = useRef<HTMLDivElement>(null);
  const onChangeRef = useRef(onChange);
  const onReadyRef = useRef(onReady);

  useEffect(() => {
    onChangeRef.current = onChange;
    onReadyRef.current = onReady;
  });

  useEffect(() => {
    const parent = host.current;
    if (!parent) {
      return;
    }
    const view = new EditorView({
      parent,
      state: EditorState.create({
        doc: initialCode,
        extensions: [
          basicSetup,
          cpp(),
          keymap.of([indentWithTab]),
          EditorView.lineWrapping,
          EditorView.updateListener.of((update) => {
            if (update.docChanged) {
              onChangeRef.current(update.state.doc.toString());
            }
          }),
          EditorView.theme({
            "&": { height: "18rem", maxHeight: "24rem", fontSize: "13px", backgroundColor: "#ffffff" },
            ".cm-scroller": { fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace", lineHeight: "1.55" },
            ".cm-gutters": { backgroundColor: "#f8fafc", color: "#64748b", borderRight: "1px solid #e2e8f0" },
            "&.cm-focused": { outline: "none" },
          }),
        ],
      }),
    });
    onReadyRef.current(view);
    return () => view.destroy();
  }, [initialCode]);

  return <div ref={host} className="overflow-hidden rounded-2xl border border-slate-200" />;
}
