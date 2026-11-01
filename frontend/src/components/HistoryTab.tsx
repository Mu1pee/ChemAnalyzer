import type { HistoryItem } from "../types/molecule";

interface Props {
  items: HistoryItem[];
  onSelect: (item: HistoryItem) => void;
  onClear: () => void;
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

export default function HistoryTab({ items, onSelect, onClear }: Props) {
  return (
    <div>
      <div className="history-head">
        <div className="section-label" style={{ margin: 0 }}>
          Последние анализы
        </div>
        {items.length > 0 && (
          <button type="button" className="text-button" onClick={onClear}>
            Очистить историю
          </button>
        )}
      </div>

      {items.length === 0 ? (
        <p className="history-empty">
          Здесь будут храниться последние структуры на этом устройстве. Нажмите
          на запись, чтобы снова открыть молекулу.
        </p>
      ) : (
        <div className="history-list">
          {items.map((item) => (
            <button
              className="history-item"
              key={item.id}
              onClick={() => onSelect(item)}
              type="button"
            >
              <span className="history-date">{formatDate(item.analyzedAt)}</span>
              <strong>{item.title ?? "Название не определено"}</strong>
              <span className="history-formula">
                {item.formula}
                {item.cid ? ` · CID ${item.cid}` : ""}
              </span>
              <code>{item.smiles}</code>
              {item.summary && (
                <span className="history-summary">{item.summary}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
