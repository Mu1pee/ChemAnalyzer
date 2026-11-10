import type {
  AsyncState,
  ChemblMechanism,
  ChemblResponse
} from "../types/molecule";

interface Props {
  state: AsyncState<ChemblResponse>;
}

function phaseLabel(phase: number | null): string {
  if (phase === null || phase === undefined) return "—";
  if (phase >= 4) return "Одобренный препарат";
  if (phase >= 1) return `Клинические испытания, фаза ${Math.floor(phase)}`;
  if (phase > 0) return "Ранняя клиническая фаза";
  return "Доклиническое / не в клинике";
}

// pChEMBL = −log10(моль/л)  →  нМ = 10^(9 − pChEMBL)
function toNanomolar(pchembl: number): string {
  const nm = Math.pow(10, 9 - pchembl);
  if (nm >= 1000) return `${(nm / 1000).toPrecision(3)} мкМ`;
  if (nm >= 1) return `${nm.toPrecision(3)} нМ`;
  return `${nm.toPrecision(2)} нМ`;
}

function mechanismText(m: ChemblMechanism): string {
  const target = m.target_name ? ` → ${m.target_name}` : "";
  return `${m.action ?? "Механизм не указан"}${target}`;
}

export default function ChemblTab({ state }: Props) {
  if (state.loading) {
    return (
      <div className="tab-state">
        <div className="spinner" />
        <p>Запрашиваем экспериментальные данные ChEMBL…</p>
      </div>
    );
  }

  if (state.error) {
    return <div className="tab-note tab-note-error">{state.error}</div>;
  }

  const data = state.data;
  if (!data) return null;

  return (
    <div>
      {data.retrieved_at && <div className="tab-note">
        {data.stale ? "Сохранённая копия при сбое сервиса" : data.cached ? "Локальный кэш ChEMBL" : "Ответ ChEMBL"}
        {" · Получено: "}{new Date(data.retrieved_at).toLocaleString()}
        {data.partial && " · Неполные данные"}
      </div>}
      {!data.found &&
        data.available &&
        data.similar.length === 0 && (
          <div className="tab-note">
            <strong>Экспериментальные данные не найдены.</strong> Соединение
            отсутствует в ChEMBL.
          </div>
        )}
      {data.message && (data.found || data.similar.length > 0 || !data.available) && (
        <div className="tab-note">{data.message}</div>
      )}

      {data.found && (
        <>
          <div className="section-label">Соединение в ChEMBL</div>
          <div className="compound-card">
            <div className="compound-status">Найдено в ChEMBL</div>
            <h3>{data.name ?? data.chembl_id}</h3>
            <div className="compound-meta">
              <span>{data.chembl_id}</span>
              <span>{phaseLabel(data.max_phase)}</span>
            </div>
            {data.source_url && (
              <a
                className="pubchem-link"
                href={data.source_url}
                target="_blank"
                rel="noreferrer"
              >
                Открыть запись ChEMBL ↗
              </a>
            )}
          </div>
        </>
      )}

      {data.mechanisms.length > 0 && (
        <>
          <div className="section-label">Механизм действия</div>
          <ul className="plain-list">
            {data.mechanisms.map((m, i) => (
              <li key={`${m.target_id}-${i}`}>{mechanismText(m)}</li>
            ))}
          </ul>
        </>
      )}

      {data.indications.length > 0 && (
        <>
          <div className="section-label">Показания</div>
          <div className="chip-row">
            {data.indications.map((i) => (
              <span className="chip" key={i.name}>
                {i.name}
              </span>
            ))}
          </div>
        </>
      )}

      {data.targets.length > 0 && (
        <>
          <div className="section-label">
            Измеренная активность по мишеням
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Мишень</th>
                  <th>pChEMBL</th>
                  <th>≈ Конц.</th>
                  <th>N</th>
                </tr>
              </thead>
              <tbody>
                {data.targets.map((t) => (
                  <tr key={t.target_id}>
                    <td>
                      {t.target_name ?? t.target_id}
                      <small>
                        {[t.organism, t.activity_types.join("/")]
                          .filter(Boolean)
                          .join(" · ")}
                      </small>
                    </td>
                    <td>{t.best_pchembl.toFixed(2)}</td>
                    <td>{toNanomolar(t.best_pchembl)}</td>
                    <td>{t.measurements}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {data.similar.length > 0 && (
        <>
          <div className="section-label">
            Похожие соединения (сходство ≥ 70%) и их мишени
          </div>
          <div className="neighbor-list">
            {data.similar.map((s) => (
              <div className="neighbor-row" key={s.chembl_id}>
                <div>
                  <strong>{s.name ?? s.chembl_id}</strong>
                  <span>
                    {s.mechanisms.length > 0
                      ? s.mechanisms.map(mechanismText).join(" · ")
                      : "Механизм в ChEMBL не указан"}
                  </span>
                </div>
                <code>{s.similarity.toFixed(0)}%</code>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="tab-note">
        Источник: ChEMBL (EMBL-EBI). pChEMBL = −log10 активности в молях:
        чем больше, тем сильнее связывание. Это экспериментальные данные из
        литературы, а не предсказание.
      </div>
    </div>
  );
}
