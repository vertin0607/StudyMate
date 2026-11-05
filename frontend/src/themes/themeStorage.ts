import { DEFAULT_THEME_ID } from "./themeConfig.ts";
import { isThemeId, type ThemeId } from "./themeTypes.ts";

const LAST_KEY = "studymate_theme_last";
const GUEST_KEY = "studymate_theme_guest";

function userKey(userId: number): string {
  return `studymate_theme_user_${userId}`;
}

function read(key: string): ThemeId | null {
  try {
    const raw = localStorage.getItem(key);
    return isThemeId(raw) ? raw : null;
  } catch {
    return null;
  }
}

function write(key: string, id: ThemeId): void {
  try {
    localStorage.setItem(key, id);
  } catch {
    // 隐私模式或配额不足时仍然允许本次会话切换。
  }
}

export function loadTheme(userId: number | null): ThemeId {
  if (userId !== null) {
    return read(userKey(userId)) ?? DEFAULT_THEME_ID;
  }
  return read(GUEST_KEY) ?? read(LAST_KEY) ?? DEFAULT_THEME_ID;
}

export function saveTheme(userId: number | null, id: ThemeId): void {
  write(userId === null ? GUEST_KEY : userKey(userId), id);
  write(LAST_KEY, id);
}

