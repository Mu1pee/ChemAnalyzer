import { useState, type RefObject } from "react";
import { IconPlay, IconTrash, IconUpload } from "./Icons";

export const EXAMPLES: Array<{ name: string; smiles: string }> = [
  { name: "Этанол", smiles: "CCO" },
  { name: "Бензол", smiles: "c1ccccc1" },
  { name: "Аспирин", smiles: "CC(=O)Oc1ccccc1C(=O)O" },
  { name: "Кофеин", smiles: "Cn1cnc2c1c(=O)n(C)c(=O)n2C" }
];

interface Props {
  ready: boolean;
  working: boolean;
  inputRef: RefObject<HTMLInputElement | null>;
  onAnalyze: () => void;
  onClear: () => void;
  onImport: (smiles: string) => Promise<boolean>;
  onExample: (smiles: string) => void;
}

export default function EditorToolbar({
  ready,
  working,
  inputRef,
  onAnalyze,
  onClear,
  onImport,
  onExample
}: Props) {
  const [value, setValue] = useState("");

  async function submitImport() {
    const smiles = value.trim();
    if (!smiles) return;
    if (await onImport(smiles)) setValue("");
  }

  return (
    <div className="toolbar">
      <button
        type="button"
        className="primary-button with-icon"
        disabled={!ready || working}
        onClick={onAnalyze}
        title="Анализировать структуру (Ctrl+Enter)"
      >
        <IconPlay size={14} />
        {working ? "Анализ…" : "Анализировать"}
      </button>

      <button
        type="button"
        className="ghost-button with-icon"
        disabled={!ready}
        onClick={onClear}
      >
        <IconTrash size={15} />
        Очистить
      </button>

      <span className="toolbar-sep" />

      <div className="import-box">
        <input
          ref={inputRef}
          value={value}
          maxLength={10000}
          spellCheck={false}
          placeholder="Импорт SMILES, например CCO"
          disabled={!ready}
          onChange={(e: { target: { value: string } }) => setValue(e.target.value)}
          onKeyDown={(e: { key: string }) => {
            if (e.key === "Enter") submitImport();
          }}
        />
        <button
          type="button"
          className="ghost-button with-icon"
          disabled={!ready || !value.trim()}
          onClick={submitImport}
        >
          <IconUpload size={15} />
          Импорт
        </button>
      </div>

      <span className="toolbar-spacer" />

      <div className="examples">
        <span>Примеры:</span>
        {EXAMPLES.map((example) => (
          <button
            key={example.name}
            type="button"
            className="chip chip-button"
            disabled={!ready}
            onClick={() => onExample(example.smiles)}
          >
            {example.name}
          </button>
        ))}
      </div>
    </div>
  );
}
