import type {
  ConformerResponse,
  ProteinStructure,
  TargetProteins
} from "../types/molecule";
import { API_ORIGIN, NETWORK_ERROR_MESSAGE } from "./base";
import { postSmiles } from "./chemistry";

const API_ROOT = API_ORIGIN;

async function getJson<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_ROOT}${path}`);
  } catch {
    throw new Error(NETWORK_ERROR_MESSAGE);
  }

  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? (data as { detail: unknown }).detail
        : null;
    throw new Error(
      typeof detail === "string"
        ? detail
        : `Ошибка сервера (код ${response.status}).`
    );
  }
  return data as T;
}

export function fetchConformer(
  smiles: string,
  seed = 42
): Promise<ConformerResponse> {
  return postSmiles(
    "conformer",
    smiles,
    "3D-конформация не была построена",
    { seed }
  );
}

export function fetchTargetProteins(chemblId: string): Promise<TargetProteins> {
  return getJson(`/api/structure/target/${encodeURIComponent(chemblId)}`);
}

export function fetchProtein(accession: string): Promise<ProteinStructure> {
  return getJson(`/api/structure/protein/${encodeURIComponent(accession)}`);
}

export function proteinDownloadUrl(
  accession: string,
  fmt: "pdb" | "cif"
): string {
  return `${API_ROOT}/api/structure/protein/${encodeURIComponent(
    accession
  )}/download?fmt=${fmt}`;
}
