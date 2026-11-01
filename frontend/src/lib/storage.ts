import { bridge } from "./desktop";

export type StoreKey = "history" | "theme";

const lsKey = (key: StoreKey) => `chemanalyzer-${key}`;

/**
 * Хранилище состояния интерфейса.
 *  - desktop: файл в папке данных пользователя (через Electron). localStorage здесь
 *    не годится: у каждого запуска свой порт backend, а значит и свой origin,
 *    поэтому localStorage при каждом старте оказывался бы пустым;
 *  - браузер: localStorage.
 */
export async function loadStored(key: StoreKey): Promise<string | null> {
  try {
    if (bridge) return await bridge.getStored(key);
    return localStorage.getItem(lsKey(key));
  } catch {
    return null;
  }
}

export async function saveStored(key: StoreKey, value: string): Promise<void> {
  try {
    if (bridge) await bridge.setStored(key, value);
    else localStorage.setItem(lsKey(key), value);
  } catch {
    // Хранилище недоступно (квота, приватный режим) — работаем без сохранения.
  }
}
