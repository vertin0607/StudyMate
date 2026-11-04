import assert from "node:assert/strict";

import { CPP_TEMPLATE, DraftSaveQueue, canSubmitCode, initialEditorCode } from "../src/utils/draftSave.ts";

assert.equal(initialEditorCode({ saved: false, source_code: "" }), CPP_TEMPLATE);
assert.equal(initialEditorCode({ saved: true, source_code: "" }), "");
assert.equal(initialEditorCode({ saved: true, source_code: "int  a;" }), "int  a;");
assert.equal(canSubmitCode("  \n"), false);
assert.equal(canSubmitCode("int main(){return 0;}"), true);

async function delayed(source: string, gate: { release: (() => void) | null }) {
  if (source === "A") {
    await new Promise<void>((resolve) => {
      gate.release = resolve;
    });
  }
}

const gate: { release: (() => void) | null } = { release: null };
const queue = new DraftSaveQueue((source) => delayed(source, gate));
queue.note("A");
const first = queue.flush();
queue.note("AB");
queue.note("ABC");
const second = queue.flush();
assert.equal(queue.phase, "saving");
gate.release?.();
await first;
await second;
assert.deepEqual(queue.sent, ["A", "ABC"]);
assert.equal(queue.phase, "saved");

let failed = false;
const flaky = new DraftSaveQueue(async (source) => {
  if (!failed && source === "old") {
    failed = true;
    throw new Error("network");
  }
});
flaky.note("old");
await flaky.flush();
assert.equal(flaky.phase, "failed");
assert.deepEqual(flaky.sent, []);
flaky.note("new");
await flaky.flush();
assert.deepEqual(flaky.sent, ["new"]);

console.log("draft-save checks passed");
