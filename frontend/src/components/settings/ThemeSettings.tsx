import { THEMES } from "../../themes/themeConfig.ts";
import { useTheme } from "../../themes/useTheme.ts";
import type { ThemeDefinition } from "../../themes/themeTypes.ts";

function ThemeCard({ theme, selected, onSelect }: { theme: ThemeDefinition; selected: boolean; onSelect: () => void }) {
  const { colors } = theme;
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`w-full rounded-3xl border p-4 text-left transition ${
        selected ? "border-accent ring-2 ring-accent/30" : "border-line hover:border-accent/50"
      }`}
    >
      <div className="overflow-hidden rounded-2xl border border-line" style={{ background: colors.background }}>
        <div className="flex h-24">
          <div className="w-10 shrink-0" style={{ background: colors.sidebar }} />
          <div className="flex min-w-0 flex-1 flex-col p-2">
            <div className="mb-2 h-4 rounded-md" style={{ background: colors.surface, border: `1px solid ${colors.border}` }} />
            <div className="flex flex-1 gap-2">
              <div className="flex-1 rounded-md p-2" style={{ background: colors.surface, border: `1px solid ${colors.border}` }}>
                <div className="h-2 w-10 rounded-full" style={{ background: colors.primary }} />
                <div className="mt-2 h-1.5 w-14 rounded-full" style={{ background: colors.text, opacity: 0.7 }} />
                <div className="mt-1 h-1.5 w-8 rounded-full" style={{ background: colors.muted }} />
              </div>
              <div className="w-8 rounded-md" style={{ background: colors.accent }} />
            </div>
          </div>
        </div>
      </div>
      <div className="mt-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">{theme.name}</p>
          <p className="mt-1 text-xs leading-5 text-muted">{theme.summary}</p>
        </div>
        {selected ? (
          <span className="shrink-0 rounded-full bg-accent-soft px-2 py-1 text-xs font-medium text-accent">当前</span>
        ) : null}
      </div>
    </button>
  );
}

export function ThemeSettings() {
  const { themeId, setTheme } = useTheme();

  return (
    <section className="mx-auto max-w-5xl">
      <p className="text-sm font-medium text-accent">外观设置</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">界面主题</h1>
      <p className="mt-4 max-w-2xl text-base leading-7 text-muted">
        选择一套配色后立即生效，并会记住你的账号偏好。成功、失败、警告和判题结果的颜色不会被主题改掉。
      </p>
      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {THEMES.map((theme) => (
          <ThemeCard key={theme.id} theme={theme} selected={theme.id === themeId} onSelect={() => setTheme(theme.id)} />
        ))}
      </div>
    </section>
  );
}
