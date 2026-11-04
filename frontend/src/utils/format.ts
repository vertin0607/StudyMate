/** 直接拆开 YYYY-MM-DD，避免时区把日期提前或推后一天。 */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.slice(0, 10).split("-");
  if (!year || !month || !day) {
    return isoDate;
  }
  return `${year}年${Number(month)}月${Number(day)}日`;
}

/** 把后端返回的 ISO 时间格式化成中文日期。 */
export function formatServerTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
