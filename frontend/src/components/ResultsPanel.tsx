import { useState } from "react";
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
import DruglikenessTab from "./DruglikenessTab";
import HistoryTab from "./HistoryTab";
import { IconCopy } from "./Icons";
import IdentificationTab from "./IdentificationTab";
import PropertiesTab from "./PropertiesTab";
import StructureTab from "./StructureTab";
import AntidotePredictionTab from "./AntidotePredictionTab";
import ResearchLabTab from "./ResearchLabTab";

export type Tab =
  | "props"
  | "adme"
  | "ident"
  | "drug"
  | "activity"
  | "antidote"
  | "chembl"
  | "3d"
  | "history"
  | "research"
  | "assistant";

export const TABS: { id: Tab; label: string }[] = [
  { id: "props", label: "Свойства" },
  { id: "adme", label: "ADME" },
  { id: "ident", label: "Идентификация" },
  { id: "drug", label: "Drug-likeness" },
  { id: "activity", label: "Активность" },
  { id: "antidote", label: "Антидот-Прогноз" },
  { id: "chembl", label: "ChEMBL" },
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

const NEEDS_RESULT: Tab[] = ["props", "adme", "ident", "drug", "activity", "antidote", "chembl", "3d"];

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
  const [copied, setCopied] = useState(false);
  const [researchPreset, setResearchPreset] = useState<"default" | "qsar">("default");

  async function copySmiles(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Буфер обмена недоступен — ничего страшного.
    }
  }

  const id = identification.data;
  // Название — только при точном совпадении. Совпадение «по связности» не
  // подтверждает тождество (стереоизомер, изотопы), поэтому в заголовок не выносится.
  const title = id?.found && id.match_type === "exact" ? id.title : null;
  const connectivityName =
    id?.found && id.match_type === "connectivity" ? id.title : null;

  function body() {
    if (tab === "research") return <ResearchLabTab initialPreset={researchPreset} />;
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

    if (NEEDS_RESULT.includes(tab)) {
      if (loading) {
        return (
          <div className="loading-box">
            <div className="spinner" />
            <h3>Анализируем структуру</h3>
            <p>RDKit считает дескрипторы.</p>
          </div>
        );
      }
      if (!result) {
        return (
          <div className="empty-result">
            <div className="empty-orb">⌬</div>
            <h3>Здесь появятся результаты</h3>
            <p>
              Нарисуйте молекулу в редакторе и нажмите «Анализировать»
              (Ctrl+Enter).
            </p>
          </div>
        );
      }
    }

    if (!result) return null;
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
          setResearchPreset("qsar");
          onTab("research");
        }} />;
      case "antidote":
        return <AntidotePredictionTab smiles={result.canonical_smiles} />;
      case "chembl":
        return <ChemblTab state={chembl} />;
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

  return (
    <aside className="results-panel">
      {result && !loading && (
        <div className="result-heading">
          <div className="result-title-row">
            <h2>{title ?? result.formula}</h2>
            <button
              className="ghost-button with-icon"
              type="button"
              onClick={() => copySmiles(result.canonical_smiles)}
            >
              <IconCopy size={14} />
              {copied ? "Скопировано" : "SMILES"}
            </button>
          </div>
          <span className="result-sub">
            {title ? `${result.formula} · ` : ""}
            MW {result.molecular_weight}
            {connectivityName ? ` · по связности возможно: ${connectivityName}` : ""}
          </span>
          <code>{result.canonical_smiles}</code>
        </div>
      )}

      <div className="tabs" role="tablist">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={`tab-button${tab === item.id ? " active" : ""}`}
            onClick={() => onTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="tab-body">{body()}</div>
    </aside>
  );
}
