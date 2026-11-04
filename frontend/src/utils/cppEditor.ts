import { selectAll } from "@codemirror/commands";
import type { EditorView } from "@codemirror/view";

export function replaceEditorCode(view: EditorView, code: string) {
  view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: code } });
  view.focus();
}

export function selectEditorCode(view: EditorView) {
  selectAll(view);
  view.focus();
}
