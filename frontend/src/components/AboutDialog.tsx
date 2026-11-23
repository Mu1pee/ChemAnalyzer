import { useEffect, useRef } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
  version: string;
  desktop: boolean;
  dataDir: string | null;
}

export default function AboutDialog({ open, onClose, version, desktop, dataDir }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (!open) return;
    const dialog = dialogRef.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, [open]);

  if (!open) return null;

  return (
      <dialog
        ref={dialogRef}
        className="modal"
        aria-label="О программе"
        onCancel={(event) => { event.preventDefault(); onClose(); }}
      >
        <div className="modal-head">
          <div>
            <h2>ChemAnalyzer</h2>
            <span>
              версия {version} · {desktop ? "desktop" : "браузер"}
            </span>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Закрыть
          </button>
        </div>

        <div className="modal-body">
          <h3>Источники данных</h3>
          <ul>
            <li><strong>RDKit</strong> — локальный расчёт дескрипторов, 2D/3D.</li>
            <li><strong>PubChem</strong> (NCBI) — идентификация соединения.</li>
            <li><strong>ChEMBL</strong> (EMBL-EBI) — экспериментальные данные об активности.</li>
            <li><strong>ПК «Антидот-Прогноз»</strong> — отдельные endpoint-модели антидотной и рострегулирующей активности (нужны проверенные обучающие данные).</li>
            <li><strong>AlphaFold DB</strong> (DeepMind, EMBL-EBI; CC BY 4.0) — структуры белков-мишеней.</li>
            <li><strong>Ketcher</strong> — редактор структур; <strong>3Dmol.js</strong> — 3D-просмотр.</li>
            <li><strong>Claude API</strong> (необязательно) — ассистент, нужен ваш ключ.</li>
          </ul>

          <h3>Ограничения</h3>
          <ul>
            <li>Расчётные значения и прогнозы требуют экспериментальной проверки.</li>
            <li>Drug-likeness — эвристические правила, а не медицинское заключение.</li>
            <li>Оценка по сходству и QSAR — не PASS/Way2Drug и не доказательство активности.</li>
            <li>ПК «Антидот-Прогноз» не поставляется с обученными моделями; без подтверждённых данных прогноз не выдаётся.</li>
            <li>3D-конформер — один расчётный вариант, а не экспериментальная структура.</li>
            <li>Название вещества присваивается только при подтверждении PubChem.</li>
          </ul>

          {desktop && dataDir && (
            <>
              <h3>Данные пользователя</h3>
              <p className="modal-path">{dataDir}</p>
              <p>
                Здесь лежат файл <code>.env</code> (ключ ассистента), папка{" "}
                <code>models</code> (QSAR и специализированные модели) и журналы.
              </p>
            </>
          )}
        </div>
      </dialog>
  );
}
