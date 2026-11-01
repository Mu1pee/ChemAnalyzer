"""3D-структуры белков-мишеней из базы AlphaFold (EMBL-EBI / DeepMind).

AlphaFold предсказывает структуры БЕЛКОВ, а не малых молекул. Здесь мы не
запускаем сам AlphaFold (нужны сотни ГБ баз и GPU), а берём готовые
модели из AlphaFold Protein Structure Database по идентификатору UniProt.
"""

import re
from collections import OrderedDict

import httpx
from fastapi import APIRouter, HTTPException, Response

router = APIRouter(prefix="/api/structure", tags=["structure"])

AF_API = "https://alphafold.ebi.ac.uk/api/prediction"
AF_HOST = "alphafold.ebi.ac.uk"
CHEMBL_TARGET = "https://www.ebi.ac.uk/chembl/api/data/target"

# Официальное регулярное выражение для accession UniProt.
UNIPROT_RE = re.compile(
    r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)
CHEMBL_ID_RE = re.compile(r"^CHEMBL[0-9]{1,9}$")

MAX_FILE_BYTES = 25 * 1024 * 1024
CACHE_SIZE = 12
TIMEOUT = httpx.Timeout(30.0, connect=8.0)
HEADERS = {"User-Agent": "ChemAnalyzerModern/2.3 (+local app)"}

ATTRIBUTION = (
    "Модели: AlphaFold Protein Structure Database (Google DeepMind и "
    "EMBL-EBI), лицензия CC BY 4.0. Jumper et al., Nature 2021; "
    "Varadi et al., Nucleic Acids Res. 2022."
)


class StructureError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------- чистые функции ----------


def normalize_accession(value: str) -> str:
    accession = (value or "").strip().upper()
    if not UNIPROT_RE.match(accession):
        raise StructureError(
            400,
            "Некорректный идентификатор UniProt (пример: P35354). "
            "Изоформы вида P35354-2 не поддерживаются.",
        )
    return accession


def safe_file_url(url: str | None) -> str | None:
    """Разрешаем скачивание только с хоста AlphaFold по https (защита от SSRF)."""
    if not url:
        return None
    match = re.match(r"^https://([^/:@]+)/", url)
    if not match or match.group(1).lower() != AF_HOST:
        return None
    return url


def _int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_prediction(payload, accession: str) -> dict | None:
    """Выбирает модель из ответа API и приводит к единому виду."""
    entries = payload if isinstance(payload, list) else [payload]
    entries = [e for e in entries if isinstance(e, dict)]
    usable = [e for e in entries if safe_file_url(e.get("pdbUrl"))]
    if not usable:
        return None

    entry = usable[0]
    start, end = _int(entry.get("uniprotStart")), _int(entry.get("uniprotEnd"))
    plddt = entry.get("globalMetricValue")

    return {
        "uniprot": accession,
        "entry_id": entry.get("entryId"),
        "gene": entry.get("gene"),
        "organism": entry.get("organismScientificName"),
        "description": entry.get("uniprotDescription"),
        "mean_plddt": round(float(plddt), 1) if isinstance(plddt, (int, float)) else None,
        "model_version": entry.get("latestVersion"),
        "residues": (end - start + 1) if start and end else None,
        "fragments": len(usable),
        "pdb_url": safe_file_url(entry.get("pdbUrl")),
        "cif_url": safe_file_url(entry.get("cifUrl")),
        "pae_image_url": safe_file_url(entry.get("paeImageUrl")),
    }


def plddt_label(value: float | None) -> str | None:
    if value is None:
        return None
    if value >= 90:
        return "очень высокая достоверность"
    if value >= 70:
        return "высокая достоверность"
    if value >= 50:
        return "низкая достоверность"
    return "очень низкая достоверность"


def parse_target_proteins(payload: dict) -> list[dict]:
    proteins, seen = [], set()
    for component in (payload or {}).get("target_components") or []:
        accession = (component.get("accession") or "").strip().upper()
        if accession and accession not in seen and UNIPROT_RE.match(accession):
            seen.add(accession)
            proteins.append(
                {
                    "accession": accession,
                    "description": component.get("component_description"),
                }
            )
    return proteins


# ---------- сеть ----------


def _host(url: str) -> str | None:
    match = re.match(r"^https://([^/:@]+)", url)
    return match.group(1).lower() if match else None


async def _get(client: httpx.AsyncClient, url: str):
    try:
        response = await client.get(url)
    except httpx.HTTPError as error:
        raise StructureError(
            502, "Не удалось связаться с внешним сервисом. Проверьте интернет."
        ) from error

    # Редирект не должен уводить на другой хост (защита от подмены адреса).
    final_host = getattr(getattr(response, "url", None), "host", None)
    if final_host and final_host.lower() != _host(url):
        raise StructureError(
            502, "Сервис перенаправил запрос на неожиданный адрес."
        )
    return response


_cache: "OrderedDict[str, dict]" = OrderedDict()


async def load_protein(accession: str) -> dict:
    accession = normalize_accession(accession)
    if accession in _cache:
        _cache.move_to_end(accession)
        return _cache[accession]

    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers=HEADERS, follow_redirects=True
    ) as client:
        response = await _get(client, f"{AF_API}/{accession}")
        if response.status_code == 404:
            raise StructureError(
                404,
                f"Для {accession} нет модели в базе AlphaFold. Возможно, "
                "есть экспериментальная структура в PDB (rcsb.org).",
            )
        if response.status_code != 200:
            raise StructureError(
                502, f"База AlphaFold вернула ошибку ({response.status_code})."
            )

        try:
            meta = parse_prediction(response.json(), accession)
        except ValueError as error:
            raise StructureError(502, "Некорректный ответ базы AlphaFold.") from error
        if meta is None:
            raise StructureError(404, f"Для {accession} нет доступной модели.")

        file_response = await _get(client, meta["pdb_url"])
        if file_response.status_code != 200:
            raise StructureError(502, "Не удалось скачать файл модели.")
        if len(file_response.content) > MAX_FILE_BYTES:
            raise StructureError(413, "Файл модели слишком большой.")

    meta["pdb"] = file_response.text
    meta["plddt_label"] = plddt_label(meta["mean_plddt"])
    meta["attribution"] = ATTRIBUTION
    meta["disclaimer"] = (
        "Это предсказанная модель, а не эксперимент. Цвет показывает "
        "достоверность pLDDT: участки с низким значением ненадёжны. Модель "
        "без лигандов и кофакторов, поэтому позы связывания по ней нельзя "
        "считать надёжными без дополнительной проверки."
    )

    _cache[accession] = meta
    while len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)
    return meta


async def download_file(accession: str, fmt: str) -> tuple[bytes, str]:
    if fmt not in ("pdb", "cif"):
        raise StructureError(400, "Формат должен быть pdb или cif.")
    accession = normalize_accession(accession)

    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers=HEADERS, follow_redirects=True
    ) as client:
        response = await _get(client, f"{AF_API}/{accession}")
        if response.status_code != 200:
            raise StructureError(404, f"Для {accession} нет модели в AlphaFold.")
        try:
            meta = parse_prediction(response.json(), accession)
        except ValueError as error:
            raise StructureError(502, "Некорректный ответ базы AlphaFold.") from error
        url = meta and meta.get(f"{fmt}_url")
        if not url:
            raise StructureError(404, f"Файл формата {fmt} недоступен.")

        file_response = await _get(client, url)
        if file_response.status_code != 200:
            raise StructureError(502, "Не удалось скачать файл модели.")
        if len(file_response.content) > MAX_FILE_BYTES:
            raise StructureError(413, "Файл модели слишком большой.")

    name = f"{meta['entry_id'] or 'AF-' + accession}-model.{fmt}"
    return file_response.content, name


async def resolve_target(chembl_id: str) -> dict:
    chembl_id = (chembl_id or "").strip().upper()
    if not CHEMBL_ID_RE.match(chembl_id):
        raise StructureError(400, "Некорректный идентификатор мишени ChEMBL.")

    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
        response = await _get(client, f"{CHEMBL_TARGET}/{chembl_id}.json")

    if response.status_code == 404:
        raise StructureError(404, f"Мишень {chembl_id} не найдена в ChEMBL.")
    if response.status_code != 200:
        raise StructureError(502, f"ChEMBL вернул ошибку ({response.status_code}).")

    try:
        payload = response.json()
    except ValueError as error:
        raise StructureError(502, "Некорректный ответ ChEMBL.") from error

    return {
        "chembl_id": chembl_id,
        "name": payload.get("pref_name"),
        "target_type": payload.get("target_type"),
        "proteins": parse_target_proteins(payload),
    }


# ---------- маршруты ----------


def _raise(error: StructureError):
    raise HTTPException(status_code=error.status, detail=error.message) from error


@router.get("/target/{chembl_id}")
async def target_proteins(chembl_id: str):
    try:
        return await resolve_target(chembl_id)
    except StructureError as error:
        _raise(error)


@router.get("/protein/{accession}")
async def protein(accession: str):
    try:
        return await load_protein(accession)
    except StructureError as error:
        _raise(error)


@router.get("/protein/{accession}/download")
async def protein_download(accession: str, fmt: str = "pdb"):
    try:
        content, filename = await download_file(accession, fmt)
    except StructureError as error:
        _raise(error)

    return Response(
        content=content,
        media_type="chemical/x-pdb" if fmt == "pdb" else "chemical/x-cif",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
