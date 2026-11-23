import { ShieldCheck, TriangleAlert } from "lucide-react";
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
  const structure = [
    ["Вращаемые связи", result.rotatable_bonds],
    ["Кольца", result.rings],
    ["Тяжёлые атомы", result.heavy_atoms],
    ["Ароматические атомы", result.aromatic_atoms],
    ["Атомы без H", result.atom_count],
    ["Связи", result.bond_count]
  ] as const;
  const VerdictIcon = lipinski.verdict === "pass" ? ShieldCheck : TriangleAlert;

  return (
    <div className="properties-workspace">
      {result.fragments > 1 && (
        <p className="tab-note tab-note-warn">
          Структура состоит из {result.fragments} фрагментов (например, соль или
          смесь). Свойства на этой вкладке посчитаны для всей структуры, а ADME,
          идентификация, Drug-likeness и прогнозы — для наибольшего фрагмента
          в нейтральной форме.
        </p>
      )}

      <section aria-labelledby="properties-descriptors">
        <div className="properties-heading">
          <h3 id="properties-descriptors">Дескрипторы</h3>
          <span>RDKit</span>
        </div>
        <div className="properties-metrics">
          <MetricCard label="Мол. масса" value={result.molecular_weight} unit=" г/моль" />
          <MetricCard label="LogP" value={result.logp} />
          <MetricCard label="TPSA" value={result.tpsa} unit=" Å²" />
          <MetricCard label="Доноры (HBD)" value={result.hbd} />
          <MetricCard label="Акцепторы (HBA)" value={result.hba} />
        </div>
      </section>

      <section aria-labelledby="properties-lipinski" className={`properties-verdict properties-verdict--${lipinski.verdict}`}>
        <div className="properties-verdict__heading">
          <VerdictIcon size={17} aria-hidden="true" />
          <h3 id="properties-lipinski">Правило пяти Липински</h3>
          <strong>{VERDICT_LABEL[lipinski.verdict]}</strong>
        </div>
        <p>{lipinski.text}</p>
        <p>{DRUGLIKE_DISCLAIMER}</p>
      </section>

      <section aria-labelledby="properties-structure">
        <div className="properties-heading"><h3 id="properties-structure">Строение</h3></div>
        <dl className="properties-structure">
          {structure.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="properties-smiles">
        <div className="properties-heading"><h3 id="properties-smiles">SMILES</h3></div>
        <dl className="properties-smiles">
          <div>
            <dt>Введённый</dt>
            <dd><code>{result.input_smiles}</code></dd>
          </div>
          <div>
            <dt>Канонический</dt>
            <dd><code>{result.canonical_smiles}</code></dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
