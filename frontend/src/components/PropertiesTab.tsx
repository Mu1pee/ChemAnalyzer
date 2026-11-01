import type { MoleculeResponse } from "../types/molecule";
import {
  DRUGLIKE_DISCLAIMER,
  VERDICT_LABEL,
  evaluateCriteria,
  summarizeLipinski
} from "../lib/druglike";
import MetricCard from "./MetricCard";

export default function PropertiesTab({ result }: { result: MoleculeResponse }) {
  const lipinski = summarizeLipinski(evaluateCriteria(result));

  return (
    <div>
      <div className="section-label">Физико-химические свойства</div>
      <div className="metrics-grid">
        <MetricCard label="Формула" value={result.formula} />
        <MetricCard label="Мол. масса" value={result.molecular_weight} unit=" г/моль" />
        <MetricCard label="LogP" value={result.logp} />
        <MetricCard label="TPSA" value={result.tpsa} unit=" Å²" />
        <MetricCard label="HBD" value={result.hbd} />
        <MetricCard label="HBA" value={result.hba} />
        <MetricCard label="Вращаемые связи" value={result.rotatable_bonds} />
        <MetricCard label="Кольца" value={result.rings} />
        <MetricCard label="Тяжёлые атомы" value={result.heavy_atoms} />
        <MetricCard label="Ароматические атомы" value={result.aromatic_atoms} />
        <MetricCard label="Атомов (без H)" value={result.atom_count} />
        <MetricCard label="Связей" value={result.bond_count} />
        <div className={`metric-card verdict-card verdict-${lipinski.verdict}`}>
          <span>Липински</span>
          <strong>{VERDICT_LABEL[lipinski.verdict]}</strong>
        </div>
      </div>

      {result.fragments > 1 && (
        <div className="tab-note tab-note-warn">
          Структура состоит из {result.fragments} фрагментов (например, соль или
          смесь). Свойства на этой вкладке посчитаны для всей структуры, а ADME,
          идентификация, Drug-likeness и прогнозы — для наибольшего фрагмента
          в нейтральной форме.
        </div>
      )}

      <div className="tab-note">
        <strong>Правило пяти Липински:</strong> {lipinski.text}{" "}
        {DRUGLIKE_DISCLAIMER}
      </div>

      <div className="section-label">SMILES</div>
      <div className="smiles-block">
        <span>Введённый</span>
        <code>{result.input_smiles}</code>
      </div>
      <div className="smiles-block">
        <span>Канонический</span>
        <code>{result.canonical_smiles}</code>
      </div>
    </div>
  );
}
