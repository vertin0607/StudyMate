export function formatPracticeDuration(seconds: number | null): string {
  if (seconds === null) {
    return "暂无有效记录";
  }
  if (seconds === 0) {
    return "0 分钟";
  }
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  if (minutes === 0) {
    return `${rest} 秒`;
  }
  if (rest === 0) {
    return `${minutes} 分钟`;
  }
  return `${minutes} 分钟 ${rest} 秒`;
}

export function formatPassRate(rate: number | null, denominator: number): string {
  if (rate === null || denominator === 0) {
    return "暂无已判结果";
  }
  return `${Math.round(rate * 1000) / 10}%`;
}

export function localDateKey(value: string): string {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value.slice(0, 10);
  }
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

export function daysBefore(today: string, days: number): string {
  const [year, month, day] = today.split("-").map(Number);
  const date = new Date(year, (month ?? 1) - 1, day ?? 1);
  date.setDate(date.getDate() - (days - 1));
  const nextMonth = String(date.getMonth() + 1).padStart(2, "0");
  const nextDay = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${nextMonth}-${nextDay}`;
}

export const directionLabels: Record<string, string> = {
  up: "上升",
  down: "下降",
  stable: "基本稳定",
  insufficient: "数据不足",
};

export const categoryLabels: Record<string, string> = {
  knowledge_understanding: "知识理解",
  algorithm: "算法",
  implementation: "实现",
  boundary: "边界",
  forgetting: "遗忘",
};

export const diagnosisStatusLabels: Record<string, string> = {
  confirmed: "已确认",
  suspected: "初步发现",
  insufficient_data: "证据不足",
};

export const judgeCountLabels = [
  ["accepted", "本地测试通过"],
  ["wrong_answer", "答案错误"],
  ["compile_error", "编译错误"],
  ["runtime_error", "运行错误"],
  ["time_limit_exceeded", "超时"],
  ["system_error", "系统异常"],
  ["unjudged", "尚未判题"],
] as const;
