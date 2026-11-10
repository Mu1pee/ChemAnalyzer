import type { Tab } from "../components/ResultsPanel";

export type ResearchPreset = {
  name: string; domain: "qsar" | "admet" | "growth" | "antidote_catalog";
  endpoint: string; units: string; context: string; kind: "regression" | "classification";
};
export type BioGroup = "pharmacology" | "admet" | "science" | "sources";
export type BioModule = {
  id: string; name: string; group: BioGroup; method: string; scope: string;
  status: "calculation" | "qsar" | "dataset" | "key" | "source";
  tab?: Tab; preset?: ResearchPreset;
};

export const BIO_GROUPS: { id: BioGroup; name: string }[] = [
  { id: "pharmacology", name: "Фармакология" },
  { id: "admet", name: "ADMET" },
  { id: "science", name: "Научный анализ" },
  { id: "sources", name: "Базы данных" }
];

function classification(name: string, endpoint: string): ResearchPreset {
  return { name, domain: "qsar", endpoint, units: "0/1", kind: "classification", context: "До импорта определить организм, assay, концентрацию, время и экспериментальное правило меток." };
}

export const BIO_MODULES: BioModule[] = [
  { id: "spectrum", group: "pharmacology", name: "Спектр биоактивности", method: "Morgan · Tanimoto", scope: "Сходство с известными препаратами", status: "calculation", tab: "activity" },
  { id: "targets", group: "pharmacology", name: "Мишени и QSAR", method: "Random Forest · scaffold CV", scope: "Отдельная модель для каждой мишени", status: "qsar", tab: "activity" },
  { id: "antibacterial", group: "pharmacology", name: "Антибактериальная активность", method: "Экспериментальные MIC / IC50", scope: "Штамм, среда и протокол опыта", status: "dataset", preset: classification("Антибактериальная активность", "antibacterial_assay") },
  { id: "antiviral", group: "pharmacology", name: "Противовирусная активность", method: "Экспериментальные EC50", scope: "Вирус, клеточная линия и цитотоксичность", status: "dataset", preset: classification("Противовирусная активность", "antiviral_assay") },
  { id: "cytotoxicity", group: "pharmacology", name: "Цитотоксичность", method: "Жизнеспособность клеток", scope: "Отдельная клеточная линия и экспозиция", status: "dataset", preset: classification("Цитотоксичность", "cell_viability") },
  { id: "antidote", group: "pharmacology", name: "Антидотная активность", method: "Защита от парацетамола", scope: "Проверенные endpoint-модели", status: "dataset", tab: "antidote", preset: { ...classification("Защита от парацетамола", "rescue_from_acetaminophen_injury"), domain: "antidote_catalog", context: "Токсикант: парацетамол (acetaminophen). До импорта определить вид, ткань, дозу токсиканта и соединения, время, контроль и readout." } },
  { id: "growth", group: "pharmacology", name: "Росторегулирующая активность", method: "Arabidopsis thaliana", scope: "Длина первичного корня / контроль", status: "dataset", tab: "antidote", preset: { name: "Arabidopsis: первичный корень", domain: "growth", endpoint: "primary_root_length_relative_to_control", kind: "regression", units: "ratio", context: "Arabidopsis thaliana: primary root length relative to matched control. До импорта определить экотип, возраст, дозу, время, среду и режим освещения." } },
  { id: "adme", group: "admet", name: "ADME-профиль", method: "RDKit · BOILED-Egg · ESOL", scope: "Проницаемость и физико-химические оценки", status: "calculation", tab: "adme" },
  { id: "drug", group: "admet", name: "Сходство с лекарствами", method: "Липински · Вебер · PAINS", scope: "Структурные правила и фильтры", status: "calculation", tab: "drug" },
  { id: "hydration", group: "admet", name: "Энергия гидратации", method: "FreeSolv · kcal/mol", scope: "Экспериментальные значения гидратации", status: "dataset", preset: { name: "FreeSolv: энергия гидратации", domain: "admet", endpoint: "hydration_free_energy", units: "kcal/mol", kind: "regression", context: "FreeSolv v0.52 small neutral molecules; hydration free energy in water; source reference conditions" } },
  { id: "cyp", group: "admet", name: "Цитохромы P450", method: "CYP1A2 · 2C9 · 2C19 · 2D6 · 3A4", scope: "Изоформы и тип действия раздельно", status: "dataset", preset: classification("CYP: отдельная изоформа", "cyp_inhibition_single_isoform") },
  { id: "metabolism", group: "admet", name: "Метаболическая стабильность", method: "Микросомы / гепатоциты", scope: "Вид организма, T½ и условия инкубации", status: "dataset", preset: { name: "Метаболическая стабильность", domain: "admet", endpoint: "microsomal_half_life", kind: "regression", units: "min", context: "До импорта определить вид, систему микросом, концентрацию соединения и протокол инкубации." } },
  { id: "toxicity", group: "admet", name: "Токсичность", method: "Отдельный токсикологический endpoint", scope: "Вид, путь введения и экспозиция", status: "dataset", preset: classification("Токсичность: один endpoint", "toxicity_single_endpoint") },
  { id: "literature", group: "science", name: "Научный ассистент", method: "Claude · контекст молекулы", scope: "Требуется ключ API", status: "key", tab: "assistant" },
  { id: "structure", group: "science", name: "Молекула и белок в 3D", method: "ETKDG · MMFF94 · AlphaFold", scope: "Конформер и структура мишени", status: "calculation", tab: "3d" },
  { id: "genes", group: "science", name: "Экспрессия генов", method: "Транскриптомные данные", scope: "Не реализовано: нужен отдельный pipeline", status: "dataset" },
  { id: "text", group: "science", name: "Извлечение из публикаций", method: "Химические сущности и связи", scope: "Не реализовано: нужен корпус с разметкой", status: "dataset" },
  { id: "pubchem", group: "sources", name: "PubChem", method: "CID · InChIKey · структура", scope: "Точное совпадение и кандидаты раздельно", status: "source", tab: "ident" },
  { id: "chembl", group: "sources", name: "ChEMBL", method: "Экспериментальные активности", scope: "Assay, мишень, тип измерения", status: "source", tab: "chembl" },
  { id: "registry", group: "sources", name: "Реестр моделей", method: "AI Research Agent", scope: "Эксперименты, метрики и версии", status: "calculation", tab: "research" },
  { id: "history", group: "sources", name: "История исследований", method: "Локальное хранилище", scope: "Структуры и результаты анализа", status: "calculation", tab: "history" }
];
