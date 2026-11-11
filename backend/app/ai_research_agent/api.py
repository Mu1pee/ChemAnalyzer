"""Local opt-in API. No arbitrary URL download, code execution or model upload."""
import os
import httpx
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Request, Depends
from urllib.parse import urlparse
from pydantic import BaseModel, Field

from .config import FREESOLV_TASK, Provenance, TaskConfig
from .data_discovery import discover
from .model_registry import Registry, Review, Approval
from .orchestrator import ResearchAgent
from .scheduler import Schedule, Scheduler
from .security import read_json

def local_origin(request: Request):
    origin = request.headers.get("origin")
    if request.method != "GET" and origin:
        parsed = urlparse(origin)
        if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost"):
            raise HTTPException(403, "Research mutations require a local application origin")


router = APIRouter(prefix="/api/research", tags=["AI Research Lab"], dependencies=[Depends(local_origin)])


@lru_cache(maxsize=1)
def agent():
    return ResearchAgent()


@lru_cache(maxsize=1)
def scheduler():
    return Scheduler(agent())


def enabled():
    return os.environ.get("CHEMANALYZER_RESEARCH_ENABLED") == "1"


def call(function, *args):
    if not enabled():
        raise HTTPException(403, "AI Research Lab disabled. Set CHEMANALYZER_RESEARCH_ENABLED=1 and restart backend.")
    try:
        return function(*args)
    except FileNotFoundError:
        raise HTTPException(404, "Task, dataset or model not found")
    except httpx.HTTPError as error:
        raise HTTPException(502, f"Source unavailable: {type(error).__name__}; retry later or import local data")
    except (ValueError, OSError) as error:
        raise HTTPException(400, str(error))


@router.get("/status")
def status():
    from .tdc_cyp import FILES, task_config
    from .tdc_hiv import task_config as hiv_task
    from .tdc_hepg2 import task_config as hepg2_task
    from .ncats_hlm import task_config as hlm_task
    return dict(enabled=enabled(), default_task=FREESOLV_TASK,
                hlm_task=hlm_task(),
                screening_tasks={"hiv": hiv_task(), "hepg2": hepg2_task()},
                cyp_tasks={key: task_config(key) for key in FILES}, api_cost_limit=0, worker_limit=1)


@router.get("/sources")
def sources(endpoint: str = "hydration_free_energy"):
    return discover(endpoint)


@router.get("/tasks")
def tasks():
    return call(lambda: agent().tasks())


@router.post("/tasks")
def create(task: TaskConfig):
    return call(lambda: agent().create(task))


class ImportRequest(BaseModel):
    csv_text: str = Field(max_length=8_000_000)
    provenance: Provenance


@router.post("/tasks/{identifier}/import")
def import_data(identifier: str, body: ImportRequest):
    return call(lambda: agent().import_csv(identifier, body.csv_text, body.provenance))


@router.post("/tasks/{identifier}/freesolv")
def freesolv(identifier: str):
    return call(lambda: agent().import_freesolv(identifier))


@router.post("/tasks/{identifier}/tdc-cyp")
def tdc_cyp(identifier: str):
    return call(lambda: agent().import_tdc_cyp(identifier))


@router.post("/tasks/{identifier}/tdc-hiv")
def tdc_hiv(identifier: str):
    return call(lambda: agent().import_tdc_hiv(identifier))


@router.post("/tasks/{identifier}/tdc-hepg2")
def tdc_hepg2(identifier: str):
    return call(lambda: agent().import_tdc_hepg2(identifier))


@router.post("/tasks/{identifier}/ncats-hlm")
def ncats_hlm(identifier: str):
    return call(lambda: agent().import_ncats_hlm(identifier))


@router.post("/tasks/{identifier}/{action}")
def start(identifier: str, action: str):
    return call(lambda: agent().start(identifier, action))


@router.get("/runs")
def runs():
    return call(lambda: agent().runs())


@router.get("/runs/{identifier}")
def run(identifier: str):
    return call(lambda: agent().run(identifier))


@router.post("/runs/{identifier}/cancel")
def cancel(identifier: str):
    return call(lambda: agent().cancel(identifier))


@router.get("/models")
def models():
    return call(lambda: Registry(agent().root).list())


@router.post("/schedules")
def save_schedule(body: Schedule):
    return call(lambda: scheduler().save(body))


@router.get("/schedules")
def schedules():
    return call(lambda: [dict(policy=read_json(p), state=read_json(p.parent / "state.json") if (p.parent / "state.json").exists() else None)
                         for p in agent().root.glob("schedules/*/policy.json")])


@router.post("/models/{identifier}/review")
def review(identifier: str, body: Review):
    return call(lambda: Registry(agent().root).review(identifier, body))


@router.post("/models/{identifier}/approve")
def approve(identifier: str, body: Approval):
    return call(lambda: Registry(agent().root).approve(identifier, body))


@router.post("/models/{identifier}/archive")
def archive(identifier: str):
    return call(lambda: Registry(agent().root).archive(identifier))


class Prediction(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)


@router.post("/models/{identifier}/predict")
def predict(identifier: str, body: Prediction):
    return call(lambda: Registry(agent().root).predict(identifier, body.smiles))


class ActivePrediction(Prediction):
    endpoint: str = Field(max_length=160)
    context: str = Field(max_length=2000)


@router.post("/active/predict")
def predict_active(body: ActivePrediction):
    return call(lambda: Registry(agent().root).predict_active(body.endpoint, body.context, body.smiles))
