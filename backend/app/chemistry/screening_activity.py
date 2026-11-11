"""Separate experimental screening endpoints with exact source context admission."""
from rdkit import Chem

from app.ai_research_agent.config import storage_root
from app.ai_research_agent.model_registry import Registry
from app.ai_research_agent.molecular_features import molecule
from app.ai_research_agent.tdc_hiv import task_config as hiv_task
from app.ai_research_agent.tdc_hepg2 import task_config as hepg2_task

TASKS = {"hiv": hiv_task, "hepg2": hepg2_task}
TITLES = {"hiv": "ВИЧ: ингибирование репликации", "hepg2": "HepG2: снижение пролиферации, 24 ч"}
CONTEXTS = {
    "hiv": "NCI/MoleculeNet: подтверждённо и умеренно активные соединения объединены в положительный класс. "
           "Это скрининговый исход, без единого порога EC50; не клиническая эффективность и не активность против других вирусов.",
    "hepg2": "ToxCast APR_HepG2_CellLoss_24h_dn: клетки HepG2, 24 часа, исходная бинарная оценка снижения пролиферации. "
             "Не доказательство гибели клеток, лечения рака, поражения печени или защиты от парацетамола.",
}
DISCLAIMER = (
    "Экспериментальные модели отдельных тестов. Качество оценено на внутренней отложенной выборке "
    "по химическим каркасам; внешней валидации и отдельной калибровки вероятностей нет. "
    "Чувствительность и точность положительных прогнозов показываются отдельно от сбалансированной точности. "
    "Область применимости определяется эвристически; вне неё численный прогноз скрыт."
)


def _empty(key, status="not_trained", message=None):
    return dict(key=key, title=TITLES[key], context=CONTEXTS[key], status=status,
                model_id=None, model_status=None, probability=None, max_similarity=None,
                metrics={}, n_train=0, n_test=0, test_positive=0, test_negative=0,
                trained_at=None, message=message or "Подходящая модель этого теста не подключена.")


def predict_screening(smiles):
    canonical = Chem.MolToSmiles(molecule(smiles), isomericSmiles=True)
    registry = Registry(storage_root())
    try:
        models = registry.list()
    except (ValueError, KeyError, OSError):
        return dict(canonical_smiles=canonical, predictions=[_empty(key, "error", "Реестр моделей недоступен или повреждён.") for key in TASKS], disclaimer=DISCLAIMER)
    predictions = []
    for key, config in TASKS.items():
        expected = config()
        candidates = [meta for meta in models if meta.get("status") != "archived"
                      and all(meta.get("task", {}).get(field) == expected[field]
                              for field in ("endpoint", "context", "kind", "domain", "units"))]
        qualified = [meta for meta in candidates if meta.get("quality", {}).get("passed")]
        if not qualified:
            predictions.append(_empty(key, "quality_failed" if candidates else "not_trained",
                                      "Модель не прошла текущий контроль качества; прогноз скрыт." if candidates else None))
            continue
        # Human approval, then recency; never choose by held-out test score.
        meta = max(qualified, key=lambda m: (m["status"] == "approved", m.get("trained_at", ""), m["id"]))
        try:
            result = registry.predict(meta["id"], canonical)
            domain, support = result["applicability"], meta["evaluation"]["support"]
            prediction = _empty(key)
            prediction.update(status="ready" if domain["in_domain"] else "out_of_domain",
                              model_id=meta["id"], model_status=meta["status"],
                              probability=result["probability"] if domain["in_domain"] else None,
                              max_similarity=domain["max_similarity"], metrics=meta["evaluation"]["test"],
                              n_train=support["train"]["molecules"], n_test=support["test"]["molecules"],
                              test_positive=support["test"]["positive"], test_negative=support["test"]["negative"],
                              trained_at=meta.get("trained_at"), message=None if domain["in_domain"] else "Структура вне области применимости этой модели.")
            predictions.append(prediction)
        except (ValueError, KeyError, OSError):
            predictions.append(_empty(key, "error", "Артефакт модели не прошёл проверку целостности или не загрузился."))
    return dict(canonical_smiles=canonical, predictions=predictions, disclaimer=DISCLAIMER)
