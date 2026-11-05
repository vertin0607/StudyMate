import { indentWithTab } from "@codemirror/commands";
import { cpp } from "@codemirror/lang-cpp";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { tags as t } from "@lezer/highlight";
import { basicSetup } from "codemirror";
import { useEffect, useRef } from "react";

import { useTheme } from "../themes/useTheme.ts";

type CppEditorProps = {
  initialCode: string;
  onChange: (code: string) => void;
  onReady: (view: EditorView) => void;
};

const nightHighlight = HighlightStyle.define([
  { tag: t.keyword, color: "#c4b5fd" },
  { tag: t.controlKeyword, color: "#c4b5fd" },
  { tag: t.definitionKeyword, color: "#c4b5fd" },
  { tag: t.moduleKeyword, color: "#c4b5fd" },
  { tag: t.string, color: "#f9a8d4" },
  { tag: t.comment, color: "#93a4b8" },
  { tag: t.number, color: "#fbbf24" },
  { tag: t.typeName, color: "#7dd3fc" },
  { tag: t.bool, color: "#fbbf24" },
  { tag: t.function(t.variableName), color: "#93c5fd" },
  { tag: t.variableName, color: "#e8eef6" },
  { tag: t.operator, color: "#7dd3fc" },
  { tag: t.processingInstruction, color: "#93c5fd" },
  { tag: t.meta, color: "#93c5fd" },
  { tag: t.name, color: "#e8eef6" },
]);

export function CppEditor({ initialCode, onChange, onReady }: CppEditorProps) {
  const host = useRef<HTMLDivElement>(null);
  const onChangeRef = useRef(onChange);
  const onReadyRef = useRef(onReady);
  const { themeId } = useTheme();
  const night = themeId === "night";

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
          ...(night ? [syntaxHighlighting(nightHighlight), EditorView.darkTheme.of(true)] : []),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) {
              onChangeRef.current(update.state.doc.toString());
            }
          }),
          EditorView.theme({
            "&": {
              height: "18rem",
              maxHeight: "24rem",
              fontSize: "13px",
              backgroundColor: "var(--app-surface)",
              color: "var(--app-text)",
              caretColor: "var(--app-text)",
            },
            ".cm-scroller": { fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace", lineHeight: "1.55" },
            ".cm-gutters": {
              backgroundColor: "var(--app-soft)",
              color: "var(--app-muted)",
              borderRight: "1px solid var(--app-border)",
            },
            ".cm-activeLine": { backgroundColor: "color-mix(in srgb, var(--app-primary) 12%, transparent)" },
            ".cm-activeLineGutter": { backgroundColor: "color-mix(in srgb, var(--app-primary) 12%, transparent)" },
            "&.cm-focused .cm-selectionBackground, .cm-selectionBackground": {
              backgroundColor: "color-mix(in srgb, var(--app-primary) 35%, transparent) !important",
            },
            ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--app-text)" },
            "&.cm-focused": { outline: "none" },
          }),
        ],
      }),
    });
    onReadyRef.current(view);
    return () => view.destroy();
  }, [initialCode, night]);

  return <div ref={host} className="overflow-hidden rounded-2xl border border-line" />;
}
