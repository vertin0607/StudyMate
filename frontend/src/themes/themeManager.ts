import { THEME_MAP } from "./themeConfig.ts";
import type { ThemeId } from "./themeTypes.ts";

export function applyTheme(id: ThemeId): void {
  const root = document.documentElement;
  root.dataset.theme = id;
  root.style.colorScheme = id === "night" ? "dark" : "light";
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.setAttribute("content", THEME_MAP[id].colors.sidebar);
  }
}

export function enableThemeTransitions(): void {
  const media = window.matchMedia("(prefers-reduced-motion: reduce)");
  const sync = () => {
    document.documentElement.classList.toggle("theme-reduce-motion", media.matches);
    document.documentElement.classList.add("theme-ready");
  };
  sync();
  media.addEventListener("change", sync);
}
