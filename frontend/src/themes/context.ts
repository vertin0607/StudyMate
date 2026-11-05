import { createContext } from "react";

import type { ThemeDefinition, ThemeId } from "./themeTypes.ts";

export type ThemeContextValue = {
  themeId: ThemeId;
  theme: ThemeDefinition;
  setTheme: (id: ThemeId) => void;
};

export const ThemeContext = createContext<ThemeContextValue | null>(null);
