"""Technical fixtures only: no real root measurements or scientific training."""
import hashlib

import pytest

from app.ai_research_agent.config import Provenance, TaskConfig
from app.ai_research_agent.model_registry import Registry
from app.ai_research_agent.orchestrator import ResearchAgent
from app.ai_research_agent.root_protocol import ROOT_ENDPOINT, validate_root_dataset
from app.ai_research_agent.security import write_json
from app.ai_research_agent.training import train

CSV = "smiles,value\nCCO,1.25\nCCN,0\nCCC,\n"


def root_task(**overrides):
    config = dict(name="Technical root fixture", domain="growth", kind="regression",
                  endpoint=ROOT_ENDPOINT, units="ratio", context="Arabidopsis thaliana; technical fixture, not experimental data")
    config.update(overrides)
    return TaskConfig(**config)


def protocol(raw=CSV):
    return dict(species="Arabidopsis thaliana", ecotype="Col-0",
                seedling_age_at_treatment_days=0, compound_concentration_uM=10,
                exposure_duration_h=168, medium="Technical fixture medium",
                light_cycle="Technical fixture light cycle", matched_control="Matched fixture DMSO wells",
                replicate_design="Fixture replicate means retained with source identifiers",
                measurement_method="Fixture primary-root length, not area",
                normalization="treated_primary_root_length / matched_control_primary_root_length",
                dataset_sha256=hashlib.sha256(raw.encode('utf-8')).hexdigest())


def provenance(task):
    return Provenance(source_url="https://example.org/fixture.csv", doi="test-fixture-not-science",
                      license="CC0-1.0", license_url="https://example.org/license",
                      source_version="fixture", retrieved_at="2026-11-18T00:00:00Z", curator="Technical fixture",
                      experimental=True, endpoint=task.endpoint, units=task.units, context=task.context)


def evaluation():
    # These fabricated scores reproduce an admission bypass, not model quality.
    return dict(test_used_for_selection=False, beats_baseline=True,
                test=dict(r2=.8, mae=.1), baseline_test=dict(mae=.3),
                support=dict(test=dict(molecules=30, scaffolds=10)))


def test_draft_can_be_created_but_not_imported_or_fitted(tmp_path):
    task = root_task()
    agent = ResearchAgent(tmp_path)
    identifier = agent.create(task)["id"]
    with pytest.raises(ValueError, match="root_protocol"):
        agent.import_csv(identifier, CSV, provenance(task))
    assert not (tmp_path / "tasks" / identifier / "dataset.json").exists()
    with pytest.raises(ValueError, match="root_protocol"):
        train(None, None, None, task)


@pytest.mark.parametrize("field,value", [("domain", "qsar"), ("kind", "classification"),
                                         ("units", "%"), ("endpoint", "root_area")])
def test_root_semantics_cannot_be_changed_by_one_field(field, value):
    with pytest.raises(ValueError, match="primary-root regression"):
        root_task(**{field:value})


@pytest.mark.parametrize("field,value", [("species", "Oryza sativa"), ("ecotype", "  "),
    ("compound_concentration_uM", True), ("compound_concentration_uM", float('nan')),
    ("exposure_duration_h", 0), ("seedling_age_at_treatment_days", -1),
    ("normalization", "root tissue pixel area / control")])
def test_incompatible_or_incomplete_protocol_rejected(field, value):
    with pytest.raises(ValueError):
        root_task(root_protocol=dict(protocol(), **{field:value}))


def test_import_binds_exact_csv_and_retains_growth_above_control(tmp_path):
    task = root_task(root_protocol=protocol())
    agent = ResearchAgent(tmp_path)
    identifier = agent.create(task)["id"]
    imported = agent.import_csv(identifier, CSV, provenance(task))
    assert imported['measurements'] == 2
    assert imported['issues'] == [{'row':4, 'category':'missing_label'}]
    assert imported['dataset_sha256'] == task.root_protocol.dataset_sha256
    with pytest.raises(ValueError, match="checksum"):
        agent.import_csv(identifier, CSV.replace('1.25','1.5'), provenance(task))
    assert agent.task(identifier).root_protocol == task.root_protocol


def test_negative_ratios_rejected_even_with_matching_hash(tmp_path):
    text = CSV.replace('1.25', '-.1')
    task = root_task(root_protocol=protocol(text))
    agent = ResearchAgent(tmp_path)
    with pytest.raises(ValueError, match="nonnegative"):
        agent.import_csv(agent.create(task)['id'], text, provenance(task))


def test_worker_validation_also_binds_exact_bytes():
    task = root_task(root_protocol=protocol())
    with pytest.raises(ValueError, match="checksum"):
        validate_root_dataset(task, CSV.replace('\n','\r\n').encode(), [{'value':1.25}])
    validate_root_dataset(task, CSV.encode(), [{'value':1.25}, {'value':0}])


def test_worker_rejects_replaced_csv_before_features_or_training(tmp_path, monkeypatch):
    import app.ai_research_agent.molecular_features as features
    from app.ai_research_agent.orchestrator import execute_run
    from app.ai_research_agent.security import read_json
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        monkeypatch.setenv(name, '1')
    task = root_task(root_protocol=protocol())
    write_json(tmp_path / 'task.json', task.model_dump())
    write_json(tmp_path / 'provenance.json', provenance(task).model_dump())
    write_json(tmp_path / 'request.json', dict(action='train'))
    (tmp_path / 'dataset.csv').write_text(CSV.replace('1.25','1.5'), encoding='utf-8', newline='')
    def no_features(*args, **kwargs):
        pytest.fail('Changed experimental data reached feature preparation')
    monkeypatch.setattr(features, 'prepare', no_features)
    execute_run(str(tmp_path))
    state = read_json(tmp_path / 'state.json')
    assert state['status'] == 'failed' and 'checksum' in state['error']
    assert not (tmp_path / 'preparation.json').exists() and not (tmp_path / 'models').exists()


def test_old_approved_root_record_cannot_bypass_protocol(tmp_path):
    identifier = 'a' * 32
    registry = Registry(tmp_path)
    meta = dict(id=identifier, status='approved', trained_at='2026-11-18T00:00:00Z',
                task=root_task().model_dump(), evaluation=evaluation())
    path = registry.root / identifier / 'metadata.json'
    write_json(path, meta)
    before = path.read_bytes()
    checked = registry.metadata(identifier)
    assert checked['status'] == 'approved' and not checked['quality']['passed']
    with pytest.raises(ValueError, match="experimental evidence"):
        registry.predict(identifier, 'CCO')
    assert path.read_bytes() == before  # User record is preserved, never rewritten.


def test_registry_rechecks_source_and_protocol_dataset_binding(tmp_path):
    identifier = 'a' * 32
    task = root_task(root_protocol=protocol())
    registry = Registry(tmp_path)
    meta = dict(id=identifier, status='experimental', trained_at='2026-11-18T00:00:00Z',
                task=task.model_dump(), source=provenance(task).model_dump(),
                dataset_sha256=task.root_protocol.dataset_sha256, evaluation=evaluation())
    path = registry.root / identifier / 'metadata.json'
    write_json(path, meta)
    assert registry.metadata(identifier)['quality']['passed']
    meta['dataset_sha256'] = '0' * 64
    write_json(path, meta)
    assert not registry.metadata(identifier)['quality']['passed']
    meta['dataset_sha256'] = task.root_protocol.dataset_sha256
    meta['source']['context'] = 'Different treatment conditions from the declared task'
    write_json(path, meta)
    assert not registry.metadata(identifier)['quality']['passed']
