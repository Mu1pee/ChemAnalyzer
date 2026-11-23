import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, ArrowDownToLine, ArrowRight, Atom, BookOpen, CheckCircle2, ChevronDown, Database, FlaskConical, Info, LayoutGrid, RefreshCw, Search, Workflow, X } from "lucide-react";
import { BIO_GROUPS, BIO_MODULES, type BioGroup, type BioModule, type ResearchPreset } from "../lib/bioactivity";
import { API_ORIGIN } from "../api/base";
import { saveText } from "../lib/exporters";
import type { Tab } from "./ResultsPanel";
import type { ActivityResponse, AsyncState, CapabilitiesResponse, ModelCapability } from "../types/molecule";

type AgentModel = { id: string; task: { endpoint: string; name: string }; status: string;
  quality?: { passed: boolean; metric: string; value: number | null; reasons: string[] } };
type AgentSummary = { enabled: boolean; models: AgentModel[]; error: string };
const groupIcons = { pharmacology: Activity, admet: FlaskConical, science: BookOpen, sources: Database };
const statusNames = { calculation: "Доступен расчёт", qsar: "Локальные модели", dataset: "Нужны данные", key: "API-ассистент", source: "Внешний источник" };
const modelModules = new Set(["targets", "cyp", "hiv", "hepg2", "metabolism", "solubility", "hydration", "antidote", "growth"]);
const capabilityLabels: Record<string, string> = { experimental: "Экспериментальная", validated: "Проверена в реестре", approved: "Утверждена",
  partial: "Допущена часть моделей", not_trained: "Модель не обучена", quality_failed: "Качество не пройдено",
  incompatible: "Нет совместимого контекста", archived: "Только архивные модели", error: "Ошибка проверки модели", disabled: "Нужно включить AI Research Lab" };

export default function BioactivityWorkspace({ onTab, onResearch, activity, hasMolecule }: {
  onTab: (tab: Tab) => void; onResearch: (preset?: ResearchPreset) => void;
  activity: AsyncState<ActivityResponse>; hasMolecule: boolean;
}) {
  const [category, setCategory] = useState<BioGroup | "all">("all");
  const [query, setQuery] = useState("");
  const [onlyReady, setOnlyReady] = useState(false);
  const [agent, setAgent] = useState<AgentSummary>({ enabled: false, models: [], error: "" });
  const [capabilities, setCapabilities] = useState<CapabilitiesResponse | null>(null);
  const [capabilityError, setCapabilityError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<BioModule | null>(null);
  const [notice, setNotice] = useState("");
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (!selected) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    dialog?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); setSelected(null); }
      if (event.key !== "Tab" || !dialog) return;
      const controls = dialog.querySelectorAll<HTMLElement>("button:not(:disabled), [href], input, select, textarea");
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
    document.addEventListener("keydown", onKey, true);
    return () => { document.removeEventListener("keydown", onKey, true); previousFocus?.focus(); };
  }, [selected]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    const research = (async () => {
      const response = await fetch(`${API_ORIGIN}/api/research/status`, { signal: controller.signal });
      if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) {
        throw new Error("Не удалось получить статус исследовательского агента");
      }
      const status: { enabled: boolean } = await response.json();
      let models: AgentModel[] = [];
      if (status.enabled) {
        const result = await fetch(`${API_ORIGIN}/api/research/models`, { signal: controller.signal });
        if (!result.ok || !result.headers.get("content-type")?.includes("application/json")) {
          throw new Error("Реестр моделей недоступен");
        }
        models = await result.json();
      }
      if (!controller.signal.aborted) setAgent({ enabled: status.enabled, models, error: "" });
    })().catch(error => {
      if (!controller.signal.aborted) {
        const message = error instanceof TypeError || error instanceof SyntaxError
          ? "Не удалось получить статус исследовательского агента"
          : String(error.message);
        setAgent({ enabled: false, models: [], error: message });
      }
    });
    const catalog = (async () => {
      const response = await fetch(`${API_ORIGIN}/api/molecules/capabilities`, { signal: controller.signal });
      if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) {
        throw new Error("Не удалось подтвердить доступность моделей");
      }
      const data: CapabilitiesResponse = await response.json();
      if (!controller.signal.aborted) { setCapabilities(data); setCapabilityError(""); }
    })().catch(() => {
      if (!controller.signal.aborted) { setCapabilities(null); setCapabilityError("Не удалось подтвердить доступность моделей"); }
    });
    Promise.allSettled([research, catalog]).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [refreshKey]);

  const capabilityMap = useMemo(() => new Map(capabilities?.modules.map(module => [module.id, module]) ?? []), [capabilities]);
  const filtered = useMemo(() => BIO_MODULES.filter(item => {
    const text = `${item.name} ${item.method} ${item.scope}`.toLocaleLowerCase("ru");
    return (category === "all" || item.group === category) && text.includes(query.trim().toLocaleLowerCase("ru"))
      && (!onlyReady || ["calculation", "source"].includes(item.status)
        || (!loading && capabilityMap.get(item.id)?.available === true));
  }), [query, category, onlyReady, capabilityMap, loading]);
  const localCount = capabilities?.modules.find(module => module.id === "targets")?.models_available;
  const liveModels = agent.models.filter(model => model.status === "approved" && model.quality?.passed);
  function capabilityLabel(item: BioModule) {
    if (!modelModules.has(item.id)) return statusNames[item.status];
    if (loading) return "Проверка моделей";
    const capability = capabilityMap.get(item.id);
    if (!capability) return "Статус не подтверждён";
    const label = capabilityLabels[capability.status] ?? "Статус не подтверждён";
    return capability.available ? `${label} · ${capability.models_available}/${capability.models_expected}` : label;
  }

  function capabilityTone(item: BioModule) {
    if (!modelModules.has(item.id)) return item.status;
    if (loading) return "pending";
    return capabilityMap.get(item.id)?.available ? "qsar" : "dataset";
  }

  function capabilityDescription(capability?: ModelCapability) {
    if (!capability) return "Доступность модели не подтверждена. Обновите проверку статусов.";
    return capability.available
      ? "Для совместимого экспериментального контекста есть допущенная модель. Прогноз требует проверки области применимости конкретной структуры. Внешняя валидация не заявлена."
      : capability.states.map(state => state.message).filter(Boolean).join(" ") || capabilityLabels[capability.status];
  }

  function open(item: BioModule) {
    if (["cyp", "hiv", "hepg2", "metabolism", "solubility"].includes(item.id) && item.tab) { onTab(item.tab); return; }
    if (item.status === "dataset" || item.status === "key") { setSelected(item); return; }
    if (item.tab) onTab(item.tab);
  }

  async function exportRegistry() {
    try {
      const outcome = await saveText("ChemAnalyzer-bioactivity.json", JSON.stringify({ exported_at: new Date().toISOString(), modules: BIO_MODULES,
        agent_enabled: agent.enabled, research_models: agent.models, capabilities, capability_error: capabilityError,
        local_qsar: activity.data?.qsar ?? null }, null, 2));
      setNotice(outcome.ok ? "Реестр сохранён" : outcome.canceled ? "Экспорт отменён" : "Не удалось сохранить реестр");
    } catch { setNotice("Не удалось сохранить реестр"); }
  }

  const metrics = [
    { label: "Модули каталога", value: BIO_MODULES.length, Icon: LayoutGrid },
    { label: "Допущено моделей мишеней", value: loading ? "…" : localCount ?? "—", Icon: Activity },
    { label: "Модели в реестре агента", value: loading ? "…" : capabilities?.registry_models ?? (agent.error ? "—" : agent.models.length), Icon: Database },
    { label: "Утверждено в реестре", value: loading ? "…" : capabilities?.registry_approved ?? (agent.error ? "—" : liveModels.length), Icon: CheckCircle2 }
  ];

  return <section className="bio-workspace" aria-labelledby="bio-title">
    <div className="bio-content">
      <header className="bio-heading">
        <div className="bio-title">
          <h1 id="bio-title">Биоактивность</h1>
          <p>Расчёты, исследовательские модели и экспериментальные данные.</p>
        </div>
        <div className="bio-heading-actions">
          <span className={`bio-agent-state ${agent.enabled && !loading ? "online" : ""}`} role="status"><i aria-hidden="true" />{loading ? "Проверка агента" : agent.error ? "Нет связи с агентом" : agent.enabled ? "Агент подключён" : "Агент выключен"}</span>
          <button className="bio-primary" type="button" onClick={() => onResearch()}><Workflow size={16} aria-hidden="true" /> AI Research Lab <ArrowRight size={15} aria-hidden="true" /></button>
        </div>
      </header>
      <dl className="bio-summary" aria-label="Состояние моделей">
        {metrics.map(({ label, value, Icon }) => <div key={label}>
          <dt><Icon size={15} aria-hidden="true" />{label}</dt>
          <dd>{value}</dd>
        </div>)}
      </dl>
      {(agent.error || capabilityError || capabilities?.registry_error || !!capabilities?.registry_invalid) && <div className="bio-alerts">
        {agent.error && <p className="bio-message" role="alert">{agent.error}</p>}
        {capabilityError && <p className="bio-message" role="alert">{capabilityError}</p>}
        {capabilities?.registry_error && <p className="bio-message" role="alert">{capabilities.registry_error}</p>}
        {!!capabilities?.registry_invalid && <p className="bio-message">Повреждённых записей реестра: {capabilities.registry_invalid}. Они исключены из прогнозирования.</p>}
      </div>}
      <div className="bio-contextbar">
        {!hasMolecule && <div className="bio-context"><Atom size={16} aria-hidden="true" /><span>Структура не выбрана</span><button type="button" onClick={() => onTab("props")}>Открыть редактор <ArrowRight size={14} aria-hidden="true" /></button></div>}
        <details className="bio-policy">
          <summary><Info size={14} aria-hidden="true" /> Условия допуска моделей <ChevronDown size={13} aria-hidden="true" /></summary>
          <p>Для классификации требуется сбалансированная точность &gt; 60% на отложенных структурах. Для регрессии — R² &gt; 0,60 и ошибка ниже базовой модели.</p>
          <p>R², вероятность активности и сходство структуры — разные показатели. Проверяйте статус обучения и подтверждайте исследовательские оценки экспериментально.</p>
        </details>
      </div>
      <div className="bio-tools" role="group" aria-label="Фильтры и действия каталога">
        <div className="bio-filterbar">
          <label className="bio-search"><Search size={17} aria-hidden="true" /><input type="search" aria-label="Поиск модулей биоактивности" placeholder="Найти модуль, мишень или метод…" value={query} onChange={e => setQuery(e.target.value)} /></label>
          <label className="bio-ready"><input type="checkbox" checked={onlyReady} onChange={e => setOnlyReady(e.target.checked)} />Только доступные</label>
          <div className="bio-tool-actions">
            <button className="bio-tool" type="button" title="Обновить реестр" aria-label="Обновить реестр" disabled={loading} onClick={() => setRefreshKey(x => x + 1)}><RefreshCw size={16} aria-hidden="true" /></button>
            <button className="bio-tool" type="button" title="Экспорт реестра JSON" aria-label="Экспорт реестра JSON" onClick={exportRegistry}><ArrowDownToLine size={16} aria-hidden="true" /><span>Экспорт JSON</span></button>
          </div>
        </div>
        <div className="bio-categories" role="group" aria-label="Направления биоактивности">
          {[{ id: "all" as const, name: "Все направления" }, ...BIO_GROUPS].map(group => <button key={group.id} type="button" aria-pressed={category === group.id} onClick={() => setCategory(group.id)}>{group.name}<span>{group.id === "all" ? BIO_MODULES.length : BIO_MODULES.filter(item => item.group === group.id).length}</span></button>)}
        </div>
      </div>
      {notice && <div className="bio-message bio-notice" role="status">{notice}</div>}
      {BIO_GROUPS.map(group => {
        const entries = filtered.filter(item => item.group === group.id);
        const Icon = groupIcons[group.id];
        return entries.length > 0 && <section className={`bio-band bio-band-${group.id}`} key={group.id} aria-labelledby={`bio-${group.id}`}>
          <div className="bio-band-heading"><span className="bio-band-icon"><Icon size={16} aria-hidden="true" /></span><h2 id={`bio-${group.id}`}>{group.name}</h2><span className="bio-band-count">{entries.length}</span></div>
          <div className="bio-grid">{entries.map(item => <article key={item.id} className="bio-module">
            <div className="bio-module-top"><span id={`bio-status-${item.id}`} className={`bio-badge bio-badge-${capabilityTone(item)}`}>{capabilityLabel(item)}</span></div>
            <h3><button type="button" aria-describedby={`bio-status-${item.id}`} onClick={() => open(item)}>{item.name}</button></h3>
            <p>{item.method}</p>
            <div className="bio-module-bottom"><span>{item.scope}</span><ArrowRight size={16} aria-hidden="true" /></div>
          </article>)}</div>
        </section>;
      })}
      {filtered.length === 0 && <div className="bio-empty" role="status"><Search size={24} aria-hidden="true" /><h2>Модули не найдены</h2><button type="button" onClick={() => { setQuery(""); setCategory("all"); setOnlyReady(false); }}>Сбросить фильтры</button></div>}
      {capabilities && <footer className="bio-footnote">Статусы моделей проверены: <time dateTime={capabilities.checked_at}>{new Date(capabilities.checked_at).toLocaleString()}</time></footer>}
    </div>
    {selected && <div className="bio-modal-backdrop" onClick={e => { if (e.target === e.currentTarget) setSelected(null); }}>
      <dialog ref={dialogRef} open tabIndex={-1} aria-modal="true" className="bio-dialog" aria-labelledby="bio-detail-title" onCancel={() => setSelected(null)}>
        <div className="bio-dialog-heading"><h2 id="bio-detail-title">{selected.name}</h2><button type="button" onClick={() => setSelected(null)} aria-label="Закрыть" title="Закрыть"><X size={19} /></button></div>
        <dl><dt>Метод / endpoint</dt><dd>{selected.method}</dd><dt>Контекст</dt><dd>{selected.scope}</dd><dt>Статус</dt><dd>{selected.status === "key" ? "Ответы ассистента требуют настроенного ключа API; они не являются прогнозом обученной QSAR-модели." : modelModules.has(selected.id) ? capabilityDescription(capabilityMap.get(selected.id)) : "Обученная модель не подключена. Прогноз для этого направления не рассчитывается."}</dd></dl>
        {capabilityMap.get(selected.id)?.states.map(state => <div className="bio-message" key={state.key}>
          <strong>{state.key}: {capabilityLabels[state.status] ?? state.status}</strong>
          {state.context && <p>{state.context}</p>}
          {state.kind && <p>{state.kind === "regression" ? "Регрессия" : "Классификация"}{state.units && ` · ${state.units}`}</p>}
          {state.message && <p>{state.message}</p>}
        </div>)}
        <div className="bio-dialog-actions">
          {selected.tab && <button type="button" onClick={() => onTab(selected.tab!)}>Открыть раздел <ArrowRight size={15} /></button>}
          {selected.preset && <button className="bio-primary" type="button" onClick={() => onResearch(selected.preset)}>Подготовить задачу <Workflow size={15} /></button>}
          {!!capabilityMap.get(selected.id)?.models_available && <button type="button" onClick={() => onResearch()}>Открыть реестр <Database size={15} /></button>}
          {!selected.tab && !selected.preset && <span>Модуль запланирован; модель и pipeline отсутствуют.</span>}
        </div>
      </dialog>
    </div>}
  </section>;
}
