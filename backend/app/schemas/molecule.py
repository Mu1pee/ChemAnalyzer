from pydantic import BaseModel, Field


class MoleculeRequest(BaseModel):
    smiles: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="SMILES представление структуры",
    )


class SimilarCompound(BaseModel):
    cid: int
    title: str | None = None
    iupac_name: str | None = None
    inchikey: str | None = None
    source_url: str | None = None


class IdentificationResult(BaseModel):
    # found | not_found | unavailable — «недоступен» не равно «не найдено»
    status: str
    found: bool
    match_type: str | None = None  # exact | connectivity
    cid: int | None = None
    title: str | None = None
    iupac_name: str | None = None
    synonyms: list[str] = []
    inchikey: str | None = None
    source: str = "PubChem"
    source_url: str | None = None
    message: str | None = None
    checks: dict[str, str] = {}
    similar: list[SimilarCompound] = []
    similarity_threshold: int = 90


class MoleculeResponse(BaseModel):
    input_smiles: str
    canonical_smiles: str
    formula: str
    molecular_weight: float
    logp: float
    tpsa: float
    hbd: int
    hba: int
    rotatable_bonds: int
    rings: int
    heavy_atoms: int
    aromatic_atoms: int
    atom_count: int
    bond_count: int
    fragments: int = 1
    lipinski_violations: int
    lipinski_passes: bool


# ---------- биологическая активность ----------


class ActivitySupport(BaseModel):
    drug: str
    similarity: float


class PredictedActivity(BaseModel):
    name: str
    score: float
    confidence: str
    support: list[ActivitySupport] = []


class NearestDrug(BaseModel):
    name: str
    similarity: float
    activities: list[str] = []


class DrugRule(BaseModel):
    name: str
    passed: bool
    violations: list[str] = []


class Druglikeness(BaseModel):
    qed: float
    qed_label: str
    rules: list[DrugRule]
    gi_absorption: str
    bbb_permeant: str
    pains_alerts: list[str] = []
    brenk_alerts: list[str] = []
    disclaimer: str


class QsarPrediction(BaseModel):
    model_id: str | None = None
    model_version: str | None = None
    target_id: str
    target_name: str
    chembl_name: str | None = None
    probability: float | None
    domain: str
    max_similarity: float
    cv_auc: float
    cv_balanced_accuracy: float
    validation_method: str
    n_train: int
    active_pchembl: float


class QsarResult(BaseModel):
    status: str = "not_trained"  # ready | not_trained | error
    available: bool
    message: str | None = None
    models_loaded: int = 0
    predictions: list[QsarPrediction] = []
    disclaimer: str = ""


class ActivityResponse(BaseModel):
    method: str
    reference_size: int
    activities: list[PredictedActivity] = []
    nearest: list[NearestDrug] = []
    message: str | None = None
    disclaimer: str
    druglikeness: Druglikeness
    qsar: QsarResult


class ChemblMechanism(BaseModel):
    molecule_id: str | None = None
    action: str | None = None
    action_type: str | None = None
    target_id: str | None = None
    target_name: str | None = None


class ChemblIndication(BaseModel):
    name: str
    max_phase: float | None = None


class ChemblTarget(BaseModel):
    target_id: str
    target_name: str | None = None
    organism: str | None = None
    best_pchembl: float
    measurements: int
    activity_types: list[str] = []


class ChemblSimilar(BaseModel):
    chembl_id: str
    name: str | None = None
    similarity: float
    max_phase: float | None = None
    mechanisms: list[ChemblMechanism] = []


class ChemblResponse(BaseModel):
    available: bool
    found: bool
    chembl_id: str | None = None
    name: str | None = None
    max_phase: float | None = None
    source_url: str | None = None
    mechanisms: list[ChemblMechanism] = []
    indications: list[ChemblIndication] = []
    targets: list[ChemblTarget] = []
    similar: list[ChemblSimilar] = []
    message: str | None = None
    source: str = "ChEMBL"
    cached: bool = False
    stale: bool = False
    partial: bool = False
    retrieved_at: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ConformerRequest(BaseModel):
    smiles: str = Field(..., min_length=1, max_length=10000)
    seed: int = Field(42, ge=0, le=1_000_000)


class DepictRequest(BaseModel):
    smiles: str = Field(..., min_length=1, max_length=10000)
    width: int = Field(480, ge=120, le=2000)
    height: int = Field(360, ge=120, le=2000)


class ConformerResponse(BaseModel):
    molblock: str
    sdf: str
    pdb: str
    num_atoms: int
    method: str
    seed: int = 42
    warnings: list[str] = []
    note: str


# ---------- ADME (в духе SwissADME) ----------


class Ellipse(BaseModel):
    cx: float
    cy: float
    a: float
    b: float
    angle: float


class BoiledEggModel(BaseModel):
    tpsa: float
    wlogp: float
    gi_absorption: bool
    bbb_permeant: bool
    white: Ellipse
    yolk: Ellipse
    source: str


class RadarAxis(BaseModel):
    key: str
    label: str
    value: float
    ok_min: float
    ok_max: float
    in_range: bool
    unit: str = ""


class AdmePhyschem(BaseModel):
    formula: str
    molecular_weight: float
    heavy_atoms: int
    aromatic_heavy_atoms: int
    fsp3: float
    rotatable_bonds: int
    hba: int
    hbd: int
    molar_refractivity: float
    tpsa: float
    wlogp: float


class AdmeSolubility(BaseModel):
    esol_logs: float
    esol_mol_l: float
    esol_mg_ml: float
    esol_class: str


class AdmePharmacokinetics(BaseModel):
    gi_absorption: str
    bbb_permeant: str
    log_kp: float


class AdmeMedchem(BaseModel):
    pains: list[str] = []
    brenk: list[str] = []
    lead_likeness: DrugRule
    synthetic_accessibility: float | None = None


class AdmeResponse(BaseModel):
    boiled_egg: BoiledEggModel
    radar: list[RadarAxis]
    physchem: AdmePhyschem
    solubility: AdmeSolubility
    pharmacokinetics: AdmePharmacokinetics
    druglikeness: list[DrugRule]
    medchem: AdmeMedchem
    not_computed: list[str] = []
    notes: list[str] = []


# ---------- ПК «Антидот-Прогноз» ----------

class SpecializedModelPrediction(BaseModel):
    endpoint: str
    context: str
    status: str  # ready | out_of_domain
    probability: float | None = None
    predicted_label: int | None = None  # 1 = activity per dataset label; 0 = inactive
    similarity: float
    domain_label: str
    model_version: str
    trained_at: str | None = None
    n_train: int
    n_active: int
    n_inactive: int
    metrics: dict[str, float] = Field(default_factory=dict)
    dataset_source: str
    message: str | None = None


class SpecializedDomainResult(BaseModel):
    domain: str
    title: str
    status: str  # ready | not_trained | error
    models_available: int = 0
    predictions: list[SpecializedModelPrediction] = Field(default_factory=list)
    message: str | None = None


class SpecializedActivityResponse(BaseModel):
    input_smiles: str
    canonical_smiles: str
    antidote: SpecializedDomainResult
    growth_regulating: SpecializedDomainResult
    disclaimer: str
