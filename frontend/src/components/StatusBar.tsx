export type ApiStatus = "checking" | "online" | "offline";

interface Props {
  apiStatus: ApiStatus;
  version: string;
  desktop: boolean;
  busy: boolean;
}

const LABEL: Record<ApiStatus, string> = {
  checking: "Запуск движка…",
  online: "Движок RDKit: готов",
  offline: "Движок RDKit: нет связи"
};

export default function StatusBar({ apiStatus, version, desktop, busy }: Props) {
  return (
    <footer className="statusbar">
      <span className={`status-dot status-${apiStatus}`} role="status">
        <i aria-hidden="true" />
        {LABEL[apiStatus]}
      </span>
      {busy && <span className="status-busy">Выполняется анализ…</span>}
      <span className="status-spacer" />
      <span>{desktop ? "Приложение Windows" : "Браузер"}</span>
      <span className="status-version">v{version}</span>
    </footer>
  );
}
