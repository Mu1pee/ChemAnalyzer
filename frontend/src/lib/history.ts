import type { HistoryItem } from "../types/molecule";

export const HISTORY_LIMIT = 30;

function makeId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `h-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }
}

/** Разбор сохранённой истории; записи старых версий дополняются новыми полями. */
export function parseHistory(raw: string | null): HistoryItem[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item): item is Partial<HistoryItem> => !!item && typeof item === "object")
      .filter((item) => typeof item.smiles === "string" && item.smiles.length > 0)
      .map((item) => ({
        id: item.id ?? makeId(),
        analyzedAt: item.analyzedAt ?? new Date().toISOString(),
        formula: item.formula ?? "",
        smiles: item.smiles as string,
        title: item.title ?? null,
        cid: item.cid ?? null,
        summary: item.summary ?? ""
      }))
      .slice(0, HISTORY_LIMIT);
  } catch {
    return [];
  }
}

/**
 * Объединяет записи, уже появившиеся в сессии (current), с загруженными из
 * хранилища (stored): свежие сверху, без дублей по SMILES, не более лимита.
 */
export function mergeHistory(current: HistoryItem[], stored: HistoryItem[]): HistoryItem[] {
  const seen = new Set<string>();
  const out: HistoryItem[] = [];
  for (const item of [...current, ...stored]) {
    if (seen.has(item.smiles)) continue;
    seen.add(item.smiles);
    out.push(item);
  }
  return out.slice(0, HISTORY_LIMIT);
}
