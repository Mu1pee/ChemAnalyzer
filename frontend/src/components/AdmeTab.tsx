import type { AdmeResponse, AsyncState, DrugRule } from "../types/molecule";
import EggPlot from "./EggPlot";
import RadarChart from "./RadarChart";

interface Props {
  state: AsyncState<AdmeResponse>;
}

type Row = [label: string, value: string, tone?: "good" | "bad" | "muted"];

function fmtExp(value: number): string {
  return value >= 0.01 && value < 1000 ? value.toPrecision(3) : value.toExponential(2);
}

function ruleText(rule: DrugRule): { value: string; tone: "good" | "bad" } {
  const n = rule.violations.length;
  if (rule.passed) {
    return { value: n === 0 ? "Да, нарушений нет" : `Да (допускается одно нарушение: ${rule.violations[0]})`, tone: "good" };
  }
  return { value: `Нет: ${n} нарушени${n === 1 ? "е" : n < 5 ? "я" : "й"} — ${rule.violations.join("; ")}`, tone: "bad" };
}

function Group({ title, rows }: { title: string; rows: Row[] }) {
  return (
    <div className="kv-group">
      <div className="kv-title">{title}</div>
      <table className="kv-table">
        <tbody>
          {rows.map(([label, value, tone]) => (
            <tr key={label}>
              <th>{label}</th>
              <td className={tone ? `kv-${tone}` : undefined}>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AdmeTab({ state }: Props) {
  if (state.loading) {
    return (
      <div className="tab-state">
        <div className="spinner" />
        <p>Считаем ADME-профиль…</p>
      </div>
    );
  }
  if (state.error) {
    return <div className="tab-note tab-note-error">{state.error}</div>;
  }
  const d = state.data;
  if (!d) return null;

  const egg = d.boiled_egg;
  const inZone = d.radar.filter((a) => a.in_range).length;
  const sa = d.medchem.synthetic_accessibility;
  const rules = Object.fromEntries(d.druglikeness.map((r) => [r.name, ruleText(r)]));
  const lead = ruleText(d.medchem.lead_likeness);

  const physchem: Row[] = [
    ["Формула", d.physchem.formula],
    ["Молекулярная масса", `${d.physchem.molecular_weight} г/моль`],
    ["Тяжёлые атомы", String(d.physchem.heavy_atoms)],
    ["Ароматические тяжёлые атомы", String(d.physchem.aromatic_heavy_atoms)],
    ["Доля sp3-углеродов (Fsp3)", String(d.physchem.fsp3)],
    ["Вращаемые связи", String(d.physchem.rotatable_bonds)],
    ["Акцепторы H-связи (HBA)", String(d.physchem.hba)],
    ["Доноры H-связи (HBD)", String(d.physchem.hbd)],
    ["Молярная рефракция", String(d.physchem.molar_refractivity)],
    ["TPSA (S и P учтены)", `${d.physchem.tpsa} Å²`]
  ];

  return (
    <div>
      <div className="section-label">BOILED-Egg: ЖКТ и гематоэнцефалический барьер</div>
      <div className="egg-wrap">
        <EggPlot egg={egg} />
        <div className="egg-legend">
          <span><i className="lg-yolk" />Желток — проникает через ГЭБ</span>
          <span><i className="lg-white" />Белок — высокое всасывание в ЖКТ</span>
          <span><i className="lg-dot" />Ваша молекула</span>
        </div>
      </div>

      <div className="verdict-pair">
        <div className={`pill ${egg.gi_absorption ? "pill-good" : "pill-bad"}`}>
          <span>Всасывание в ЖКТ</span>
          <strong>{egg.gi_absorption ? "высокое" : "низкое"}</strong>
        </div>
        <div className={`pill ${egg.bbb_permeant ? "pill-good" : "pill-bad"}`}>
          <span>Проникает через ГЭБ</span>
          <strong>{egg.bbb_permeant ? "да" : "нет"}</strong>
        </div>
        <div className="pill pill-muted">
          <span>Субстрат P-gp</span>
          <strong>не рассчитывается</strong>
        </div>
      </div>
      <p className="egg-caption">
        TPSA {egg.tpsa} Å² · WLOGP {egg.wlogp}. Области не исключают друг друга.
      </p>

      <div className="section-label">Радар биодоступности</div>
      <div className="radar-wrap">
        <RadarChart axes={d.radar} />
        <p className="egg-caption">
          Розовая зона — оптимум для приёма внутрь. В зоне:{" "}
          <strong>{inZone} из {d.radar.length}</strong> параметров
          {inZone < d.radar.length &&
            ` (вне зоны: ${d.radar.filter((a) => !a.in_range).map((a) => a.key).join(", ")})`}
          .
        </p>
      </div>

      <div className="section-label">Ключевые характеристики</div>
      <Group title="Физико-химические свойства" rows={physchem} />
      <Group title="Липофильность" rows={[["Log P (WLOGP, метод Крипена)", String(d.physchem.wlogp)]]} />
      <Group
        title="Растворимость в воде (ESOL)"
        rows={[
          ["Log S", String(d.solubility.esol_logs)],
          ["Растворимость", `${fmtExp(d.solubility.esol_mg_ml)} мг/мл; ${fmtExp(d.solubility.esol_mol_l)} моль/л`],
          ["Класс", d.solubility.esol_class]
        ]}
      />
      <Group
        title="Фармакокинетика"
        rows={[
          ["Всасывание в ЖКТ", d.pharmacokinetics.gi_absorption, d.pharmacokinetics.gi_absorption === "высокое" ? "good" : "bad"],
          ["Проницаемость для ГЭБ", d.pharmacokinetics.bbb_permeant, d.pharmacokinetics.bbb_permeant === "да" ? "good" : "bad"],
          ["Субстрат P-gp", "не рассчитывается", "muted"],
          ["Ингибиторы CYP1A2/2C19/2C9/2D6/3A4", "не рассчитываются", "muted"],
          ["Log Kp (кожа)", `${d.pharmacokinetics.log_kp} см/с`]
        ]}
      />
      <Group
        title="Сходство с лекарствами"
        rows={d.druglikeness.map((r): Row => [r.name, rules[r.name].value, rules[r.name].tone])}
      />
      <Group
        title="Медицинская химия"
        rows={[
          ["PAINS", d.medchem.pains.length ? d.medchem.pains.join("; ") : "0 предупреждений", d.medchem.pains.length ? "bad" : "good"],
          ["Brenk", d.medchem.brenk.length ? d.medchem.brenk.join("; ") : "0 предупреждений", d.medchem.brenk.length ? "bad" : "good"],
          ["Lead-likeness", lead.value, lead.tone],
          ["Синтетическая доступность", sa === null ? "не рассчитана" : `${sa} (1 — легко, 10 — очень сложно)`, sa === null ? "muted" : undefined]
        ]}
      />

      <div className="tab-note">
        {d.notes.map((n) => (
          <p key={n}>{n}</p>
        ))}
        <p>
          Не рассчитывается: {d.not_computed.join("; ")}. Источник модели BOILED-Egg: {egg.source}
        </p>
      </div>
    </div>
  );
}
