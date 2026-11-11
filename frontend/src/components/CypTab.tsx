import { useEffect, useState } from "react";
import { fetchCyp } from "../api/chemistry";
import type { AsyncState, CypResponse } from "../types/molecule";
import ScoreBar from "./ScoreBar";

export default function CypTab({ smiles }: { smiles: string }) {
  const [state, setState] = useState<AsyncState<CypResponse>>({ data: null, loading: true, error: "" });
  useEffect(() => {
    let current = true;
    setState({ data: null, loading: true, error: "" });
    fetchCyp(smiles).then(data => current && setState({ data, loading: false, error: "" }))
      .catch(error => current && setState({ data: null, loading: false, error: String(error.message) }));
    return () => { current = false; };
  }, [smiles]);
  if (state.loading) return <div className="tab-state"><div className="spinner" /><p>Проверяем отдельные модели CYP…</p></div>;
  if (state.error) return <div className="tab-note tab-note-error">{state.error}</div>;
  if (!state.data) return null;
  return <div>
    <div className="section-label">CYP: ингибирование отдельных изоформ</div>
    <div className="activity-list">{state.data.predictions.map(p => <article className="activity-row" key={p.isoform}>
      <div className="activity-head"><strong>{p.isoform}</strong><span className={`badge badge-${p.status === "ready" ? "high" : "low"}`}>
        {p.status === "ready" ? "В области применимости" : p.status === "out_of_domain" ? "Вне области применимости" : p.status === "not_trained" ? "Не обучена" : "Прогноз недоступен"}
      </span></div>
      {p.probability !== null && <div className="activity-bar-line"><ScoreBar value={p.probability} tone="medium" />
        <span className="activity-score">{(100 * p.probability).toFixed(1)}%</span></div>}
      {p.probability !== null && <div className="activity-support">Оценка вероятности ингибирования по разметке TDC/Veith</div>}
      {p.model_id && <>
        <div className="activity-support">Сбалансированная точность теста: {(100 * p.metrics.balanced_accuracy).toFixed(2)}%
          {" · ROC-AUC: "}{p.metrics.roc_auc.toFixed(3)}{" · PR-AUC: "}{p.metrics.pr_auc.toFixed(3)}</div>
        <div className="activity-support">Обучение: {p.n_train} молекул · Отложенный тест: {p.n_test}
          {" · Сходство: "}{p.max_similarity?.toFixed(2)}{" · "}{p.model_status === "approved" ? "Утверждена в реестре" : "Экспериментальная модель"}</div>
        <div className="activity-support">Чувствительность к ингибиторам: {(100 * p.metrics.recall).toFixed(1)}%
          {" · Точность положительных прогнозов: "}{(100 * p.metrics.precision).toFixed(1)}%</div>
      </>}
      {p.message && <p className="tab-note">{p.message}</p>}
    </article>)}</div>
    <p className="tab-note">{state.data.disclaimer} Вероятности не прошли отдельную калибровку.</p>
  </div>;
}
