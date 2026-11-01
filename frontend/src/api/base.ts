import { bridge } from "../lib/desktop";

/**
 * Адрес backend.
 *  - desktop: его сообщает Electron (случайный свободный порт);
 *  - dev в браузере: VITE_API_ORIGIN, либо origin из старой VITE_API_URL,
 *    либо http://127.0.0.1:8000.
 */
function resolveOrigin(): string {
  if (bridge?.apiOrigin) return bridge.apiOrigin;

  const explicit = import.meta.env.VITE_API_ORIGIN;
  if (explicit) return explicit.replace(/\/+$/, "");

  const legacy = import.meta.env.VITE_API_URL;
  if (legacy) {
    try {
      return new URL(legacy).origin;
    } catch {
      // некорректное значение — используем адрес по умолчанию
    }
  }
  return "http://127.0.0.1:8000";
}

export const API_ORIGIN: string = resolveOrigin();
export const API_URL = `${API_ORIGIN}/api/molecules`;

/** Сообщение о недоступности backend: для desktop и для разработки оно разное. */
export const NETWORK_ERROR_MESSAGE: string = bridge
  ? "Локальный движок (RDKit) не отвечает. Закройте и снова откройте ChemAnalyzer. " +
    "Подробности — в файле logs\\backend.log в папке данных (Settings → «Открыть папку данных»)."
  : "Не удалось связаться с сервером. Проверьте, что backend запущен " +
    "(python -m uvicorn app.main:app --reload).";
