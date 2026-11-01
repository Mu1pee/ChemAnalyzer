import { useEffect, useRef, useState } from "react";

export type ViewKind = "protein" | "ligand";
export type ViewStyle =
  | "plddt"
  | "spectrum"
  | "lines"
  | "ballstick"
  | "stick"
  | "sphere";

interface Props {
  data: string;
  format: "pdb" | "sdf" | "mol";
  kind: ViewKind;
  style: ViewStyle;
  height?: number;
}

// Минимальный интерфейс 3Dmol, который мы реально используем.
interface Viewer {
  addModel(data: string, format: string): unknown;
  removeAllModels(): void;
  setStyle(selection: object, style: object): void;
  zoomTo(): void;
  render(): void;
  spin(on: boolean): void;
  resize(): void;
  clear(): void;
}

// Официальные цвета pLDDT из AlphaFold DB (значение лежит в B-факторе, 0–100).
export const PLDDT_BANDS = [
  { color: "#0053D6", label: "> 90 очень высокая" },
  { color: "#65CBF3", label: "70–90 высокая" },
  { color: "#FFDB13", label: "50–70 низкая" },
  { color: "#FF7D45", label: "< 50 очень низкая" }
];

function plddtColor(b: number): string {
  if (b > 90) return PLDDT_BANDS[0].color;
  if (b > 70) return PLDDT_BANDS[1].color;
  if (b > 50) return PLDDT_BANDS[2].color;
  return PLDDT_BANDS[3].color;
}

function styleSpec(style: ViewStyle): object {
  switch (style) {
    case "plddt":
      return { cartoon: { colorfunc: (atom: { b: number }) => plddtColor(atom.b) } };
    case "spectrum":
      return { cartoon: { color: "spectrum" } };
    case "lines":
      return { line: {} };
    case "stick":
      return { stick: { radius: 0.16 } };
    case "sphere":
      return { sphere: { scale: 0.9 } };
    case "ballstick":
    default:
      return { stick: { radius: 0.14 }, sphere: { scale: 0.26 } };
  }
}

export default function MolViewer({
  data,
  format,
  kind,
  style,
  height = 320
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [spinning, setSpinning] = useState(false);

  // Создание просмотрщика (3Dmol подгружается лениво — он тяжёлый).
  useEffect(() => {
    let cancelled = false;
    let observer: ResizeObserver | null = null;

    async function init() {
      try {
        // Через unknown: не зависим от точных типов пакета 3dmol.
        const mod: unknown = await import("3dmol");
        const lib = ((mod as { default?: unknown }).default ?? mod) as {
          createViewer(el: HTMLElement, config: object): Viewer;
        };
        if (cancelled || !containerRef.current) return;

        const viewer = lib.createViewer(containerRef.current, {
          backgroundColor: "#07101c",
          antialias: true
        });
        viewerRef.current = viewer;

        observer = new ResizeObserver(() => viewer.resize());
        observer.observe(containerRef.current);
        setReady(true);
      } catch {
        if (!cancelled) {
          setError(
            "Не удалось запустить 3D-просмотрщик. Возможно, в системе отключён WebGL."
          );
        }
      }
    }

    init();

    return () => {
      cancelled = true;
      observer?.disconnect();
      try {
        viewerRef.current?.spin(false);
        viewerRef.current?.clear();
      } catch {
        // просмотрщик уже уничтожен
      }
      viewerRef.current = null;
    };
  }, []);

  // Загрузка структуры и стиля.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!ready || !viewer) return;

    try {
      viewer.removeAllModels();
      viewer.addModel(data, format);
      viewer.setStyle({}, styleSpec(style));
      viewer.zoomTo();
      viewer.render();
      viewer.spin(spinning);
      setError("");
    } catch {
      setError("Не удалось отобразить структуру.");
    }
    // spinning применяется отдельным эффектом ниже
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, data, format, style]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!ready || !viewer) return;
    try {
      viewer.spin(spinning);
    } catch {
      // игнорируем
    }
  }, [ready, spinning]);

  function resetView() {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.zoomTo();
    viewer.render();
  }

  function toggleFullscreen() {
    const el = wrapperRef.current;
    if (!el) return;
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => undefined);
    } else {
      el.requestFullscreen?.().catch(() => undefined);
    }
  }

  return (
    <div className="viewer-wrap" ref={wrapperRef}>
      <div
        className="viewer-canvas"
        ref={containerRef}
        style={{ height }}
        aria-label="3D-структура: вращайте мышью, колесо — масштаб"
      />
      {error && <div className="viewer-error">{error}</div>}
      <div className="viewer-toolbar">
        <button
          type="button"
          className="ghost-button"
          onClick={() => setSpinning((value) => !value)}
        >
          {spinning ? "Остановить вращение" : "Вращать"}
        </button>
        <button type="button" className="ghost-button" onClick={resetView}>
          Сбросить вид
        </button>
        <button type="button" className="ghost-button" onClick={toggleFullscreen}>
          Во весь экран
        </button>
      </div>
      {kind === "protein" && style === "plddt" && (
        <div className="plddt-legend">
          {PLDDT_BANDS.map((band) => (
            <span key={band.label}>
              <i style={{ background: band.color }} />
              {band.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
