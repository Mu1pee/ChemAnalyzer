import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Ketcher } from "ketcher-core";

import AboutDialog from "./components/AboutDialog";
import EditorToolbar, { EXAMPLES } from "./components/EditorToolbar";
import KetcherEditor from "./components/KetcherEditor";
import MenuBar, { type MenuDef } from "./components/MenuBar";
import ResultsPanel, { type Tab } from "./components/ResultsPanel";
import StatusBar, { type ApiStatus } from "./components/StatusBar";
import {
  analyzeMolecule,
  ApiNetworkError,
  checkHealth,
  fetchAdme,
  fetchAppInfo,
  fetchChembl,
  fetchDepiction,
  identifyMolecule,
  predictActivity
} from "./api/chemistry";
import { bridge, isDesktop } from "./lib/desktop";
import {
  VERDICT_LABEL,
  evaluateCriteria,
  summarizeLipinski
} from "./lib/druglike";
import {
  buildCsv,
  buildReportHtml,
  saveBlob,
  savePdfReport,
  saveText,
  svgToPng,
  type SaveOutcome
} from "./lib/exporters";
import { HISTORY_LIMIT, mergeHistory, parseHistory } from "./lib/history";
import { loadStored, saveStored } from "./lib/storage";
import { applyTheme, parseTheme, type Theme } from "./lib/theme";
import type {
  ActivityResponse,
  AdmeResponse,
  AsyncState,
  ChemblResponse,
  HistoryItem,
  IdentificationResult,
  MoleculeResponse
} from "./types/molecule";

const FALLBACK_VERSION = __APP_VERSION__;

// Пустой molfile надёжнее, чем setMolecule("").
const EMPTY_MOLFILE =
  "\n  ChemAnalyzer\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n";

function idle<T>(): AsyncState<T> {
  return { data: null, loading: false, error: "" };
}

function busy<T>(): AsyncState<T> {
  return { data: null, loading: true, error: "" };
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

function summarize(result: MoleculeResponse, id: IdentificationResult | null): string {
  const lip = summarizeLipinski(evaluateCriteria(result));
  const parts = [
    `MW ${result.molecular_weight.toFixed(1)}`,
    `Липински ${VERDICT_LABEL[lip.verdict]}`
  ];
  if (id?.status === "found") {
    parts.push(id.match_type === "exact" ? "PubChem: найдено" : "PubChem: только по связности");
  } else if (id?.status === "not_found") parts.push("PubChem: не найдено");
  else if (id?.status === "unavailable") parts.push("PubChem: недоступен");
  return parts.join(" · ");
}

interface Notice {
  kind: "ok" | "error";
  text: string;
}

function App() {
  const [result, setResult] = useState<MoleculeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [ketcher, setKetcher] = useState<Ketcher | null>(null);
  const [working, setWorking] = useState(false);

  const [identification, setIdentification] =
    useState<AsyncState<IdentificationResult>>(idle);
  const [adme, setAdme] = useState<AsyncState<AdmeResponse>>(idle);
  const [activity, setActivity] = useState<AsyncState<ActivityResponse>>(idle);
  const [chembl, setChembl] = useState<AsyncState<ChemblResponse>>(idle);

  const [tab, setTab] = useState<Tab>("props");
  const [theme, setTheme] = useState<Theme>("dark");
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [version, setVersion] = useState(FALLBACK_VERSION);
  const [dataDir, setDataDir] = useState<string | null>(null);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  const runId = useRef(0);
  // Сохранять можно только после загрузки сохранённого: иначе пустое начальное
  // состояние затёрло бы историю и тему.
  const historyLoaded = useRef(false);
  const themeLoaded = useRef(false);
  const importRef = useRef<HTMLInputElement | null>(null);

  // ---------------------------------------------------------- служебное

  useEffect(() => {
    let cancelled = false;
    loadStored("history").then((raw) => {
      if (cancelled) return;
      setHistory((current) => mergeHistory(current, parseHistory(raw)));
      historyLoaded.current = true;
    });
    loadStored("theme").then((raw) => {
      if (cancelled) return;
      const saved = parseTheme(raw);
      if (saved) setTheme(saved);
      themeLoaded.current = true;
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    applyTheme(theme);
    if (themeLoaded.current) saveStored("theme", theme);
  }, [theme]);

  useEffect(() => {
    let cancelled = false;

    async function ping() {
      const ok = await checkHealth();
      if (cancelled) return;
      setApiStatus(ok ? "online" : "offline");
    }

    ping();
    const timer = window.setInterval(ping, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (apiStatus !== "online") return;
    fetchAppInfo().then((info) => info && setVersion(info.version));
    bridge?.getInfo().then((info) => info && setDataDir(info.dataDir));
  }, [apiStatus]);

  useEffect(() => {
    if (historyLoaded.current) saveStored("history", JSON.stringify(history));
  }, [history]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 6000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const notify = useCallback((kind: Notice["kind"], text: string) => {
    setNotice({ kind, text });
  }, []);

  const reportSave = useCallback(
    (outcome: SaveOutcome, what: string) => {
      if (outcome.canceled) return;
      if (outcome.ok) {
        notify("ok", outcome.path ? `${what}: сохранено в ${outcome.path}` : `${what}: готово`);
      } else {
        notify("error", `${what}: не удалось сохранить${outcome.message ? ` (${outcome.message})` : ""}.`);
      }
    },
    [notify]
  );

  // ---------------------------------------------------------- анализ

  function resetResults() {
    runId.current += 1;
    setLoading(false);
    setResult(null);
    setIdentification(idle());
    setAdme(idle());
    setActivity(idle());
    setChembl(idle());
    setError("");
  }

  function loadSecondary(smiles: string, id: number) {
    setIdentification(busy());
    setAdme(busy());
    setActivity(busy());
    setChembl(busy());

    const guard = <T,>(
      setter: (state: AsyncState<T>) => void,
      fallback: string
    ) => ({
      ok: (data: T) => {
        if (id === runId.current) setter({ data, loading: false, error: "" });
      },
      fail: (err: unknown) => {
        if (id === runId.current) {
          setter({ data: null, loading: false, error: errorMessage(err, fallback) });
        }
      }
    });

    const ident = guard(setIdentification, "PubChem недоступен — локальный анализ выполнен.");
    identifyMolecule(smiles)
      .then((data) => {
        ident.ok(data);
        if (id !== runId.current) return;
        setHistory((current) =>
          current.map((item) =>
            item.smiles === smiles
              ? {
                  ...item,
                  // Название в истории — только при точном совпадении.
                  title: data.found && data.match_type === "exact" ? data.title : null,
                  cid: data.found && data.match_type === "exact" ? data.cid : null,
                  summary: item.summary.split(" · PubChem")[0] +
                    (data.status === "found"
                      ? data.match_type === "exact"
                        ? " · PubChem: найдено"
                        : " · PubChem: только по связности"
                      : data.status === "unavailable"
                        ? " · PubChem: недоступен"
                        : " · PubChem: не найдено")
                }
              : item
          )
        );
      })
      .catch(ident.fail);

    const adm = guard(setAdme, "Не удалось рассчитать ADME-профиль.");
    fetchAdme(smiles).then(adm.ok).catch(adm.fail);

    const act = guard(setActivity, "Не удалось рассчитать биологическую активность.");
    predictActivity(smiles).then(act.ok).catch(act.fail);

    const chem = guard(setChembl, "ChEMBL недоступен — локальный анализ выполнен.");
    fetchChembl(smiles).then(chem.ok).catch(chem.fail);
  }

  async function handleAnalyze(smiles: string) {
    const id = ++runId.current;
    setLoading(true);
    setError("");

    try {
      const data = await analyzeMolecule(smiles);
      if (id !== runId.current) return;

      setApiStatus("online");
      setResult(data);
      loadSecondary(data.canonical_smiles, id);

      const entry: HistoryItem = {
        id: crypto.randomUUID(),
        analyzedAt: new Date().toISOString(),
        formula: data.formula,
        smiles: data.canonical_smiles,
        title: null,
        cid: null,
        summary: summarize(data, null)
      };
      setHistory((current) =>
        [entry, ...current.filter((item) => item.smiles !== entry.smiles)].slice(
          0,
          HISTORY_LIMIT
        )
      );
    } catch (err) {
      if (id !== runId.current) return;
      if (err instanceof ApiNetworkError) setApiStatus("offline");
      setResult(null);
      setIdentification(idle());
      setAdme(idle());
      setActivity(idle());
      setChembl(idle());
      setError(errorMessage(err, "Не удалось распознать химическую структуру."));
    } finally {
      if (id === runId.current) setLoading(false);
    }
  }

  const analyzeFromEditor = useCallback(async () => {
    if (!ketcher || working) return;
    setWorking(true);
    try {
      const smiles = await ketcher.getSmiles();
      if (!smiles.trim()) {
        setResult(null);
        setError("Редактор пустой. Нарисуйте молекулу.");
        return;
      }
      await handleAnalyze(smiles);
    } catch (err) {
      setError(
        err instanceof Error && err.message
          ? `Не удалось получить структуру из редактора: ${err.message}`
          : "Не удалось получить структуру из редактора."
      );
    } finally {
      setWorking(false);
    }
    // handleAnalyze использует только стабильные setState и refs
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ketcher, working]);

  // Ctrl+Enter — анализ.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        analyzeFromEditor();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [analyzeFromEditor]);

  // ---------------------------------------------------------- редактор

  async function importSmiles(smiles: string): Promise<boolean> {
    if (!ketcher) return false;
    try {
      await ketcher.setMolecule(smiles);
      setError("");
      return true;
    } catch {
      setError("Не удалось распознать химическую структуру: проверьте SMILES.");
      return false;
    }
  }

  async function clearEditor() {
    if (!ketcher) return;
    try {
      await ketcher.setMolecule(EMPTY_MOLFILE);
    } catch {
      setError("Не удалось очистить редактор.");
      return;
    }
    resetResults();
  }

  async function selectHistory(item: HistoryItem) {
    if (!ketcher) return;
    if (await importSmiles(item.smiles)) {
      await handleAnalyze(item.smiles);
      setTab("props");
    }
  }

  function clearHistory() {
    setHistory([]);
  }

  // ---------------------------------------------------------- экспорт

  function needResult(): MoleculeResponse | null {
    if (!result) {
      notify("error", "Сначала выполните анализ структуры.");
      return null;
    }
    return result;
  }

  async function exportSmiles() {
    const r = needResult();
    if (r) reportSave(await saveText("chemanalyzer-structure.smi", `${r.canonical_smiles}\n`), "SMILES");
  }

  async function exportJson() {
    const r = needResult();
    if (!r) return;
    const payload = {
      generated_at: new Date().toISOString(),
      app_version: version,
      structure: r,
      identification: identification.data,
      adme: adme.data,
      biological_activity: activity.data,
      chembl: chembl.data
    };
    reportSave(
      await saveText(`chemanalyzer-${r.formula}.json`, JSON.stringify(payload, null, 2), "application/json"),
      "JSON"
    );
  }

  async function exportCsv() {
    const r = needResult();
    if (!r) return;
    const csv = buildCsv(r, identification.data, activity.data?.druglikeness.qed ?? null);
    reportSave(await saveText(`chemanalyzer-${r.formula}.csv`, csv, "text/csv"), "CSV");
  }

  async function depiction(r: MoleculeResponse): Promise<string | null> {
    try {
      return await fetchDepiction(r.canonical_smiles);
    } catch (err) {
      notify("error", errorMessage(err, "Не удалось построить изображение структуры."));
      return null;
    }
  }

  async function exportSvg() {
    const r = needResult();
    if (!r) return;
    const svg = await depiction(r);
    if (svg) reportSave(await saveText(`chemanalyzer-${r.formula}.svg`, svg, "image/svg+xml"), "SVG");
  }

  async function exportPng() {
    const r = needResult();
    if (!r) return;
    const svg = await depiction(r);
    if (!svg) return;
    try {
      reportSave(await saveBlob(`chemanalyzer-${r.formula}.png`, await svgToPng(svg)), "PNG");
    } catch (err) {
      notify("error", errorMessage(err, "Не удалось создать PNG."));
    }
  }

  async function exportPdf() {
    const r = needResult();
    if (!r) return;
    let svg: string | null = null;
    try {
      svg = await fetchDepiction(r.canonical_smiles);
    } catch {
      // Отчёт без картинки лучше, чем отсутствие отчёта.
    }
    const html = buildReportHtml({
      generatedAt: new Date(),
      appVersion: version,
      result: r,
      svg,
      identification: identification.data,
      activity: activity.data,
      chembl: chembl.data,
      adme: adme.data
    });
    reportSave(await savePdfReport(`chemanalyzer-${r.formula}-report.pdf`, html), "PDF-отчёт");
  }

  async function copySmiles() {
    const r = needResult();
    if (!r) return;
    try {
      await navigator.clipboard.writeText(r.canonical_smiles);
      notify("ok", "SMILES скопирован.");
    } catch {
      notify("error", "Не удалось скопировать в буфер обмена.");
    }
  }

  // ---------------------------------------------------------- меню

  const menus: MenuDef[] = useMemo(() => {
    const hasResult = Boolean(result);
    const goTab = (t: Tab) => () => setTab(t);

    return [
      {
        label: "File",
        entries: [
          { type: "item", label: "Новая структура", onClick: clearEditor, disabled: !ketcher },
          { type: "item", label: "Импорт SMILES…", onClick: () => importRef.current?.focus(), disabled: !ketcher },
          { type: "separator" },
          { type: "header", label: "Экспорт" },
          { type: "item", label: "SMILES (.smi)", onClick: exportSmiles, disabled: !hasResult },
          { type: "item", label: "JSON", onClick: exportJson, disabled: !hasResult },
          { type: "item", label: "CSV", onClick: exportCsv, disabled: !hasResult },
          { type: "item", label: "Изображение SVG", onClick: exportSvg, disabled: !hasResult },
          { type: "item", label: "Изображение PNG", onClick: exportPng, disabled: !hasResult },
          { type: "item", label: "PDF-отчёт", onClick: exportPdf, disabled: !hasResult },
          ...(isDesktop
            ? ([
                { type: "separator" },
                { type: "item", label: "Выход", onClick: () => bridge?.quit() }
              ] as const)
            : [])
        ]
      },
      {
        label: "Edit",
        entries: [
          { type: "item", label: "Очистить холст", onClick: clearEditor, disabled: !ketcher },
          { type: "item", label: "Копировать SMILES", onClick: copySmiles, disabled: !hasResult },
          { type: "separator" },
          { type: "header", label: "Отмена / повтор: Ctrl+Z, Ctrl+Y (в редакторе)" }
        ]
      },
      {
        label: "Structure",
        entries: [
          { type: "item", label: "Анализировать", hint: "Ctrl+Enter", onClick: analyzeFromEditor, disabled: !ketcher || working },
          { type: "separator" },
          { type: "header", label: "Примеры" },
          ...EXAMPLES.map((example) => ({
            type: "item" as const,
            label: example.name,
            onClick: () => importSmiles(example.smiles),
            disabled: !ketcher
          }))
        ]
      },
      {
        label: "Analysis",
        entries: [
          { type: "item", label: "Свойства", onClick: goTab("props") },
          { type: "item", label: "ADME / BOILED-Egg", onClick: goTab("adme") },
          { type: "item", label: "Идентификация", onClick: goTab("ident") },
          { type: "item", label: "Drug-likeness", onClick: goTab("drug") },
          { type: "item", label: "Активность / QSAR", onClick: goTab("activity") },
          { type: "item", label: "ПК «Антидот-Прогноз»", onClick: goTab("antidote") },
          { type: "item", label: "ChEMBL", onClick: goTab("chembl") },
          { type: "item", label: "3D-структура", onClick: goTab("3d") },
          { type: "item", label: "Ассистент Claude", onClick: goTab("assistant") }
        ]
      },
      {
        label: "View",
        entries: [
          { type: "item", label: "Тёмная тема", checked: theme === "dark", onClick: () => setTheme("dark") },
          { type: "item", label: "Светлая тема", checked: theme === "light", onClick: () => setTheme("light") },
          { type: "separator" },
          { type: "item", label: "История анализов", onClick: goTab("history") }
        ]
      },
      {
        label: "Settings",
        entries: [
          { type: "item", label: "Тема: тёмная", checked: theme === "dark", onClick: () => setTheme("dark") },
          { type: "item", label: "Тема: светлая", checked: theme === "light", onClick: () => setTheme("light") },
          ...(isDesktop
            ? ([
                { type: "separator" },
                { type: "item", label: "Открыть папку данных (ключ API, модели)", onClick: () => bridge?.openDataFolder() }
              ] as const)
            : []),
          { type: "separator" },
          { type: "item", label: "Очистить историю", onClick: clearHistory, disabled: history.length === 0 }
        ]
      },
      {
        label: "Help",
        entries: [
          { type: "item", label: "О программе", onClick: () => setAboutOpen(true) },
          { type: "item", label: "Источники данных и ограничения", onClick: () => setAboutOpen(true) }
        ]
      }
    ];
    // Действия зависят от актуальных данных; пересборка дешёвая.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result, ketcher, working, theme, history.length, identification.data, adme.data, activity.data, chembl.data, version]);

  return (
    <div className="app-shell">
      <MenuBar menus={menus} />

      <main className="desk">
        <section className="desk-editor">
          <EditorToolbar
            ready={Boolean(ketcher)}
            working={working}
            inputRef={importRef}
            onAnalyze={analyzeFromEditor}
            onClear={clearEditor}
            onImport={importSmiles}
            onExample={(smiles) => importSmiles(smiles)}
          />

          <KetcherEditor onReady={setKetcher} />

          {error && (
            <div className="error-banner" role="alert">
              <strong>Ошибка</strong>
              <span>{error}</span>
              <button type="button" className="text-button" onClick={() => setError("")}>
                Скрыть
              </button>
            </div>
          )}
        </section>

        <ResultsPanel
          tab={tab}
          onTab={setTab}
          result={result}
          loading={loading}
          identification={identification}
          adme={adme}
          activity={activity}
          chembl={chembl}
          history={history}
          onSelectHistory={selectHistory}
          onClearHistory={clearHistory}
        />
      </main>

      <StatusBar
        apiStatus={apiStatus}
        version={version}
        desktop={isDesktop}
        busy={loading || working}
      />

      {notice && (
        <div className={`toast toast-${notice.kind}`} role="status">
          {notice.text}
        </div>
      )}

      <AboutDialog
        open={aboutOpen}
        onClose={() => setAboutOpen(false)}
        version={version}
        desktop={isDesktop}
        dataDir={dataDir}
      />
    </div>
  );
}

export default App;
