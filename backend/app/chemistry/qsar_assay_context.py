"""Separate human single-protein assays from cellular and tissue IC50 data."""
import re

PROFILE = {
    "profile_id": "human_single_protein_ic50_v1",
    "organism": "Homo sapiens",
    "bao_format": "BAO_0000357",
    "assay_type": "B",
    "confidence_score": 9,
    "description_conflicts": "Descriptions mentioning blood require separate protocol review.",
    "limitations": "Single-protein format is not proof of identical substrate, detection or incubation protocols.",
}

# Retain the source annotations rather than infer format from a target name,
# target type or a Binding (B) assay label.
ASSAY_FIELDS = (
    "assay_chembl_id", "target_chembl_id", "assay_type", "confidence_score",
    "assay_organism", "bao_format", "bao_label", "assay_cell_type",
    "cell_chembl_id", "assay_tissue", "tissue_chembl_id",
    "assay_subcellular_fraction", "variant_sequence", "description",
    "document_chembl_id",
)


def incompatibility(assay, target_id):
    if not isinstance(assay, dict):
        return "missing_assay_metadata"
    if (assay.get("target_chembl_id") != target_id or assay.get("assay_type") != "B"
            or assay.get("confidence_score") != 9):
        return "target_or_confidence"
    if assay.get("assay_organism") != "Homo sapiens":
        return "assay_organism_unknown_or_different"
    if assay.get("bao_format") != PROFILE["bao_format"]:
        return "assay_format_unknown_or_different"
    if any(assay.get(key) for key in (
        "assay_cell_type", "cell_chembl_id", "assay_tissue", "tissue_chembl_id",
        "assay_subcellular_fraction",
    )):
        return "cellular_tissue_or_fraction_context"
    if assay.get("variant_sequence"):
        return "variant_requires_separate_profile"
    # Some original records have a single-protein BAO tag and empty tissue
    # fields while explicitly describing a blood-based experiment. Keep those
    # records for review instead of trusting the structured tag over the text.
    # Do not reject "cell-free" or protein expression in cells by keyword alone.
    description = assay.get("description")
    if isinstance(description, str) and re.search(r"\b(?:whole[\s\-\u2010-\u2015]*)?blood\b", description, re.I):
        return "description_requires_context_review"
    if not isinstance(assay.get("assay_chembl_id"), str) or not assay["assay_chembl_id"]:
        return "missing_assay_identifier"
    return None


def source_record(assay):
    return {field: assay.get(field) for field in ASSAY_FIELDS}


def evidence_reasons(provenance, target_id):
    if not isinstance(provenance, dict) or provenance.get("assay_context") != PROFILE:
        return ["A versioned human single-protein IC50 assay context is required"]
    assays = provenance.get("assays")
    if not isinstance(assays, list) or not assays:
        return ["Original assay format/organism annotations are required"]
    identifiers = set()
    for assay in assays:
        if incompatibility(assay, target_id):
            return ["All contributing assays must match the human single-protein context"]
        identifier = assay["assay_chembl_id"]
        if identifier in identifiers:
            return ["Contributing assay identifiers must be unique"]
        identifiers.add(identifier)
    return []
