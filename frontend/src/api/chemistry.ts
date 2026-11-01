import type {
  ActivityResponse,
  AdmeResponse,
  IdentificationResult,
  ChemblResponse,
  MoleculeResponse,
  SpecializedActivityResponse
} from "../types/molecule";

import { API_ORIGIN, API_URL, NETWORK_ERROR_MESSAGE } from "./base";

/** Сервер недоступен (не запущен, неверный адрес, сеть). */
export class ApiNetworkError extends Error {
  constructor() {
    super(NETWORK_ERROR_MESSAGE);
    this.name = "ApiNetworkError";
  }
}

function extractDetail(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const detail = (data as { detail?: unknown }).detail;

  if (typeof detail === "string") return detail;

  // Ошибки валидации FastAPI (422): detail — массив объектов.
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) =>
        item && typeof item === "object" && "msg" in item
          ? String((item as { msg: unknown }).msg)
          : null
      )
      .filter(Boolean);
    return messages.length ? messages.join("; ") : null;
  }

  return null;
}

export async function postSmiles<T>(
  endpoint: string,
  smiles: string,
  fallbackError: string,
  extra: Record<string, unknown> = {}
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_URL}/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ smiles, ...extra })
    });
  } catch {
    throw new ApiNetworkError();
  }

  // Ответ может быть не JSON (например, 500 от прокси).
  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    throw new Error(
      extractDetail(data) ?? `${fallbackError} (код ${response.status}).`
    );
  }

  return data as T;
}

export function analyzeMolecule(smiles: string): Promise<MoleculeResponse> {
  return postSmiles("analyze", smiles, "Не удалось выполнить анализ");
}

export function identifyMolecule(
  smiles: string
): Promise<IdentificationResult> {
  return postSmiles(
    "identify",
    smiles,
    "Не удалось выполнить идентификацию"
  );
}

/** SVG-изображение структуры (RDKit) для экспорта и отчёта. */
export async function fetchDepiction(
  smiles: string,
  width = 520,
  height = 380
): Promise<string> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/depict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ smiles, width, height })
    });
  } catch {
    throw new ApiNetworkError();
  }
  if (!response.ok) {
    throw new Error("Не удалось построить изображение структуры.");
  }
  return response.text();
}

export function fetchAdme(smiles: string): Promise<AdmeResponse> {
  return postSmiles("adme", smiles, "Не удалось рассчитать ADME-профиль");
}

export function predictActivity(smiles: string): Promise<ActivityResponse> {
  return postSmiles(
    "activity",
    smiles,
    "Не удалось рассчитать биологическую активность"
  );
}

export function fetchChembl(smiles: string): Promise<ChemblResponse> {
  return postSmiles("chembl", smiles, "Не удалось получить данные ChEMBL");
}

/** ПК «Антидот-Прогноз»: endpoint-specific models, if trained and validated. */
export function fetchSpecializedActivity(
  smiles: string
): Promise<SpecializedActivityResponse> {
  return postSmiles(
    "specialized-activity",
    smiles,
    "Не удалось проверить модели Антидот-Прогноз"
  );
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_ORIGIN}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

export interface AppInfo {
  name: string;
  version: string;
  desktop: boolean;
  assistant_configured: boolean;
  models_dir: string | null;
}

export async function fetchAppInfo(): Promise<AppInfo | null> {
  try {
    const response = await fetch(`${API_ORIGIN}/api/app/info`);
    return response.ok ? ((await response.json()) as AppInfo) : null;
  } catch {
    return null;
  }
}
