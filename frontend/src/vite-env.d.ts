/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Адрес backend для dev в браузере, например http://127.0.0.1:8000 */
  readonly VITE_API_ORIGIN?: string;
  /** Устаревшая переменная (полный URL до /api/molecules); используется только её origin */
  readonly VITE_API_URL?: string;
}

/** Версия из package.json (подставляется Vite при сборке). */
declare const __APP_VERSION__: string;
