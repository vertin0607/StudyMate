/** 默认 C++ 模板。只在编辑器里展示，没有草稿时不写入数据库。 */
export const CPP_TEMPLATE = `#include <iostream>
using namespace std;

int main() {

    return 0;
}
`;

export type CodeDraft = {
  saved: boolean;
  source_code: string;
};

export function initialEditorCode(draft: CodeDraft): string {
  if (!draft.saved) {
    return CPP_TEMPLATE;
  }
  return draft.source_code;
}

export function canSubmitCode(source: string): boolean {
  return source.trim().length > 0;
}

export type SavePhase = "idle" | "saving" | "saved" | "failed";

/**
 * 同一时间只发送一份草稿。请求进行中又有新代码时，结束后只提交最新内容。
 * 不会把编辑器内容替换成服务器返回值。
 */
export class DraftSaveQueue {
  phase: SavePhase = "idle";
  readonly sent: string[] = [];
  private running = false;
  private latest: string | null = null;
  private lastCommitted: string | null = null;
  private readonly waiters: Array<() => void> = [];
  private readonly put: (source: string) => Promise<void>;

  constructor(put: (source: string) => Promise<void>) {
    this.put = put;
  }

  markSaved(source: string) {
    this.lastCommitted = source;
    this.latest = source;
    this.phase = "saved";
  }

  note(source: string) {
    this.latest = source;
  }

  hasUnsaved(source: string): boolean {
    return source !== this.lastCommitted;
  }

  async flush(): Promise<void> {
    if (this.running) {
      await new Promise<void>((resolve) => {
        this.waiters.push(resolve);
      });
      return;
    }
    this.running = true;
    try {
      while (this.latest !== null && this.latest !== this.lastCommitted) {
        const snapshot = this.latest;
        this.phase = "saving";
        try {
          await this.put(snapshot);
        } catch {
          this.phase = "failed";
          return;
        }
        this.sent.push(snapshot);
        if (this.latest === snapshot) {
          this.lastCommitted = snapshot;
          this.phase = "saved";
        }
      }
    } finally {
      this.running = false;
      const pending = this.waiters.splice(0);
      for (const resolve of pending) {
        resolve();
      }
    }
  }
}
