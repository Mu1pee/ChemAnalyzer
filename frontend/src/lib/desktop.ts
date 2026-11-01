/** Мост к Electron (window.chemAnalyzer). В обычном браузере его нет. */

export interface SaveResult {
  saved: boolean;
  canceled?: boolean;
  path?: string;
  error?: string;
}

export interface ChemAnalyzerBridge {
  isDesktop: true;
  apiOrigin: string | null;
  getInfo(): Promise<{
    version: string;
    electron: string;
    platform: string;
    dataDir: string;
  } | null>;
  getStored(key: "history" | "theme"): Promise<string | null>;
  setStored(key: "history" | "theme", value: string): Promise<boolean>;
  saveFile(payload: {
    name: string;
    text?: string;
    base64?: string;
  }): Promise<SaveResult>;
  exportPdf(payload: { html: string; name: string }): Promise<SaveResult>;
  openDataFolder(): Promise<boolean>;
  openExternal(url: string): Promise<boolean>;
  quit(): Promise<void>;
}

declare global {
  interface Window {
    chemAnalyzer?: ChemAnalyzerBridge;
  }
}

export const bridge: ChemAnalyzerBridge | undefined =
  typeof window !== "undefined" ? window.chemAnalyzer : undefined;

export const isDesktop = Boolean(bridge);
