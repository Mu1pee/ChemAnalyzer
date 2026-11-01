export type Theme = "dark" | "light";

export function parseTheme(raw: string | null): Theme | null {
  return raw === "light" || raw === "dark" ? raw : null;
}

/** Только применяет тему к документу; сохранение — в lib/storage.ts. */
export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
}
