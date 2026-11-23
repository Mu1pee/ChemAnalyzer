import { useCallback, useEffect, useRef, useState } from "react";
import type { Ketcher } from "ketcher-core";
import { Activity, ArrowDownToLine, Atom, Beaker, BookOpen, ChevronRight, CircleHelp, Cuboid, Database, FlaskConical, History, Layers3, Menu, Microscope, PanelTop, Play, ScanLine, ShieldCheck, Sparkles, X } from "lucide-react";

import AboutDialog from "./components/AboutDialog";
import EditorToolbar from "./components/EditorToolbar";
import KetcherEditor from "./components/KetcherEditor";
import MenuBar, { type MenuDef } from "./components/MenuBar";
import { IconLogo } from "./components/Icons";
import ResultsPanel, { TABS, type Tab } from "./components/ResultsPanel";
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
const TAB_ICONS = { bioactivity: Layers3, props: Atom, adme: FlaskConical, ident: ScanLine, drug: ShieldCheck,
  activity: Activity, antidote: Beaker, chembl: Database, cyp: FlaskConical, screening: Microscope, metabolism: FlaskConical, solubility: Beaker, "3d": Cuboid, history: History, research: Sparkles, assistant: BookOpen };
const NAV_GROUPS: { label: string; tabs: Tab[] }[] = [
  { label: "Структура", tabs: ["props", "ident", "3d", "history"] },
  { label: "Анализ", tabs: ["adme", "drug", "activity", "cyp", "screening", "metabolism", "solubility", "antidote"] },
  { label: "Данные и исследования", tabs: ["bioactivity", "chembl", "research", "assistant"] }
];
const TAB_LABELS = Object.fromEntries(TABS.map(({ id, label }) => [id, label])) as Record<Tab, string>;
TAB_LABELS["3d"] = "3D-структура";
TAB_LABELS.history = "История анализов";
const FULL_WORKSPACES = new Set<Tab>(["bioactivity", "research", "history", "assistant"]);

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
  const [navigationOpen, setNavigationOpen] = useState(false);
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
  const contentRef = useRef<HTMLDivElement | null>(null);
  const fullWorkspace = FULL_WORKSPACES.has(tab);

  const openTab = useCallback((section: Tab) => {
    contentRef.current?.scrollTo({ top: 0, behavior: "instant" });
    setTab(section);
    setNavigationOpen(false);
  }, []);

  function focusImport() {
    if (fullWorkspace) openTab("props");
    requestAnimationFrame(() => importRef.current?.focus());
  }

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
    if (fullWorkspace) openTab("props");
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
  }, [ketcher, working, fullWorkspace, openTab]);

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
      openTab("props");
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

  const exportEntries: MenuDef["entries"] = [
    { type: "item", label: "SMILES (.smi)", onClick: exportSmiles },
    { type: "item", label: "JSON", onClick: exportJson },
    { type: "item", label: "CSV", onClick: exportCsv },
    { type: "item", label: "Изображение SVG", onClick: exportSvg },
    { type: "item", label: "Изображение PNG", onClick: exportPng },
    { type: "item", label: "PDF-отчёт", onClick: exportPdf }
  ];
  const menus: MenuDef[] = [
      {
        label: "Файл",
        entries: [
          { type: "item", label: "Новая структура", onClick: clearEditor, disabled: !ketcher },
          { type: "item", label: "Импорт SMILES…", onClick: focusImport, disabled: !ketcher },
          { type: "separator" },
          { type: "header", label: "Экспорт" },
          ...exportEntries.map((entry) => ({ ...entry, disabled: !result })),
          ...(isDesktop
            ? ([
                { type: "separator" },
                { type: "item", label: "Выход", onClick: () => bridge?.quit() }
              ] as const)
            : [])
        ]
      },
      {
        label: "Правка",
        entries: [
          { type: "item", label: "Очистить холст", onClick: clearEditor, disabled: !ketcher },
          { type: "item", label: "Копировать SMILES", onClick: copySmiles, disabled: !result },
          { type: "separator" },
          { type: "item", label: "Анализировать", hint: "Ctrl+Enter", onClick: analyzeFromEditor, disabled: !ketcher || working },
          { type: "header", label: "Отмена / повтор: Ctrl+Z, Ctrl+Y (в редакторе)" }
        ]
      },
      {
        label: "Вид",
        entries: [
          { type: "item", label: "Тёмная тема", checked: theme === "dark", onClick: () => setTheme("dark") },
          { type: "item", label: "Светлая тема", checked: theme === "light", onClick: () => setTheme("light") },
          { type: "separator" },
          { type: "item", label: "История анализов", onClick: () => openTab("history") }
        ]
      },
      {
        label: "Настройки",
        entries: [
          ...(isDesktop
            ? ([
                { type: "item", label: "Открыть папку данных (ключ API, модели)", onClick: () => bridge?.openDataFolder() }
              ] as const)
            : []),
          { type: "item", label: "Очистить историю", onClick: clearHistory, disabled: history.length === 0 }
        ]
      }
  ];

  return (
    <div className="app-shell">
      <header className="workbench-header">
        <div className="workbench-brand">
          <button type="button" className="shell-icon nav-toggle" aria-controls="workspace-navigation" aria-expanded={navigationOpen}
            aria-label={navigationOpen ? "Скрыть разделы" : "Показать разделы"} onClick={() => setNavigationOpen(!navigationOpen)}>
            {navigationOpen ? <X size={19} /> : <Menu size={19} />}
          </button>
          <span className="workbench-logo"><IconLogo size={23} /></span>
          <strong>ChemAnalyzer</strong>
          <span className="workbench-version">{version}</span>
        </div>
        <MenuBar menus={menus} />
        <button type="button" className="shell-icon workbench-help" aria-label="Справка о программе"
          title="Справка о программе" onClick={() => setAboutOpen(true)}><CircleHelp size={18} /></button>
      </header>

      <div className="workbench-frame">
        <nav id="workspace-navigation" className={`workspace-sidebar${navigationOpen ? " is-open" : ""}`} aria-label="Разделы анализа">
          {NAV_GROUPS.map((group) => (
            <div className="navigation-group" key={group.label}>
              <div className="navigation-group-label">{group.label}</div>
              {group.tabs.map((item) => {
                const TabIcon = TAB_ICONS[item];
                return <button key={item} type="button" aria-current={tab === item ? "page" : undefined}
                  className={tab === item ? "selected" : ""} onClick={() => openTab(item)}>
                  <TabIcon size={16} aria-hidden="true" /><span>{TAB_LABELS[item]}</span>
                </button>;
              })}
            </div>
          ))}
        </nav>
        <main className="workbench-main" ref={contentRef}>
          <div className="workbench-content">
            <div className="workbench-location">
              <PanelTop size={14} aria-hidden="true" />
              <span>Рабочая область</span>
              <ChevronRight size={13} aria-hidden="true" />
              <strong>{TAB_LABELS[tab]}</strong>
            </div>
            {!fullWorkspace && (
              <div className="molecule-heading">
                <div>
                  <h1>Молекулярный анализ</h1>
                  <p>Редактируйте структуру и изучайте её свойства.</p>
                </div>
                <div className="molecule-heading-actions">
                  <MenuBar label="Экспорт" buttonIcon={<ArrowDownToLine size={15} aria-hidden="true" />}
                    menus={[{ label: "Экспорт", disabled: !result, entries: exportEntries }]} />
                  <button id="analyze-structure" type="button" className="primary-button with-icon"
                    disabled={!ketcher || working} onClick={analyzeFromEditor}
                    aria-keyshortcuts="Control+Enter Meta+Enter" title="Анализировать структуру (Ctrl+Enter)">
                    <Play size={15} aria-hidden="true" /> {working ? "Анализ…" : "Анализировать"}
                  </button>
                </div>
              </div>
            )}
            <div className={`molecule-workspace${fullWorkspace ? " is-wide" : ""}`}>
              <section className="desk-editor" aria-labelledby="editor-heading" hidden={fullWorkspace}>
                <header className="editor-heading">
                  <span className="editor-heading-icon"><Atom size={19} aria-hidden="true" /></span>
                  <div><h2 id="editor-heading">Редактор структуры</h2><span>Двумерный холст Ketcher</span></div>
                  <button className="ghost-button with-icon editor-view" type="button" onClick={() => openTab(tab === "3d" ? "props" : "3d")}>
                    {tab === "3d" ? <PanelTop size={15} aria-hidden="true" /> : <Cuboid size={15} aria-hidden="true" />}
                    {tab === "3d" ? "Свойства" : "3D-вид"}
                  </button>
                </header>
                {error && (
                  <div className="error-banner" role="alert">
                    <strong>Ошибка</strong>
                    <span>{error}</span>
                    <button type="button" className="text-button" onClick={() => setError("")}>Скрыть</button>
                  </div>
                )}
                <KetcherEditor onReady={setKetcher} />
                <EditorToolbar
                  ready={Boolean(ketcher)}
                  inputRef={importRef}
                  onClear={clearEditor}
                  onImport={importSmiles}
                  onExample={(smiles) => importSmiles(smiles)}
                />
              </section>
              <ResultsPanel
                tab={tab}
                onTab={openTab}
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
            </div>
          </div>
        </main>
      </div>

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
