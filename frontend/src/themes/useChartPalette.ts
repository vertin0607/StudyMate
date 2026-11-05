import { useMemo } from "react";

import { THEME_MAP } from "./themeConfig.ts";
import { useTheme } from "./useTheme.ts";

export function useChartPalette() {
  const { themeId } = useTheme();
  return useMemo(() => {
    const colors = THEME_MAP[themeId].colors;
    return {
      grid: colors.border,
      bar: colors.chart,
      barMuted: colors.chartMuted,
      tick: colors.muted,
    };
  }, [themeId]);
}
