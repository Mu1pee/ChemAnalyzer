import { useEffect, useState } from "react";
import { fetchSpecializedActivity } from "../api/chemistry";
import type {
  SpecializedActivityResponse,
  SpecializedDomainResult,
  SpecializedModelPrediction
} from "../types/molecule";

interface Props {
  smiles: string;
}

type State = {
  data: SpecializedActivityResponse | null;
  loading: boolean;
  error: string;
};

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function modelTone(status: string): string {
  if (status === "ready") return "special-status-ready";
  if (status === "out_of_domain") return "special-status-warning";
  return "special-status-muted";
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="special-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PredictionCard({ prediction }: { prediction: SpecializedModelPrediction }) {
  const auc = prediction.metrics?.roc_auc;
  const bacc = prediction.metrics?.balanced_accuracy;
  const mcc = prediction.metrics?.mcc;
  const isReady = prediction.status === "ready" && prediction.probability !== null;

  return (
    <article className="special-prediction-card">
      <div className="special-prediction-head">
        <div>
          <span className="eyebrow">ENDPOINT</span>
          <h4>{prediction.endpoint}</h4>
        </div>
        <span className={`special-status ${modelTone(prediction.status)}`}>
          {isReady ? "В области применимости" : "Вне области применимости"}
        </span>
      </div>

      <p className="special-context">{prediction.context}</p>

      {isReady ? (
        <div className="special-probability-row">
          <div>
            <span className="special-caption">Некалиброванная оценка класса «активный»</span>
            <strong className="special-probability">{pct(prediction.probability!)}</strong>
          </div>
          <span className={`special-status ${prediction.predicted_label === 1 ? "special-status-ready" : "special-status-warning"}`}>
            {prediction.predicted_label === 1 ? "Класс 1 · активный" : "Класс 0 · неактивный"}
          </span>
        </div>
      ) : (
        <div className="special-note special-note-warning">
          {prediction.message ?? "Молекула недостаточно похожа на обучающую выборку. Численный прогноз скрыт."}
        </div>
      )}

      <div className="special-metrics-grid">
        <Metric label="Сходство Tanimoto" value={prediction.similarity.toFixed(2)} />
        <Metric label="Обучающая выборка" value={prediction.n_train} />
        <Metric label="Активные / неактивные" value={`${prediction.n_active} / ${prediction.n_inactive}`} />
        <Metric label="Версия модели" value={prediction.model_version} />
      </div>

      <div className="special-model-quality">
        <span>Отдельный тест по каркасам, без выбора модели по тесту:</span>
        <span>ROC-AUC {typeof auc === "number" ? auc.toFixed(2) : "—"}</span>
        <span>Balanced accuracy {typeof bacc === "number" ? bacc.toFixed(2) : "—"}</span>
        <span>MCC {typeof mcc === "number" ? mcc.toFixed(2) : "—"}</span>
      </div>
      <p className="special-source">Тест: {prediction.n_test} соединений · класс 1: {prediction.test_positive} · класс 0: {prediction.test_negative}. Внешней валидации нет.</p>
      <p className="special-source">Источник данных: {prediction.dataset_source}</p>
    </article>
  );
}

function DomainPanel({ domain }: { domain: SpecializedDomainResult }) {
  return (
    <section className="special-domain-card">
      <div className="special-domain-head">
        <div>
          <span className="eyebrow">{domain.domain === "antidote" ? "TOXICOLOGY RESEARCH" : "PLANT SCIENCE RESEARCH"}</span>
          <h3>{domain.title}</h3>
        </div>
        <span className={`special-status ${modelTone(domain.status)}`}>
          {domain.status === "ready"
            ? `Моделей: ${domain.models_available}`
            : domain.status === "error"
              ? "Ошибка загрузки"
              : "Модель не обучена"}
        </span>
      </div>

      {domain.status !== "ready" || domain.predictions.length === 0 ? (
        <div className={`special-note ${domain.status === "error" ? "special-note-error" : "special-note-warning"}`}>
          <strong>{domain.status === "error" ? "Не удалось загрузить модели" : "Пока нет валидированного прогноза"}</strong>
          <p>{domain.message}</p>
          {domain.domain === "antidote" ? (
            <p>Для обучения необходимы прослеживаемые экспериментальные данные с конкретным токсикантом, протоколом и критерием антидотной активности.</p>
          ) : (
            <p>Для обучения необходимы данные с указанием культуры/вида растения, протокола опыта, дозы и критерия рострегулирующего эффекта.</p>
          )}
        </div>
      ) : (
        <div className="special-predictions-list">
          {domain.predictions.map((prediction, index) => (
            <PredictionCard key={`${prediction.endpoint}-${prediction.context}-${index}`} prediction={prediction} />
          ))}
        </div>
      )}
    </section>
  );
}

export default function AntidotePredictionTab({ smiles }: Props) {
  const [state, setState] = useState<State>({ data: null, loading: true, error: "" });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: "" });
    fetchSpecializedActivity(smiles)
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: "" });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            data: null,
            loading: false,
            error: error instanceof Error ? error.message : "Не удалось загрузить Антидот-Прогноз."
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [smiles]);

  return (
    <div className="specialized-activity">
      <header className="specialized-title">
        <span className="eyebrow">SPECIALIZED ACTIVITY MODULE</span>
        <h2>ПК «Антидот-Прогноз»</h2>
        <p>Разработка системы прогнозирования антидотной и рострегулирующей активности химических соединений</p>
        <code>{smiles}</code>
      </header>

      <div className="special-note special-note-warning">
        <strong>Научное ограничение</strong>
        <p>
          Результаты доступны только при наличии моделей, обученных на проверенных данных для конкретного endpoint. Оценка класса модели не является откалиброванной вероятностью. У приложения нет универсальной модели для всех токсикантов и видов растений. Прогноз не заменяет лабораторный эксперимент и не предназначен для выбора лечения отравлений или применения веществ в окружающей среде.
        </p>
      </div>

      {state.loading && (
        <div className="tab-state">
          <div className="spinner" />
          <p>Проверяем наличие специализированных моделей…</p>
        </div>
      )}
      {state.error && <div className="tab-note tab-note-error">{state.error}</div>}
      {state.data && (
        <>
          <div className="special-domain-grid">
            <DomainPanel domain={state.data.antidote} />
            <DomainPanel domain={state.data.growth_regulating} />
          </div>
          <div className="special-note">
            <strong>Как активировать прогнозирование</strong>
            <p>
              Для обучения нужны экспериментальный CSV и соответствующий протокол с условиями опыта, определением классов и правами на данные. Инструкция и пустые шаблоны находятся в <code>backend/training/specialized_data/README.md</code>. В приложении доступны только модели, прошедшие проверку на отдельной тестовой выборке. Старые модели требуют повторной проверки по текущему протоколу.
            </p>
          </div>
          <p className="special-disclaimer">{state.data.disclaimer}</p>
        </>
      )}
    </div>
  );
}
