import type { ActivityResponse, AsyncState } from "../types/molecule";
import ScoreBar from "./ScoreBar";

interface Props {
  state: AsyncState<ActivityResponse>;
  onTrainQsar?: () => void;
}

function tone(confidence: string): "high" | "medium" | "low" {
  if (confidence === "высокая") return "high";
  if (confidence === "средняя") return "medium";
  return "low";
}

function domainTone(domain: string): "high" | "medium" | "low" {
  if (domain === "в области применимости") return "high";
  if (domain === "на границе области") return "medium";
  return "low";
}

export default function ActivityTab({ state, onTrainQsar }: Props) {
  if (state.loading) {
    return (
      <div className="tab-state">
        <div className="spinner" />
        <p>Сравниваем структуру с библиотекой препаратов…</p>
      </div>
    );
  }

  if (state.error) {
    return <div className="tab-note tab-note-error">{state.error}</div>;
  }

  const data = state.data;
  if (!data) return null;

  const qsar = data.qsar;

  return (
    <div>
      <div className="section-label">QSAR: обученные модели по мишеням</div>
      {qsar.status === "ready" ? (
        <>
          <div className="activity-list">
            {qsar.predictions.map((p) => (
              <div className="activity-row" key={p.model_id ?? p.target_id}>
                <div className="activity-head">
                  <strong>{p.target_name}</strong>
                  <span className={`badge badge-${domainTone(p.domain)}`}>
                    {p.domain}
                  </span>
                </div>
                {p.probability !== null ? <div className="activity-bar-line">
                  <ScoreBar
                    value={p.probability}
                    tone={domainTone(p.domain)}
                  />
                  <span className="activity-score">
                    {(p.probability * 100).toFixed(0)}%
                  </span>
                </div> : <div className="tab-note">Вне области применимости: численный прогноз скрыт.</div>}
                <div className="activity-support">
                  вероятность pChEMBL ≥ {p.active_pchembl} · сходство с
                  обучающей выборкой {p.max_similarity.toFixed(2)} · порог IC50 ≤
                  {p.active_threshold_nM} нМ · обучено на {p.n_train} · тест
                  {" "}{p.n_test} (активных {p.test_positive}, неактивных {p.test_negative})
                </div>
                <div className="activity-support">
                  Тест по каркасам: BA {(p.metrics.balanced_accuracy * 100).toFixed(1)}% ·
                  ROC-AUC {p.metrics.roc_auc.toFixed(2)} · PR-AUC {p.metrics.pr_auc.toFixed(2)}
                </div>
                <div className="activity-support">{p.validation_method}</div>
                {p.model_version && (
                  <div className="activity-support">
                    модель: {p.model_version}
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="tab-note">
            Используется моделей: {qsar.models_loaded}. {qsar.disclaimer}
            {qsar.message && <p>{qsar.message}</p>}
          </div>
        </>
      ) : (
        <div
          className={`tab-note ${qsar.status === "error" ? "tab-note-error" : "tab-note-warn"}`}
        >
          <strong>
            {qsar.status === "error" ? "QSAR-модели не удалось загрузить."
              : qsar.status === "quality_failed" ? "QSAR-модель скрыта: проверка качества не пройдена."
              : "QSAR-модель не обучена."}
          </strong>{" "}
          {(qsar.message ?? "").replace(/^QSAR-модель не обучена\.\s*/, "")}
          {qsar.status === "not_trained" && onTrainQsar && (
            <p><button type="button" className="ghost-button" onClick={onTrainQsar}>
              Обучить QSAR-модель в AI Research Lab
            </button></p>
          )}
        </div>
      )}

      <div className="section-label">Структурная similarity-оценка (не QSAR)</div>

      {data.activities.length === 0 ? (
        <div className="tab-note">{data.message}</div>
      ) : (
        <div className="activity-list">
          {data.activities.map((activity) => (
            <div className="activity-row" key={activity.name}>
              <div className="activity-head">
                <strong>{activity.name}</strong>
                <span className={`badge badge-${tone(activity.confidence)}`}>
                  {activity.confidence}
                </span>
              </div>
              <div className="activity-bar-line">
                <ScoreBar
                  value={activity.score}
                  tone={tone(activity.confidence)}
                />
                <span className="activity-score">
                  {activity.score.toFixed(2)}
                </span>
              </div>
              <div className="activity-support">
                по аналогии:{" "}
                {activity.support
                  .map((s) => `${s.drug} (${s.similarity.toFixed(2)})`)
                  .join(", ")}
              </div>
            </div>
          ))}
        </div>
      )}

      {data.nearest.length > 0 && (
        <>
          <div className="section-label">Ближайшие известные препараты</div>
          <div className="neighbor-list">
            {data.nearest.map((drug) => (
              <div className="neighbor-row" key={drug.name}>
                <div>
                  <strong>{drug.name}</strong>
                  <span>{drug.activities.slice(0, 3).join(" · ")}</span>
                </div>
                <code>{drug.similarity.toFixed(2)}</code>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="tab-note">
        <strong>Как читать:</strong> число — максимальное сходство Tanimoto
        (0–1) с препаратом, у которого эта активность известна. {data.disclaimer}{" "}
        Библиотека: {data.reference_size} препаратов.
      </div>
    </div>
  );
}
