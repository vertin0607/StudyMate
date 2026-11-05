import { useContext } from "react";

import { ThemeContext } from "./context.ts";

export function useTheme() {
  const value = useContext(ThemeContext);
  if (value === null) {
    throw new Error("useTheme 必须放在 ThemeProvider 中");
  }
  return value;
}
