import logging
from fastapi import APIRouter, HTTPException, Response
from fastapi.concurrency import run_in_threadpool

from app.api.chembl import fetch_chembl_profile
from app.api.pubchem import identify_by_smiles
from app.chemistry.activity import predict_activity
from app.chemistry.adme import compute_adme
from app.chemistry.conformer import generate_conformer
from app.chemistry.depict import depict_svg
from app.chemistry.descriptors import analyze_molecule
from app.chemistry.druglikeness import assess_druglikeness, structure_keys
from app.chemistry.qsar import predict_qsar
from app.chemistry.specialized_activity import predict_specialized_activity
from app.schemas.molecule import (
    ActivityResponse,
    AdmeResponse,
    ChemblResponse,
    ConformerRequest,
    ConformerResponse,
    DepictRequest,
    IdentificationResult,
    MoleculeRequest,
    MoleculeResponse,
    SpecializedActivityResponse,
)

router = APIRouter()


@router.post("/analyze", response_model=MoleculeResponse)
async def analyze(molecule: MoleculeRequest):
    """Локальный анализ RDKit. Работает без интернета и быстро."""
    try:
        return await run_in_threadpool(analyze_molecule, molecule.smiles)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/identify", response_model=IdentificationResult)
async def identify(molecule: MoleculeRequest):
    """Идентификация в PubChem. Сбой сервиса не ломает локальный анализ."""
    try:
        keys = await run_in_threadpool(structure_keys, molecule.smiles)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    try:
        return await identify_by_smiles(keys["smiles"])
    except Exception:
        return {
            "status": "unavailable",
            "found": False,
            "message": "PubChem недоступен — локальный анализ выполнен.",
        }


@router.post("/validate")
def validate(molecule: MoleculeRequest):
    try:
        result = analyze_molecule(molecule.smiles)
    except ValueError as error:
        return {"valid": False, "error": str(error)}

    return {
        "valid": True,
        "canonical_smiles": result["canonical_smiles"],
        "formula": result["formula"],
    }


def _activity_bundle(smiles: str) -> dict:
    result = predict_activity(smiles)
    result["druglikeness"] = assess_druglikeness(smiles)
    try:
        result["qsar"] = predict_qsar(smiles)
    except Exception as error:  # QSAR не должен ломать остальной анализ
        result["qsar"] = {
            "status": "error",
            "available": False,
            "message": f"QSAR-модели недоступны: {error}",
        }
    return result


@router.post("/activity", response_model=ActivityResponse)
async def activity(molecule: MoleculeRequest):
    """Локальный прогноз спектра активности и drug-likeness (без сети)."""
    try:
        return await run_in_threadpool(_activity_bundle, molecule.smiles)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/chembl", response_model=ChemblResponse)
async def chembl(molecule: MoleculeRequest):
    """Экспериментальные данные об активности из ChEMBL."""
    try:
        keys = await run_in_threadpool(structure_keys, molecule.smiles)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    try:
        return await fetch_chembl_profile(keys["smiles"], keys["inchikey"])
    except Exception as error:
        logging.getLogger(__name__).error("ChEMBL profile processing failed: %s", type(error).__name__)
        return {
            "available": False,
            "found": False,
            "message": "Ошибка обработки ответа ChEMBL. Подробности записаны в журнал приложения.",
            "warnings": ["processing_error"],
        }


@router.post("/conformer", response_model=ConformerResponse)
async def conformer(request: ConformerRequest):
    """3D-конформер малой молекулы (RDKit). seed меняет стартовую геометрию."""
    try:
        return await run_in_threadpool(
            generate_conformer, request.smiles, request.seed
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/depict")
async def depict(request: DepictRequest):
    """2D-изображение структуры в SVG (для экспорта и PDF-отчёта)."""
    try:
        svg = await run_in_threadpool(
            depict_svg, request.smiles, request.width, request.height
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return Response(content=svg, media_type="image/svg+xml")


@router.post("/adme", response_model=AdmeResponse)
async def adme(molecule: MoleculeRequest):
    """ADME-профиль: BOILED-Egg, радар биодоступности, ключевые свойства."""
    try:
        return await run_in_threadpool(compute_adme, molecule.smiles)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

@router.post("/specialized-activity", response_model=SpecializedActivityResponse)
async def specialized_activity(molecule: MoleculeRequest):
    """ПК «Антидот-Прогноз»: отдельные endpoint-модели для антидотной и рострегулирующей активности.

    Модели не включены без проверенного обучающего набора: в таком случае API
    возвращает `not_trained`, а не синтетический прогноз.
    """
    try:
        return await run_in_threadpool(
            predict_specialized_activity, molecule.smiles
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
