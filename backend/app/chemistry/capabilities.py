"""Catalog availability from the same scientific contracts used by inference."""
from app.ai_research_agent.config import FREESOLV_TASK, TaskConfig, storage_root, research_enabled
from app.ai_research_agent.model_registry import Registry, PREDICTABLE_STATES, select_task_model, task_matches
from app.ai_research_agent.security import utcnow
from app.ai_research_agent.tdc_cyp import FILES, task_config as cyp_task
from app.ai_research_agent.tdc_hiv import task_config as hiv_task
from app.ai_research_agent.tdc_hepg2 import task_config as hepg2_task
from app.ai_research_agent.ncats_hlm import task_config as hlm_task
from app.ai_research_agent.ncats_solubility import task_config as solubility_task


def supported_tasks():
    return {
        "cyp": [(key, cyp_task(key)) for key in FILES],
        "hiv": [("hiv", hiv_task())], "hepg2": [("hepg2", hepg2_task())],
        "metabolism": [("hlm", hlm_task())],
        "solubility": [("solubility", solubility_task())],
        # Preserve the historical source task, including its qsar domain.
        "hydration": [("freesolv", TaskConfig(**FREESOLV_TASK).model_dump())],
    }


def _state(key, status, task=None, model=None, message=None):
    task, model = task or {}, model or {}
    return dict(key=key, status=status, available=status in PREDICTABLE_STATES,
                model_id=model.get("id") or model.get("model_id"), model_status=model.get("status"),
                endpoint=task.get("endpoint"), context=task.get("context"), kind=task.get("kind"),
                domain=task.get("domain"), units=task.get("units"), message=message)


def _module(identifier, states):
    count = sum(state["available"] for state in states)
    if count:
        status = ("partial" if count < len(states) else "approved" if all(s["status"] == "approved" for s in states)
                  else "validated" if all(s["status"] in ("approved", "validated") for s in states) else "experimental")
    else:
        status = next((value for value in ("error", "quality_failed", "incompatible", "disabled", "archived")
                       if any(state["status"] == value for state in states)), "not_trained")
    return dict(id=identifier, status=status, available=bool(count), models_available=count,
                models_expected=len(states), states=states)


def _agent_state(registry, models, key, task, requires_lab=False):
    candidates, selected = select_task_model(models, task)
    if selected is not None:
        if requires_lab and not research_enabled():
            return _state(key, "disabled", task, selected,
                          message="Модель есть, но её прогноз доступен только во включённой AI Research Lab.")
        try:
            current = registry.verify_artifact(selected["id"])
            if (not task_matches(current, task) or current.get("status") not in PREDICTABLE_STATES
                    or current.get("quality", {}).get("passed") is not True):
                raise ValueError("Model admission changed during catalog lookup")
            return _state(key, current["status"], task, current)
        except (ValueError, KeyError, TypeError, OSError):
            return _state(key, "error", task, message="Файл выбранной модели отсутствует, повреждён или изменён; прогноз недоступен.")
    if candidates:
        return _state(key, "quality_failed", task, message="Совместимая модель не прошла текущие критерии качества.")
    if any(task_matches(meta, task) and meta.get("status") == "archived" for meta in models):
        return _state(key, "archived", task, message="Есть только архивная модель этого контекста.")
    if any(meta.get("task", {}).get("endpoint") == task["endpoint"] for meta in models):
        return _state(key, "incompatible", task, message="Найден endpoint, но контекст, тип задачи, domain или единицы не совпадают.")
    return _state(key, "not_trained", task, message="Совместимая обученная модель не подключена.")


def _qsar_capability():
    from .qsar import _load_models
    bundles, problem, rejected = _load_models()
    states = [_state(bundle["meta"].get("model_id", "qsar"), "experimental", bundle["meta"],
                     dict(model_id=bundle["meta"].get("model_id"), status="experimental")) for bundle in bundles]
    states += [_state(row.get("target_id") or "qsar", "quality_failed",
                      message="Модель мишени не прошла текущий допуск по отложенной проверке.") for row in rejected]
    if not states:
        states = [_state("qsar", "error" if problem else "not_trained",
                         message="Модели QSAR недоступны." if problem else "Допущенная модель мишени не подключена.")]
    return _module("targets", states)


def _specialized_capabilities():
    from .specialized_activity import _load_bundles
    grouped, problem = _load_bundles()
    modules = []
    for domain, identifier in (("antidote", "antidote"), ("growth_regulating", "growth")):
        bundles = grouped[domain]
        if problem:
            states = [_state(domain, "error", message="Хранилище специализированных моделей недоступно.")]
        elif bundles and "rejected" in bundles[0]:
            states = [_state(domain, "quality_failed", message="Специализированная модель не прошла допуск.")]
        elif not bundles:
            states = [_state(domain, "not_trained", message="Специализированная модель не обучена: нужен экспериментальный набор и протокол.")]
        else:
            states = [_state(str(index), "experimental", dict(bundle["meta"], kind="classification", units="0/1"),
                             dict(model_id=bundle["meta"].get("model_file"), status="experimental"))
                      for index, bundle in enumerate(bundles)]
        modules.append(_module(identifier, states))
    return modules


def model_capabilities():
    registry = Registry(storage_root())
    registry_error = None
    try:
        models = registry.list()
    except (ValueError, KeyError, TypeError, OSError):
        models, registry_error = [], "Реестр моделей недоступен. Статусы прогнозных моделей не подтверждены."
    modules = []
    for identifier, tasks in supported_tasks().items():
        states = [_state(key, "error", task, message=registry_error) if registry_error
                  else _agent_state(registry, models, key, task, requires_lab=identifier == "hydration") for key, task in tasks]
        modules.append(_module(identifier, states))
    modules += [_qsar_capability(), *_specialized_capabilities()]
    return dict(modules=modules, registry_models=len(models), registry_invalid=sum(m.get("status") == "invalid" for m in models),
                registry_approved=sum(m.get("status") == "approved" and m.get("quality", {}).get("passed") is True for m in models),
                registry_error=registry_error, checked_at=utcnow())
