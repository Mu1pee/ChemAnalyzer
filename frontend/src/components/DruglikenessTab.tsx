import type { ActivityResponse, AsyncState, MoleculeResponse } from "../types/molecule";
import {
  DRUGLIKE_DISCLAIMER,
  VERDICT_LABEL,
  evaluateCriteria,
  qedVerdict,
  summarizeLipinski
} from "../lib/druglike";
import MetricCard from "./MetricCard";
import ScoreBar from "./ScoreBar";

interface Props {
  result: MoleculeResponse;
  state: AsyncState<ActivityResponse>;
}

const TONE = { pass: "high", warn: "medium", fail: "low" } as const;

export default function DruglikenessTab({ result, state }: Props) {
  const criteria = evaluateCriteria(result);
  const lipinski = summarizeLipinski(criteria);
  const d = state.data?.druglikeness;

  return (
    <div>
      <div className="section-label">Правило пяти Липински</div>
      <div className={`verdict-banner verdict-${lipinski.verdict}`}>
        <strong>{VERDICT_LABEL[lipinski.verdict]}</strong>
        <span>
          Нарушений: {lipinski.violations}. {lipinski.text}
        </span>
      </div>

      <div className="section-label">Показатели</div>
      <div className="criteria-list">
        {criteria.map((c) => (
          <div className="criteria-row" key={c.key}>
            <div className="criteria-main">
              <strong>{c.label}</strong>
              <span>
                {c.value} · предел ≤ {c.limit} ({c.rule})
              </span>
            </div>
            <span className={`badge badge-${TONE[c.verdict]}`}>
              {VERDICT_LABEL[c.verdict]}
            </span>
            <p>{c.explanation}</p>
          </div>
        ))}
      </div>

      {state.loading && (
        <div className="tab-state">
          <div className="spinner" />
          <p>Считаем QED, ADMET и структурные алерты…</p>
        </div>
      )}
      {state.error && <div className="tab-note tab-note-error">{state.error}</div>}

      {d && (
        <>
          <div className="section-label">QED (общая «лекарственность»)</div>
          <div className="qed-card">
            <div className="qed-value">
              {d.qed.toFixed(2)}
              <span className={`badge badge-${TONE[qedVerdict(d.qed)]}`}>
                {VERDICT_LABEL[qedVerdict(d.qed)]}
              </span>
            </div>
            <ScoreBar value={d.qed} tone={TONE[qedVerdict(d.qed)]} />
          </div>

          <div className="section-label">Другие правила</div>
          <div className="rule-list">
            {d.rules
              .filter((r) => r.name !== "Липински")
              .map((rule) => (
                <div className="rule-row" key={rule.name}>
                  <div className="rule-head">
                    <strong>{rule.name}</strong>
                    <span
                      className={`badge ${rule.passed ? "badge-high" : "badge-low"}`}
                    >
                      {rule.passed ? "PASS" : "FAIL"}
                    </span>
                  </div>
                  {rule.violations.length > 0 && (
                    <ul>
                      {rule.violations.map((v) => (
                        <li key={v}>{v}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
          </div>

          <div className="section-label">ADMET (эвристики)</div>
          <div className="metrics-grid">
            <MetricCard label="Всасывание в ЖКТ" value={d.gi_absorption} />
            <MetricCard label="Проникает через ГЭБ" value={d.bbb_permeant} />
          </div>

          <div className="section-label">Структурные алерты</div>
          <AlertGroup title="PAINS (ложные срабатывания)" items={d.pains_alerts} />
          <AlertGroup title="Brenk (нежелательные группы)" items={d.brenk_alerts} />
        </>
      )}

      <div className="tab-note">{DRUGLIKE_DISCLAIMER}</div>
    </div>
  );
}

function AlertGroup({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="alert-group">
      <span>{title}</span>
      {items.length === 0 ? (
        <em>не обнаружено</em>
      ) : (
        <div className="chip-row">
          {items.map((item) => (
            <span className="chip chip-warn" key={item}>
              {item}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
