import { useState, type RefObject } from "react";
import { ArrowDownToLine, Trash2 } from "lucide-react";

export const DEFAULT_STRUCTURE = "Cn1cnc2c1c(=O)n(C)c(=O)n2C";

export const EXAMPLES: Array<{ name: string; smiles: string }> = [
  { name: "Этанол", smiles: "CCO" },
  { name: "Бензол", smiles: "c1ccccc1" },
  { name: "Аспирин", smiles: "CC(=O)Oc1ccccc1C(=O)O" },
  { name: "Кофеин", smiles: DEFAULT_STRUCTURE }
];

interface Props {
  ready: boolean;
  inputRef: RefObject<HTMLInputElement | null>;
  onClear: () => void;
  onImport: (smiles: string) => Promise<boolean>;
  onExample: (smiles: string) => void;
}

export default function EditorToolbar({
  ready,
  inputRef,
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
    <div className="editor-controls">
      <form className="editor-import" onSubmit={(event) => { event.preventDefault(); void submitImport(); }}>
        <label htmlFor="structure-smiles">SMILES</label>
        <input
          ref={inputRef}
          id="structure-smiles"
          value={value}
          maxLength={10000}
          spellCheck={false}
          placeholder="Введите строку, например CCO"
          disabled={!ready}
          onChange={(event) => setValue(event.target.value)}
        />
        <button type="submit" className="ghost-button with-icon" disabled={!ready || !value.trim()}>
          <ArrowDownToLine size={15} aria-hidden="true" /> Импорт
        </button>
      </form>
      <div className="editor-examples" aria-label="Примеры структур">
        <span>Примеры</span>
        {EXAMPLES.map((example) => (
          <button key={example.name} type="button" disabled={!ready} onClick={() => onExample(example.smiles)}>
            {example.name}
          </button>
        ))}
        <button type="button" className="ghost-button with-icon editor-clear" disabled={!ready} onClick={onClear}>
          <Trash2 size={14} aria-hidden="true" /> Очистить
        </button>
      </div>
    </div>
  );
}
