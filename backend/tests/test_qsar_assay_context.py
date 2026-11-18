"""Software fixtures for assay-context separation, never scientific evidence."""
import copy
import hashlib
import json
import sys

import pytest

from app.chemistry.qsar_assay_context import PROFILE, incompatibility
from app.chemistry.qsar_evidence import FEATURE_CONFIG, admission
from training import revalidate_qsar as trainer


def protein_assay():
    return dict(assay_chembl_id="CHEMBL1", target_chembl_id="CHEMBL230",
                assay_type="B", confidence_score=9, assay_organism="Homo sapiens",
                bao_format="BAO_0000357", bao_label="single protein format",
                assay_cell_type=None, cell_chembl_id=None, assay_tissue=None,
                tissue_chembl_id=None, assay_subcellular_fraction=None,
                variant_sequence=None, description="Software fixture only")


def source_fixture(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    protein = protein_assay()
    cell = dict(protein, assay_chembl_id="CHEMBL2", bao_format="BAO_0000219",
                bao_label="cell-based format", assay_cell_type="HepG2")
    tissue = dict(protein, assay_chembl_id="CHEMBL3", bao_format="BAO_0000221",
                  bao_label="tissue-based format", assay_tissue="Blood")
    unknown = dict(protein, assay_chembl_id="CHEMBL4", bao_format=None, bao_label=None)
    assays = [protein, cell, tissue, unknown]
    records = [dict(assay_chembl_id=a["assay_chembl_id"], target_chembl_id="CHEMBL230",
                    target_organism="Homo sapiens", assay_type="B", standard_type="IC50",
                    standard_units="nM", standard_relation="=", standard_value="1000",
                    pchembl_value="6.0", canonical_smiles="CCO", activity_id=i,
                    data_validity_comment=None, potential_duplicate=0)
               for i, a in enumerate(assays, 1)]
    payloads = {
        "target.json": dict(organism="Homo sapiens", target_type="SINGLE PROTEIN"),
        "chembl-status.json": dict(chembl_db_version="ChEMBL_37"),
        "chembl-status-after.json": dict(chembl_db_version="ChEMBL_37"),
        "assays.json": dict(assays=assays, page_meta=dict(total_count=len(assays))),
        "activities-00000.json": dict(activities=records, page_meta=dict(total_count=len(records), offset=0)),
    }
    sources = []
    for name, data in payloads.items():
        raw = json.dumps(data).encode()
        (source / name).write_bytes(raw)
        sources.append(dict(file=name, sha256=hashlib.sha256(raw).hexdigest(), url="https://example.org/software-fixture/" + name))
    provenance = dict(source="ChEMBL", target_id="CHEMBL230", version="ChEMBL_37",
                      assay_id="panel", endpoint="IC50", units="nM", organism="Homo sapiens",
                      license="CC-BY-SA-3.0", sources=sources)
    (source / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    return source


def test_binding_label_and_human_target_do_not_pool_cell_tissue_or_unknown_formats(tmp_path):
    source = source_fixture(tmp_path)
    output = tmp_path / "curated"
    output.mkdir()
    records, allowed, provenance, _ = trainer.snapshot(source, output)
    assert len(records) == 4 and allowed == {"CHEMBL1"}
    rows, excluded = trainer.curate(records, allowed)
    assert len(rows) == 1 and excluded["assay_or_quality_filter"] == 3
    assert provenance["assay_context"] == PROFILE
    assert [a["assay_chembl_id"] for a in provenance["assays"]] == ["CHEMBL1"]
    assert provenance["assay_context_exclusions"] == {"assay_format_unknown_or_different": 3}
    # All original context records remain available for review.
    assert (source / "assays.json").read_bytes() == (output / "assays.json").read_bytes()


@pytest.mark.parametrize("change", [
    {"assay_organism": None}, {"assay_organism": "Ovis aries"},
    {"assay_cell_type": "HepG2"}, {"cell_chembl_id": "CHEMBL3307790"},
    {"assay_tissue": "Blood"}, {"tissue_chembl_id": "CHEMBL3638178"},
    {"assay_subcellular_fraction": "Microsomes"}, {"variant_sequence": {"mutation": "R120A"}},
])
def test_single_protein_tag_does_not_override_incompatible_original_annotations(change):
    assert incompatibility(dict(protein_assay(), **change), "CHEMBL230")


@pytest.mark.parametrize("description", [
    "In vitro inhibitory activity against human whole blood Prostaglandin G/H synthase 2",
    "Inhibitory concentration against human whole blood Prostaglandin G/H synthase 2 enzyme activity was determined",
    "Inhibition of human whole blood COX-2 assessed as production of PGE2 after 24 hrs by EIA",
    "Inhibition of COX-2 in human WHOLE-BLOOD",
    "Concentration required to inhibit cyclooxygenase-2 in human blood",
    "Activity of COX2 in human heparinized blood assessed as inhibition of LPS-induced PGE2 production after 24 hrs",
    "Inhibition of COX2 in LPS-stimulated human blood",
    "Inhibition of COX2 in human blood assessed as TxB2 level after 1 hr by enzyme immunoassay",
])
def test_description_contradicting_single_protein_tag_requires_review(description):
    assert incompatibility(dict(protein_assay(), description=description), "CHEMBL230") == "description_requires_context_review"


def test_cell_free_description_is_not_misclassified_as_cellular():
    assay = dict(protein_assay(), description="Inhibition of human recombinant COX2 in cell-free system by enzyme immunoassay")
    assert incompatibility(assay, "CHEMBL230") is None


def valid_metadata():
    scores = dict(balanced_accuracy=.8, roc_auc=.8, mcc=.6, pr_auc=.8)
    procedure = dict(algorithm="random_forest", software_fixture=True)
    provenance = dict(source="ChEMBL", target_id="CHEMBL230", organism="Homo sapiens",
                      endpoint="IC50", units="nM", license="CC-BY-SA-3.0", version="ChEMBL_37",
                      assay_context=copy.deepcopy(PROFILE), assays=[protein_assay()])
    support = {"train": dict(molecules=60, positive=30, negative=30, scaffolds=10),
               "validation": dict(molecules=20, positive=10, negative=10, scaffolds=8),
               "test": dict(molecules=60, positive=30, negative=30, scaffolds=10)}
    evaluation = dict(test=scores, baseline_test=dict(pr_auc=.5), test_used_for_selection=False,
                      beats_baseline=True, support=support, procedure=procedure,
                      split=dict(train=list(range(60)), validation=list(range(60, 80)), test=list(range(80, 140))),
                      y_randomization=dict(partition="train_only", roc_auc=.5, used_for_selection=False))
    return dict(schema_version=3, target_id="CHEMBL230", feature_config=FEATURE_CONFIG,
                provenance=provenance, metrics=scores, evaluation=evaluation,
                n_total=140, n_train=60, n_active=30, n_inactive=30, n_test=60, procedure=procedure)


def test_good_scores_need_contributing_assay_context_at_admission():
    meta = valid_metadata()
    assert admission(meta)["passed"]
    meta["provenance"]["assays"][0].update(bao_format="BAO_0000219", assay_cell_type="HepG2")
    result = admission(meta)
    assert not result["passed"] and any("context" in r for r in result["reasons"])


def test_old_schema_cannot_claim_new_context_contract_with_good_scores():
    meta = valid_metadata()
    meta["schema_version"] = 2
    meta["provenance"].pop("assay_context")
    assert not admission(meta)["passed"]


def test_curate_only_prepares_data_without_any_fit_or_prediction(tmp_path, monkeypatch):
    source = source_fixture(tmp_path)
    output = tmp_path / "prepared"
    monkeypatch.setattr(sys, "argv", ["revalidate_qsar", "--source-dir", str(source),
                                    "--output-dir", str(output), "--curate-only"])
    def forbidden(*args, **kwargs):
        raise AssertionError("Curation must not fit or evaluate an estimator")
    monkeypatch.setattr(trainer, "experiment", forbidden)
    assert trainer.main() == 0
    report = json.loads((output / "report.json").read_bytes())
    assert report["status"] == "curated_only" and not report["training_performed"]
    assert not report["evaluation_performed"] and not report["accepted"]
    assert report["provenance"]["compatible_assay_count"] == 1
    assert report["provenance"]["contributing_assay_count"] == 1
    assert json.loads((output / "manifest.json").read_bytes())["models"] == []
    assert not list(output.glob("*.joblib"))
