export function safeNextPath(from: unknown): string {
  if (typeof from !== "string" || !from.startsWith("/") || from.startsWith("//")) {
    return "/dashboard";
  }
  if (from.startsWith("/login") || from.startsWith("/register")) {
    return "/dashboard";
  }
  return from;
}
