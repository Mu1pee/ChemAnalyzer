import { useMemo } from "react";
import { Editor } from "ketcher-react";
import type { Ketcher } from "ketcher-core";
import { StandaloneStructServiceProvider } from "ketcher-standalone";

import "ketcher-react/dist/index.css";

interface Props {
  onReady: (ketcher: Ketcher) => void;
}

/**
 * Редактор структур Ketcher (standalone). Вся логика действий — анализ,
 * очистка, импорт — находится в App и панели инструментов; здесь только
 * сам холст. Отмена/повтор: кнопки Ketcher и Ctrl+Z / Ctrl+Y.
 */
export default function KetcherEditor({ onReady }: Props) {
  const provider = useMemo(() => new StandaloneStructServiceProvider(), []);

  return (
    <div className="ketcher-shell">
      <Editor
        staticResourcesUrl={`${import.meta.env.BASE_URL}ketcher-assets`}
        structServiceProvider={provider}
        disableMacromoleculesEditor
        onInit={(instance: Ketcher) => {
          onReady(instance);
          instance.setMolecule("CCO").catch(() => {
            // Начальный пример необязателен.
          });
        }}
        errorHandler={(message: string) => {
          console.error("Ketcher:", message);
        }}
      />
    </div>
  );
}
