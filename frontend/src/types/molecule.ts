export type IdentificationStatus = "found" | "not_found" | "unavailable";
export type CheckStatus = "found" | "not_found" | "unavailable" | "skipped";

export interface SimilarCompound {
  cid: number;
  title: string | null;
  iupac_name: string | null;
  inchikey: string | null;
  source_url: string | null;
}

export interface IdentificationResult {
  status: IdentificationStatus;
  found: boolean;
  match_type: "exact" | "connectivity" | null;
  cid: number | null;
  title: string | null;
  iupac_name: string | null;
  synonyms: string[];
  inchikey: string | null;
  source: string;
  source_url: string | null;
  message: string | null;
  checks: Record<string, CheckStatus>;
  similar: SimilarCompound[];
  similarity_threshold: number;
}

export interface MoleculeResponse {
  input_smiles: string;
  canonical_smiles: string;
  formula: string;
  molecular_weight: number;
  logp: number;
  tpsa: number;
  hbd: number;
  hba: number;
  rotatable_bonds: number;
  rings: number;
  heavy_atoms: number;
  aromatic_atoms: number;
  atom_count: number;
  bond_count: number;
  fragments: number;
  lipinski_violations: number;
  lipinski_passes: boolean;
}

export interface HistoryItem {
  id: string;
  analyzedAt: string;
  formula: string;
  smiles: string;
  title: string | null;
  cid: number | null;
  summary: string;
}

// ---------- биологическая активность ----------

export interface ActivitySupport {
  drug: string;
  similarity: number;
}

export interface PredictedActivity {
  name: string;
  score: number;
  confidence: string;
  support: ActivitySupport[];
}

export interface NearestDrug {
  name: string;
  similarity: number;
  activities: string[];
}

export interface DrugRule {
  name: string;
  passed: boolean;
  violations: string[];
}

export interface Druglikeness {
  qed: number;
  qed_label: string;
  rules: DrugRule[];
  gi_absorption: string;
  bbb_permeant: string;
  pains_alerts: string[];
  brenk_alerts: string[];
  disclaimer: string;
}

export interface ActivityResponse {
  method: string;
  reference_size: number;
  activities: PredictedActivity[];
  nearest: NearestDrug[];
  message: string | null;
  disclaimer: string;
  druglikeness: Druglikeness;
  qsar: QsarResult;
}

export interface ChemblMechanism {
  molecule_id: string | null;
  action: string | null;
  action_type: string | null;
  target_id: string | null;
  target_name: string | null;
}

export interface ChemblIndication {
  name: string;
  max_phase: number | null;
}

export interface ChemblTarget {
  target_id: string;
  target_name: string | null;
  organism: string | null;
  best_pchembl: number;
  measurements: number;
  activity_types: string[];
}

export interface ChemblSimilar {
  chembl_id: string;
  name: string | null;
  similarity: number;
  max_phase: number | null;
  mechanisms: ChemblMechanism[];
}

export interface ChemblResponse {
  available: boolean;
  found: boolean;
  chembl_id: string | null;
  name: string | null;
  max_phase: number | null;
  source_url: string | null;
  mechanisms: ChemblMechanism[];
  indications: ChemblIndication[];
  targets: ChemblTarget[];
  similar: ChemblSimilar[];
  message: string | null;
  source: string;
  cached: boolean;
  stale: boolean;
  partial: boolean;
  retrieved_at: string | null;
  warnings: string[];
}

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string;
}

// ---------- QSAR и ассистент ----------

export interface QsarPrediction {
  model_id: string | null;
  model_version: string | null;
  target_id: string;
  target_name: string;
  chembl_name: string | null;
  probability: number | null;
  domain: string;
  max_similarity: number;
  cv_auc: number;
  cv_balanced_accuracy: number;
  validation_method: string;
  n_train: number;
  active_pchembl: number;
}

export interface QsarResult {
  status: "ready" | "not_trained" | "error";
  available: boolean;
  message: string | null;
  models_loaded: number;
  predictions: QsarPrediction[];
  disclaimer: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export type AssistantMode = "review" | "learn";

export interface AssistantStatus {
  configured: boolean;
  model: string;
}

// ---------- 3D-структуры ----------

export interface ConformerResponse {
  molblock: string;
  sdf: string;
  pdb: string;
  num_atoms: number;
  method: string;
  seed: number;
  warnings: string[];
  note: string;
}

export interface TargetProtein {
  accession: string;
  description: string | null;
}

export interface TargetProteins {
  chembl_id: string;
  name: string | null;
  target_type: string | null;
  proteins: TargetProtein[];
}

export interface ProteinStructure {
  uniprot: string;
  entry_id: string | null;
  gene: string | null;
  organism: string | null;
  description: string | null;
  mean_plddt: number | null;
  plddt_label: string | null;
  model_version: number | null;
  residues: number | null;
  fragments: number;
  pdb: string;
  attribution: string;
  disclaimer: string;
}

// ---------- ADME (в духе SwissADME) ----------

export interface Ellipse {
  cx: number;
  cy: number;
  a: number;
  b: number;
  angle: number;
}

export interface BoiledEggModel {
  tpsa: number;
  wlogp: number;
  gi_absorption: boolean;
  bbb_permeant: boolean;
  white: Ellipse;
  yolk: Ellipse;
  source: string;
}

export interface RadarAxis {
  key: string;
  label: string;
  value: number;
  ok_min: number;
  ok_max: number;
  in_range: boolean;
  unit: string;
}

export interface AdmeResponse {
  boiled_egg: BoiledEggModel;
  radar: RadarAxis[];
  physchem: {
    formula: string;
    molecular_weight: number;
    heavy_atoms: number;
    aromatic_heavy_atoms: number;
    fsp3: number;
    rotatable_bonds: number;
    hba: number;
    hbd: number;
    molar_refractivity: number;
    tpsa: number;
    wlogp: number;
  };
  solubility: {
    esol_logs: number;
    esol_mol_l: number;
    esol_mg_ml: number;
    esol_class: string;
  };
  pharmacokinetics: {
    gi_absorption: string;
    bbb_permeant: string;
    log_kp: number;
  };
  druglikeness: DrugRule[];
  medchem: {
    pains: string[];
    brenk: string[];
    lead_likeness: DrugRule;
    synthetic_accessibility: number | null;
  };
  not_computed: string[];
  notes: string[];
}

// ---------- ПК «Антидот-Прогноз» ----------

export interface SpecializedModelPrediction {
  endpoint: string;
  context: string;
  status: "ready" | "out_of_domain";
  probability: number | null;
  predicted_label: 0 | 1 | null;
  similarity: number;
  domain_label: string;
  model_version: string;
  trained_at: string | null;
  n_train: number;
  n_active: number;
  n_inactive: number;
  metrics: Record<string, number>;
  dataset_source: string;
  message: string | null;
}

export interface SpecializedDomainResult {
  domain: "antidote" | "growth_regulating";
  title: string;
  status: "ready" | "not_trained" | "error";
  models_available: number;
  predictions: SpecializedModelPrediction[];
  message: string | null;
}

export interface SpecializedActivityResponse {
  input_smiles: string;
  canonical_smiles: string;
  antidote: SpecializedDomainResult;
  growth_regulating: SpecializedDomainResult;
  disclaimer: string;
}

export interface CypPrediction {
  isoform: string;
  status: "ready" | "out_of_domain" | "not_trained" | "quality_failed" | "error";
  model_id: string | null;
  model_status: string | null;
  probability: number | null;
  max_similarity: number | null;
  metrics: Record<string, number>;
  n_train: number;
  n_test: number;
  trained_at: string | null;
  message: string | null;
}

export interface CypResponse {
  canonical_smiles: string;
  predictions: CypPrediction[];
  disclaimer: string;
}

export interface ScreeningPrediction extends Omit<CypPrediction, "isoform"> {
  key: "hiv" | "hepg2";
  title: string;
  context: string;
  test_positive: number;
  test_negative: number;
}

export interface ScreeningResponse {
  canonical_smiles: string;
  predictions: ScreeningPrediction[];
  disclaimer: string;
}
