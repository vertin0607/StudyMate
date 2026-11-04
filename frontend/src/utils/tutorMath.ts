const fencePattern = /```[\s\S]*?```/g;
const displayPattern = /\\\[([\s\S]+?)\\\]/g;
const inlinePattern = /\\\(([\s\S]+?)\\\)/g;
const mathPattern = /\$\$[\s\S]+?\$\$|\$[^$\n]+?\$/g;

/** 与后端的公式整理保持一致，让已经保存的对话也能正确显示。 */
export function normalizeTutorMath(text: string): string {
  const pieces: string[] = [];
  let last = 0;
  for (const match of text.matchAll(fencePattern)) {
    const start = match.index ?? 0;
    pieces.push(normalizeProse(text.slice(last, start)));
    pieces.push(match[0]);
    last = start + match[0].length;
  }
  pieces.push(normalizeProse(text.slice(last)));
  return pieces.join("");
}

function normalizeProse(text: string): string {
  const converted = text
    .replace(displayPattern, (_full, inner: string) => `$$${inner.trim()}$$`)
    .replace(inlinePattern, (_full, inner: string) => `$${inner.trim()}$`);
  return collapseRepeats(trimMath(converted));
}

function trimMath(text: string): string {
  let result = "";
  let index = 0;
  while (index < text.length) {
    if (text.startsWith("$$", index)) {
      const end = text.indexOf("$$", index + 2);
      if (end === -1) {
        result += text.slice(index);
        break;
      }
      result += `\n\n$$\n${text.slice(index + 2, end).trim()}\n$$\n\n`;
      index = end + 2;
      continue;
    }
    if (text[index] === "$") {
      const end = text.indexOf("$", index + 1);
      if (end === -1 || text.slice(index + 1, end).includes("\n")) {
        result += "$";
        index += 1;
        continue;
      }
      const inner = text.slice(index + 1, end).trim();
      if (!inner) {
        result += "$";
        index += 1;
        continue;
      }
      result += `$${inner}$`;
      index = end + 1;
      continue;
    }
    result += text[index];
    index += 1;
  }
  return result;
}

function collapseRepeats(text: string): string {
  const matches = [...text.matchAll(mathPattern)];
  if (matches.length === 0) {
    return text;
  }
  const pieces: string[] = [];
  let last = 0;
  let previous: string | null = null;
  for (const match of matches) {
    const start = match.index ?? 0;
    const gap = text.slice(last, start);
    const body = formulaBody(match[0]);
    if (previous !== null && previous === body && gap.trim() === "") {
      last = start + match[0].length;
      continue;
    }
    pieces.push(gap, match[0]);
    previous = body;
    last = start + match[0].length;
  }
  pieces.push(text.slice(last));
  return pieces.join("");
}

function formulaBody(formula: string): string {
  if (formula.startsWith("$$")) {
    return formula.slice(2, -2).trim();
  }
  return formula.slice(1, -1).trim();
}
