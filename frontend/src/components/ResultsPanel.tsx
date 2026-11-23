import { useEffect, useState } from "react";
import { ArrowUpRight, Atom, Check, Copy, FlaskConical, LoaderCircle } from "lucide-react";
import type {
  ActivityResponse,
  AdmeResponse,
  AsyncState,
  ChemblResponse,
  HistoryItem,
  IdentificationResult,
  MoleculeResponse
} from "../types/molecule";
import ActivityTab from "./ActivityTab";
import AdmeTab from "./AdmeTab";
import AssistantPanel from "./AssistantPanel";
import ChemblTab from "./ChemblTab";
import CypTab from "./CypTab";
import ScreeningTab from "./ScreeningTab";
import DruglikenessTab from "./DruglikenessTab";
import HistoryTab from "./HistoryTab";
import IdentificationTab from "./IdentificationTab";
import PropertiesTab from "./PropertiesTab";
import StructureTab from "./StructureTab";
import AntidotePredictionTab from "./AntidotePredictionTab";
import ResearchLabTab from "./ResearchLabTab";
import BioactivityWorkspace from "./BioactivityWorkspace";
import type { ResearchPreset } from "../lib/bioactivity";
import "../styles/results-workspace.css";

export type Tab =
  | "bioactivity"
  | "props"
  | "adme"
  | "ident"
  | "drug"
  | "activity"
  | "antidote"
  | "chembl"
  | "cyp"
  | "screening"
  | "metabolism"
  | "solubility"
  | "3d"
  | "history"
  | "research"
  | "assistant";

export const TABS: { id: Tab; label: string }[] = [
  { id: "bioactivity", label: "Биоактивность" },
  { id: "props", label: "Свойства" },
  { id: "adme", label: "ADME" },
  { id: "ident", label: "Идентификация" },
  { id: "drug", label: "Drug-likeness" },
  { id: "activity", label: "Активность" },
  { id: "antidote", label: "Антидот-Прогноз" },
  { id: "chembl", label: "ChEMBL" },
  { id: "cyp", label: "CYP" },
  { id: "screening", label: "ВИЧ / HepG2" },
  { id: "metabolism", label: "Стабильность HLM" },
  { id: "solubility", label: "Растворимость" },
  { id: "3d", label: "3D" },
  { id: "history", label: "История" },
  { id: "research", label: "AI Research Lab" },
  { id: "assistant", label: "Ассистент" }
];

interface Props {
  tab: Tab;
  onTab: (tab: Tab) => void;
  result: MoleculeResponse | null;
  loading: boolean;
  identification: AsyncState<IdentificationResult>;
  adme: AsyncState<AdmeResponse>;
  activity: AsyncState<ActivityResponse>;
  chembl: AsyncState<ChemblResponse>;
  history: HistoryItem[];
  onSelectHistory: (item: HistoryItem) => void;
  onClearHistory: () => void;
}

const FULL_WIDTH_TABS: readonly Tab[] = ["history", "research", "assistant"];
const PANE_TITLES: Partial<Record<Tab, string>> = {
  activity: "Активность / QSAR",
  props: "Свойства",
  "3d": "3D-структура"
};

export default function ResultsPanel({
  tab,
  onTab,
  result,
  loading,
  identification,
  adme,
  activity,
  chembl,
  history,
  onSelectHistory,
  onClearHistory
}: Props) {
  const [copyNotice, setCopyNotice] = useState<string | null>(null);
  const [researchPreset, setResearchPreset] = useState<"default" | "qsar">("default");
  const [researchTask, setResearchTask] = useState<ResearchPreset | undefined>();

  useEffect(() => {
    if (!copyNotice) return;
    const timer = window.setTimeout(() => setCopyNotice(null), 1800);
    return () => window.clearTimeout(timer);
  }, [copyNotice]);

  function openResearch(preset?: ResearchPreset) {
    setResearchTask(preset);
    setResearchPreset("default");
    onTab("research");
  }

  async function copySmiles(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopyNotice("SMILES скопирован");
    } catch {
      setCopyNotice("Не удалось скопировать SMILES");
    }
  }

  const id = identification.data;
  // Название — только при точном совпадении. Совпадение «по связности» не
  // подтверждает тождество (стереоизомер, изотопы), поэтому в заголовок не выносится.
  const title = id?.found && id.match_type === "exact" ? id.title : null;
  const connectivityName =
    id?.found && id.match_type === "connectivity" ? id.title : null;

  function body() {
    if (tab === "research") return <ResearchLabTab initialPreset={researchPreset} initialTask={researchTask} />;
    if (tab === "history") {
      return (
        <HistoryTab
          items={history}
          onSelect={onSelectHistory}
          onClear={onClearHistory}
        />
      );
    }
    if (tab === "assistant") {
      return (
        <AssistantPanel
          result={result}
          identification={id}
          adme={adme}
          activity={activity}
          chembl={chembl}
        />
      );
    }

    if (loading) {
      return (
        <div className="analysis-start" role="status">
          <div className="analysis-illustration">
            <LoaderCircle className="analysis-spinner" size={32} aria-hidden="true" />
          </div>
          <h3>Анализируем структуру</h3>
          <p>RDKit рассчитывает дескрипторы молекулы.</p>
        </div>
      );
    }
    if (!result) {
      return (
        <div className="analysis-start">
          <div className="analysis-illustration">
            <Atom size={33} strokeWidth={1.5} aria-hidden="true" />
          </div>
          <h3>Запустите анализ структуры</h3>
          <p>Нарисуйте молекулу или импортируйте SMILES, затем запустите расчёт.</p>
          <a className="analysis-start__link" href="#analyze-structure">
            К кнопке анализа <ArrowUpRight size={14} aria-hidden="true" />
          </a>
        </div>
      );
    }

    switch (tab) {
      case "props":
        return <PropertiesTab result={result} />;
      case "adme":
        return <AdmeTab state={adme} />;
      case "ident":
        return <IdentificationTab state={identification} />;
      case "drug":
        return <DruglikenessTab result={result} state={activity} />;
      case "activity":
        return <ActivityTab state={activity} onTrainQsar={() => {
          setResearchTask(undefined);
          setResearchPreset("qsar");
          onTab("research");
        }} />;
      case "antidote":
        return <AntidotePredictionTab smiles={result.canonical_smiles} />;
      case "chembl":
        return <ChemblTab state={chembl} />;
      case "cyp":
        return <CypTab smiles={result.canonical_smiles} />;
      case "screening":
        return <ScreeningTab smiles={result.canonical_smiles} />;
      case "metabolism":
        return <ScreeningTab smiles={result.canonical_smiles} endpointKey="hlm" />;
      case "solubility":
        return <ScreeningTab smiles={result.canonical_smiles} endpointKey="solubility" />;
      case "3d":
        return (
          <StructureTab
            smiles={result.canonical_smiles}
            qsar={activity.data?.qsar.predictions ?? []}
            chembl={chembl.data}
          />
        );
      default:
        return null;
    }
  }

  if (tab === "bioactivity") return <BioactivityWorkspace onTab={onTab} onResearch={openResearch} activity={activity} hasMolecule={Boolean(result)} />;

  const paneTitle = PANE_TITLES[tab] ?? TABS.find((item) => item.id === tab)?.label;
  if (FULL_WIDTH_TABS.includes(tab)) {
    return (
      <section className={`analysis-pane analysis-pane--wide analysis-pane--${tab}`} aria-label={paneTitle}>
        <div className="tab-body">{body()}</div>
      </section>
    );
  }

  return (
    <section className="analysis-pane" aria-labelledby="analysis-pane-title">
      <header className="analysis-pane__header">
        <span className="analysis-pane__icon"><FlaskConical size={17} aria-hidden="true" /></span>
        <h2 id="analysis-pane-title">{paneTitle}</h2>
      </header>

      {result && !loading && (
        <div className="analysis-molecule">
          <div className="analysis-molecule__heading">
            <div className="analysis-molecule__identity">
              {title && <strong className="analysis-molecule__name">{title}</strong>}
              <span className="analysis-molecule__formula" title="Молекулярная формула">{result.formula}</span>
            </div>
            <button
              className="analysis-molecule__copy"
              type="button"
              aria-label="Копировать канонический SMILES"
              onClick={() => copySmiles(result.canonical_smiles)}
            >
              {copyNotice === "SMILES скопирован" ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
              SMILES
            </button>
          </div>
          {connectivityName && <span className="analysis-molecule__match">Возможное совпадение по связности: {connectivityName}</span>}
          {tab !== "props" && <code>{result.canonical_smiles}</code>}
          <span className="analysis-copy-status" role="status">{copyNotice}</span>
        </div>
      )}

      <div className="tab-body">{body()}</div>
    </section>
  );
}
