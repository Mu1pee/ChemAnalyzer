import { useEffect, useState } from "react";
import { fetchScreening } from "../api/chemistry";
import type { AsyncState, ScreeningResponse } from "../types/molecule";
import ScoreBar from "./ScoreBar";

export default function ScreeningTab({ smiles, endpointKey }: { smiles: string; endpointKey?: "hlm" | "solubility" }) {
  const [state, setState] = useState<AsyncState<ScreeningResponse>>({ data: null, loading: true, error: "" });
  useEffect(() => {
    let current = true;
    setState({ data: null, loading: true, error: "" });
    fetchScreening(smiles).then(data => current && setState({ data, loading: false, error: "" }))
      .catch(error => current && setState({ data: null, loading: false, error: String(error.message) }));
    return () => { current = false; };
  }, [smiles]);
  if (state.loading) return <div className="tab-state"><div className="spinner" /><p>Проверяем модели отдельных скрининговых тестов…</p></div>;
  if (state.error) return <div className="tab-note tab-note-error">{state.error}</div>;
  if (!state.data) return null;
  return <div>
    <div className="section-label">{endpointKey === "hlm" ? "Метаболическая стабильность: микросомы человека" : endpointKey === "solubility" ? "Кинетическая растворимость: pH 7,4" : "Экспериментальные модели: ВИЧ и HepG2"}</div>
    <div className="activity-list">{state.data.predictions.filter(p => endpointKey ? p.key === endpointKey : ["hiv", "hepg2"].includes(p.key)).map(p => {
      const positive = p.key === "hlm" ? "стабильных" : p.key === "solubility" ? "малорастворимых" : "активных";
      const negative = p.key === "hlm" ? "нестабильных" : p.key === "solubility" ? "умеренно/хорошо растворимых" : "неактивных";
      return <article className="activity-row" key={p.key}>
      <div className="activity-head"><strong>{p.title}</strong><span className={`badge badge-${p.status === "ready" ? "high" : "low"}`}>
        {p.status === "ready" ? "В области применимости" : p.status === "out_of_domain" ? "Вне области применимости" : p.status === "not_trained" ? "Не обучена" : "Прогноз недоступен"}
      </span></div>
      <p className="tab-note">{p.context}</p>
      {p.model_id && p.metrics.recall < 0.6 && <p className="tab-note tab-note-error">
        Низкая чувствительность: модель обнаружила {(100 * p.metrics.recall).toFixed(1)}% {positive} соединений теста.
        Отрицательный прогноз не исключает {p.key === "hlm" ? "стабильность" : p.key === "solubility" ? "низкую растворимость" : "активность"}.
      </p>}
      {p.probability !== null && <>
        <div className="activity-bar-line"><ScoreBar value={p.probability} tone="medium" />
          <span className="activity-score">{(100 * p.probability).toFixed(1)}%</span></div>
        <div className="activity-support">{p.key === "hlm" ? "Некалиброванная оценка стабильности T½ > 30 минут" : p.key === "solubility" ? "Некалиброванная оценка низкой растворимости ≤10 мкг/мл" : "Некалиброванная оценка положительного исхода этого теста"}</div>
      </>}
      {p.model_id && <>
        <div className="activity-support">Сбалансированная точность теста: {(100 * p.metrics.balanced_accuracy).toFixed(2)}%
          {" · ROC-AUC: "}{p.metrics.roc_auc.toFixed(3)}{" · PR-AUC: "}{p.metrics.pr_auc.toFixed(3)}</div>
        <div className="activity-support">Чувствительность: {(100 * p.metrics.recall).toFixed(1)}%
          {" · Точность положительных прогнозов: "}{(100 * p.metrics.precision).toFixed(1)}%</div>
        <div className="activity-support">Обучение: {p.n_train} · Отложенный тест: {p.n_test}
          {" ("}{positive}{": "}{p.test_positive}{", "}{negative}{": "}{p.test_negative}{")"}</div>
        <div className="activity-support">Сходство: {p.max_similarity?.toFixed(2)} · {p.model_status === "approved" ? "Утверждена в реестре" : "Экспериментальная модель"}</div>
      </>}
      {p.message && <p className="tab-note">{p.message}</p>}
    </article>})}</div>
    <p className="tab-note">{state.data.disclaimer}</p>
  </div>;
}
