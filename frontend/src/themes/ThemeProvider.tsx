import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { useAuth } from "../auth/useAuth.ts";
import { ThemeContext } from "./context.ts";
import { DEFAULT_THEME_ID, THEME_MAP } from "./themeConfig.ts";
import { applyTheme, enableThemeTransitions } from "./themeManager.ts";
import { loadTheme, saveTheme } from "./themeStorage.ts";
import { isThemeId, type ThemeId } from "./themeTypes.ts";

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const userId = user?.id ?? null;
  const [state, setState] = useState<{ userId: number | null; themeId: ThemeId }>(() => ({
    userId: null,
    themeId: loadTheme(null),
  }));

  if (state.userId !== userId) {
    setState({ userId, themeId: loadTheme(userId) });
  }

  useEffect(() => {
    enableThemeTransitions();
  }, []);

  useEffect(() => {
    applyTheme(state.themeId);
  }, [state.themeId]);

  const setTheme = useCallback(
    (id: ThemeId) => {
      if (!isThemeId(id)) {
        return;
      }
      setState((current) => ({ ...current, themeId: id }));
      applyTheme(id);
      saveTheme(userId, id);
    },
    [userId],
  );

  const value = useMemo(
    () => ({
      themeId: state.themeId,
      theme: THEME_MAP[state.themeId] ?? THEME_MAP[DEFAULT_THEME_ID],
      setTheme,
    }),
    [setTheme, state.themeId],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
