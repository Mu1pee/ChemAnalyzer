"""Experimental CYP inhibition; separate qualified models, never pooled labels."""
from rdkit import Chem

from app.ai_research_agent.config import storage_root
from app.ai_research_agent.model_registry import Registry
from app.ai_research_agent.molecular_features import molecule
from app.ai_research_agent.tdc_cyp import FILES, task_config

DISCLAIMER = (
    "Исследовательский прогноз ингибирования отдельной изоформы CYP по данным TDC/Veith. "
    "Это не прогноз клинического лекарственного взаимодействия, метаболизма или антидотной активности. "
    "Качество измерено на внутреннем отложенном тесте по химическим каркасам; внешней валидации нет. "
    "Область применимости определяется эвристически; вне неё численный прогноз скрыт."
)


def _empty(isoform, status="not_trained", message=None):
    return dict(isoform=isoform, status=status, model_id=None, model_status=None,
                probability=None, max_similarity=None, metrics={}, n_train=0, n_test=0,
                trained_at=None, message=message or "Подходящая модель этой изоформы не подключена.")


def predict_cyp(smiles):
    canonical = Chem.MolToSmiles(molecule(smiles), isomericSmiles=True)
    registry = Registry(storage_root())
    try:
        models = registry.list()
    except (ValueError, KeyError, OSError):
        models = []
        return dict(canonical_smiles=canonical,
                    predictions=[_empty(key, "error", "Реестр моделей недоступен или повреждён.") for key in FILES],
                    disclaimer=DISCLAIMER)
    predictions = []
    for isoform in FILES:
        expected = task_config(isoform)
        candidates = [meta for meta in models if meta.get("status") != "archived"
                      and all(meta.get("task", {}).get(key) == expected[key] for key in ("endpoint", "context", "kind", "domain", "units"))]
        qualified = [meta for meta in candidates if meta.get("quality", {}).get("passed")]
        if not qualified:
            predictions.append(_empty(isoform, "quality_failed" if candidates else "not_trained",
                                      "Модель не прошла текущий контроль качества; прогноз скрыт." if candidates else None))
            continue
        # Never choose an algorithm/model by its test score at prediction time.
        meta = max(qualified, key=lambda m: (m["status"] == "approved", m.get("trained_at", ""), m["id"]))
        try:
            result = registry.predict(meta["id"], canonical)
            domain = result["applicability"]
            predictions.append(dict(isoform=isoform,
                                    status="ready" if domain["in_domain"] else "out_of_domain",
                                    model_id=meta["id"], model_status=meta["status"], probability=result["probability"],
                                    max_similarity=domain["max_similarity"], metrics=meta["evaluation"]["test"],
                                    n_train=meta["evaluation"]["support"]["train"]["molecules"],
                                    n_test=meta["evaluation"]["support"]["test"]["molecules"],
                                    trained_at=meta.get("trained_at"),
                                    message=None if domain["in_domain"] else "Структура вне области применимости этой модели."))
        except (ValueError, KeyError, OSError):
            predictions.append(_empty(isoform, "error", "Артефакт модели не прошёл проверку целостности или не загрузился."))
    return dict(canonical_smiles=canonical, predictions=predictions, disclaimer=DISCLAIMER)
