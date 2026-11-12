"use client";

import { MonitorIcon, MoonIcon, SunIcon } from "@/shared/ui/icons";
import { THEMES, useTheme, type Theme } from "@/shared/lib/theme";

const META: Record<Theme, { label: string; icon: React.ReactNode }> = {
  system: { label: "System", icon: <MonitorIcon size={15} /> },
  light: { label: "Light", icon: <SunIcon size={15} /> },
  dark: { label: "Dark", icon: <MoonIcon size={15} /> },
};

/** Segmented control: System / Light / Dark. `onNav` styles it for the dark sidebar. */
export function ThemeToggle({
  onNav = false,
  compact = false,
}: {
  onNav?: boolean;
  compact?: boolean;
}) {
  const [theme, setTheme] = useTheme();
  if (compact) {
    const next = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length] ?? "system";
    return (
      <button
        type="button"
        onClick={() => setTheme(next)}
        aria-label={`Theme: ${META[theme].label}. Switch to ${META[next].label}`}
        title={`Theme: ${META[theme].label}`}
        className="text-nav-ink/80 flex size-9 items-center justify-center rounded-lg hover:bg-white/[0.04] hover:text-white focus-visible:outline-2 focus-visible:outline-teal-300"
      >
        {META[theme].icon}
      </button>
    );
  }
  return (
    <div
      role="group"
      aria-label="Theme"
      className={`flex gap-0.5 rounded-lg p-0.5 ${onNav ? "bg-white/[0.05]" : "bg-surface-3"}`}
    >
      {THEMES.map((t) => {
        const active = t === theme;
        return (
          <button
            key={t}
            type="button"
            onClick={() => setTheme(t)}
            aria-pressed={active}
            aria-label={`${META[t].label} theme`}
            title={`${META[t].label} theme`}
            className={`flex h-7 flex-1 items-center justify-center gap-1.5 rounded-md px-2.5 text-xs font-medium whitespace-nowrap transition-colors focus-visible:outline-2 ${
              onNav
                ? `focus-visible:outline-teal-300 ${active ? "bg-nav-2 text-white shadow-[0_1px_2px_rgb(0_0_0/0.4)]" : "text-nav-ink/80 hover:text-white"}`
                : `focus-visible:outline-brand-ring ${active ? "bg-surface text-ink shadow-card" : "text-ink-3 hover:text-ink"}`
            }`}
          >
            {META[t].icon}
            <span>{META[t].label}</span>
          </button>
        );
      })}
    </div>
  );
}
