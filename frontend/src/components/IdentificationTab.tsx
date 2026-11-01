import type {
  AsyncState,
  CheckStatus,
  IdentificationResult
} from "../types/molecule";

interface Props {
  state: AsyncState<IdentificationResult>;
}

const CHECKS: Array<[string, string, string]> = [
  ["exact", "Точное совпадение структуры", "та же структура с учётом стереохимии и изотопов"],
  ["connectivity", "Совпадение по связности", "та же связность атомов; стереохимия может отличаться"],
  ["similarity", "Похожие вещества (similarity)", "НЕ то же самое соединение"]
];

const CHECK_LABEL: Record<CheckStatus, string> = {
  found: "найдено",
  not_found: "не найдено",
  unavailable: "недоступно",
  skipped: "не требуется"
};

function checkTone(status: CheckStatus | undefined): string {
  if (status === "found") return "badge-high";
  if (status === "unavailable") return "badge-low";
  return "badge-medium";
}

export default function IdentificationTab({ state }: Props) {
  if (state.loading) {
    return (
      <div className="tab-state">
        <div className="spinner" />
        <p>Проверяем соединение в PubChem…</p>
        <small>Локальные результаты RDKit уже доступны на других вкладках.</small>
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="tab-note tab-note-error">
        {state.error} Локальный анализ выполнен.
      </div>
    );
  }

  const id = state.data;
  if (!id) return null;

  const headline =
    id.status === "found"
      ? id.match_type === "exact"
        ? "Найдено в PubChem (точное совпадение)"
        : "Найдено в PubChem (только по связности)"
      : id.status === "unavailable"
        ? "PubChem недоступен"
        : "Точное соединение не найдено";

  return (
    <div>
      <div className="section-label">Идентификация (PubChem)</div>

      <div className="compound-card">
        <div
          className={`compound-status${id.status === "found" ? "" : " muted"}`}
        >
          {headline}
        </div>

        {id.found ? (
          <>
            {id.match_type === "exact" ? (
              <>
                <h3>{id.title ?? "Соединение найдено, название отсутствует"}</h3>
                {id.iupac_name && <p className="iupac">{id.iupac_name}</p>}
              </>
            ) : (
              <>
                <h3>{id.title ? `Возможно, это: ${id.title}` : "Найден кандидат без названия"}</h3>
                {id.iupac_name && (
                  <p className="iupac">
                    IUPAC кандидата (не подтверждает тождество): {id.iupac_name}
                  </p>
                )}
              </>
            )}
            <div className="compound-meta">
              {id.cid && <span>{id.match_type === "exact" ? "CID" : "CID кандидата"} {id.cid}</span>}
              {id.inchikey && <span>{id.inchikey}</span>}
            </div>
            {id.synonyms.length > 0 && (
              <>
                {id.match_type === "connectivity" && <p className="iupac">Синонимы записи-кандидата:</p>}
                <div className="chip-row" style={{ marginTop: 10 }}>
                  {id.synonyms.slice(0, 8).map((s) => (
                    <span className="chip" key={s}>
                      {s}
                    </span>
                  ))}
                </div>
              </>
            )}
            {id.source_url && (
              <a
                className="pubchem-link"
                href={id.source_url}
                target="_blank"
                rel="noreferrer"
              >
                {id.match_type === "exact" ? "Открыть подтверждённую запись PubChem ↗" : "Открыть запись-кандидат в PubChem ↗"}
              </a>
            )}
          </>
        ) : (
          <>
            <h3>Название не определено</h3>
            <p>
              {id.status === "unavailable"
                ? "PubChem недоступен — локальный анализ выполнен."
                : "Структура не подтверждена внешней базой, поэтому приложение не присваивает ей название."}
            </p>
          </>
        )}
      </div>

      {id.message && id.status === "found" && (
        <div className="tab-note tab-note-warn">{id.message}</div>
      )}

      <div className="section-label">Уровни проверки</div>
      <div className="check-list">
        {CHECKS.map(([key, title, hint]) => {
          const status = id.checks[key] as CheckStatus | undefined;
          return (
            <div className="check-row" key={key}>
              <div>
                <strong>{title}</strong>
                <span>
                  {key === "similarity"
                    ? `${hint} · порог ${id.similarity_threshold}%`
                    : hint}
                </span>
              </div>
              <span className={`badge ${checkTone(status)}`}>
                {status ? CHECK_LABEL[status] : "—"}
              </span>
            </div>
          );
        })}
      </div>

      {id.similar.length > 0 && (
        <>
          <div className="section-label">
            Похожие вещества — это НЕ то же самое соединение
          </div>
          <div className="neighbor-list">
            {id.similar.map((s) => (
              <div className="neighbor-row" key={s.cid}>
                <div>
                  <strong>{s.title ?? `CID ${s.cid}`}</strong>
                  <span>{s.iupac_name ?? "название не указано"}</span>
                </div>
                {s.source_url && (
                  <a
                    className="pubchem-link"
                    href={s.source_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    CID {s.cid} ↗
                  </a>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      <div className="tab-note">
        Название присваивается только при подтверждении PubChem. Совпадение
        «по связности» не гарантирует тождество стереоизомеров или изотопных
        форм, а похожие вещества — это другие соединения.
      </div>
    </div>
  );
}
