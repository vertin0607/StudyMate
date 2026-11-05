export const THEME_IDS = ["sky", "sakura", "forest", "lavender", "sunset", "ocean", "night"] as const;

export type ThemeId = (typeof THEME_IDS)[number];

export type ThemeColors = {
  background: string;
  surface: string;
  soft: string;
  sidebar: string;
  sidebarText: string;
  sidebarMuted: string;
  sidebarActive: string;
  text: string;
  muted: string;
  border: string;
  primary: string;
  primaryHover: string;
  primarySoft: string;
  onPrimary: string;
  accent: string;
  overlay: string;
  chart: string;
  chartMuted: string;
  codeBg: string;
  codeFg: string;
  inlineCode: string;
};

export type ThemeDefinition = {
  id: ThemeId;
  name: string;
  summary: string;
  colors: ThemeColors;
};

export function isThemeId(value: unknown): value is ThemeId {
  return typeof value === "string" && (THEME_IDS as readonly string[]).includes(value);
}
