import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, ArrowDownToLine, ArrowRight, Atom, BookOpen, Database, FlaskConical, RefreshCw, Search, Workflow, X } from "lucide-react";
import { BIO_GROUPS, BIO_MODULES, type BioGroup, type BioModule, type ResearchPreset } from "../lib/bioactivity";
import { API_ORIGIN } from "../api/base";
import { saveText } from "../lib/exporters";
import type { Tab } from "./ResultsPanel";
import type { ActivityResponse, AsyncState } from "../types/molecule";
import iconUrl from "../../../assets/icon.png";

type AgentModel = { id: string; task: { endpoint: string; name: string }; status: string;
  quality?: { passed: boolean; metric: string; value: number | null; reasons: string[] } };
type AgentSummary = { enabled: boolean; models: AgentModel[]; error: string };
const groupIcons = { pharmacology: Activity, admet: FlaskConical, science: BookOpen, sources: Database };
const statusNames = { calculation: "Доступен расчёт", qsar: "Локальные модели", dataset: "Нужны данные", key: "API-ассистент", source: "Внешний источник" };

export default function BioactivityWorkspace({ onTab, onResearch, activity, hasMolecule }: {
  onTab: (tab: Tab) => void; onResearch: (preset?: ResearchPreset) => void;
  activity: AsyncState<ActivityResponse>; hasMolecule: boolean;
}) {
  const [category, setCategory] = useState<BioGroup | "all">("all");
  const [query, setQuery] = useState("");
  const [onlyReady, setOnlyReady] = useState(false);
  const [agent, setAgent] = useState<AgentSummary>({ enabled: false, models: [], error: "" });
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
    (async () => {
      const response = await fetch(`${API_ORIGIN}/api/research/status`, { signal: controller.signal });
      if (!response.ok) throw new Error("Не удалось получить статус исследовательского агента");
      const status: { enabled: boolean } = await response.json();
      let models: AgentModel[] = [];
      if (status.enabled) {
        const result = await fetch(`${API_ORIGIN}/api/research/models`, { signal: controller.signal });
        if (!result.ok) throw new Error("Реестр моделей недоступен");
        models = await result.json();
      }
      if (!controller.signal.aborted) setAgent({ enabled: status.enabled, models, error: "" });
    })().catch(error => {
      if (!controller.signal.aborted) setAgent({ enabled: false, models: [], error: String(error.message) });
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [refreshKey]);

  const filtered = useMemo(() => BIO_MODULES.filter(item => {
    const text = `${item.name} ${item.method} ${item.scope}`.toLocaleLowerCase("ru");
    return (category === "all" || item.group === category) && text.includes(query.trim().toLocaleLowerCase("ru"))
      && (!onlyReady || ["calculation", "source"].includes(item.status) || (item.status === "qsar" && activity.data?.qsar.status === "ready")
        || (item.id === "cyp" && matchingModels(item).some(model => model.quality?.passed)));
  }), [query, category, onlyReady, activity.data, agent.models]);
  const localCount = activity.data?.qsar.models_loaded;
  const liveModels = agent.models.filter(model => model.status === "approved" && model.quality?.passed);
  function matchingModels(item: BioModule) {
    if (item.id === "cyp") return agent.models.filter(model => model.status !== "archived" && /^cyp(?:1a2|2c9|2c19|2d6|3a4)_inhibition_veith$/.test(model.task?.endpoint ?? ""));
    return item.preset ? agent.models.filter(model => model.task?.endpoint === item.preset?.endpoint) : [];
  }

  function open(item: BioModule) {
    if (item.id === "cyp" && item.tab) { onTab(item.tab); return; }
    if (item.status === "dataset" || item.status === "key") { setSelected(item); return; }
    if (item.tab) onTab(item.tab);
  }

  async function exportRegistry() {
    try {
      const outcome = await saveText("ChemAnalyzer-bioactivity.json", JSON.stringify({ exported_at: new Date().toISOString(), modules: BIO_MODULES,
        agent_enabled: agent.enabled, research_models: agent.models, local_qsar: activity.data?.qsar ?? null }, null, 2));
      setNotice(outcome.ok ? "Реестр сохранён" : outcome.canceled ? "Экспорт отменён" : "Не удалось сохранить реестр");
    } catch { setNotice("Не удалось сохранить реестр"); }
  }

  return <section className="bio-workspace" aria-labelledby="bio-title">
    <header className="bio-heading">
      <div className="bio-title"><img src={iconUrl} alt="" width="42" height="42" /><div><span className="bio-eyebrow">CHEMANALYZER / RESEARCH WORKSPACE</span><h1 id="bio-title">Биоактивность</h1></div></div>
      <button className="bio-primary" type="button" onClick={() => onResearch()}><Workflow size={16} /> AI Research Lab <ArrowRight size={15} /></button>
    </header>
    <div className="bio-summary" aria-label="Состояние моделей">
      <div><strong>{BIO_MODULES.length}</strong><span>модуль исследования</span></div>
      <div><strong>{localCount ?? "—"}</strong><span>QSAR в текущем анализе</span></div>
      <div><strong>{loading ? "…" : agent.models.length}</strong><span>моделей в реестре агента</span></div>
      <div><strong>{loading ? "…" : liveModels.length}</strong><span>утверждено в реестре</span></div>
      <span className={`bio-agent-state ${agent.enabled ? "online" : ""}`}><i />{loading ? "Проверка агента" : agent.error ? "Нет связи с агентом" : agent.enabled ? "Агент подключён" : "Агент выключен"}</span>
    </div>
    {agent.error && <div className="bio-message" role="alert">{agent.error}</div>}
    <div className="bio-message">
      Допуск прогнозных моделей: сбалансированная точность &gt; 60% на отложенных структурах;
      для регрессии — R² &gt; 0,60 и ошибка ниже базовой модели.
      R², вероятность активности и сходство структуры — разные показатели.
      Наличие раздела в каталоге не означает, что его модель обучена.
    </div>
    {!hasMolecule && <div className="bio-context"><Atom size={16} /><span>Структура не выбрана</span><button type="button" onClick={() => onTab("props")}>Открыть редактор <ArrowRight size={14} /></button></div>}
    <div className="bio-filterbar">
      <label className="bio-search"><Search size={16} /><input aria-label="Поиск модулей биоактивности" placeholder="Найти модуль, мишень или метод…" value={query} onChange={e => setQuery(e.target.value)} /></label>
      <label className="bio-ready"><input type="checkbox" checked={onlyReady} onChange={e => setOnlyReady(e.target.checked)} />Доступные</label>
      <button className="bio-icon" type="button" title="Обновить реестр" aria-label="Обновить реестр" disabled={loading} onClick={() => setRefreshKey(x => x + 1)}><RefreshCw size={16} /></button>
      <button className="bio-icon" type="button" title="Экспорт реестра JSON" aria-label="Экспорт реестра JSON" onClick={exportRegistry}><ArrowDownToLine size={16} /></button>
    </div>
    <div className="bio-categories" role="tablist" aria-label="Направления биоактивности">
      {[{ id: "all" as const, name: "Все направления" }, ...BIO_GROUPS].map(group => <button key={group.id} type="button" role="tab" aria-selected={category === group.id} onClick={() => setCategory(group.id)}>{group.name}<span>{group.id === "all" ? BIO_MODULES.length : BIO_MODULES.filter(item => item.group === group.id).length}</span></button>)}
    </div>
    {BIO_GROUPS.map(group => {
      const entries = filtered.filter(item => item.group === group.id);
      const Icon = groupIcons[group.id];
      return entries.length > 0 && <section className={`bio-band bio-band-${group.id}`} key={group.id} aria-labelledby={`bio-${group.id}`}>
        <div className="bio-band-heading"><Icon size={18} /><h2 id={`bio-${group.id}`}>{group.name}</h2><span>{entries.length.toString().padStart(2, "0")}</span></div>
        <div className="bio-grid">{entries.map(item => <button key={item.id} type="button" className="bio-module" onClick={() => open(item)} aria-label={`Открыть: ${item.name}`}>
          <div className="bio-module-top"><Icon size={20} /><span className={`bio-badge bio-badge-${item.status}`}>{matchingModels(item).length ? `В реестре: ${matchingModels(item).length}` : item.status === "qsar" && localCount === 0 ? "Нет локальных моделей" : statusNames[item.status]}</span></div>
          <h3>{item.name}</h3><p>{item.method}</p><div className="bio-module-bottom"><span>{item.scope}</span><ArrowRight size={16} /></div>
        </button>)}</div>
      </section>;
    })}
    {filtered.length === 0 && <div className="bio-empty"><Search size={24} /><h2>Модули не найдены</h2><button type="button" onClick={() => { setQuery(""); setCategory("all"); setOnlyReady(false); }}>Сбросить фильтры</button></div>}
    {notice && <div className="bio-message" role="status">{notice}</div>}
    <footer className="bio-footnote">Исследовательские оценки. Наличие модуля не означает наличие обученной модели. Экспериментальная проверка обязательна.</footer>
    {selected && <div className="bio-modal-backdrop" onClick={e => { if (e.target === e.currentTarget) setSelected(null); }}>
      <dialog ref={dialogRef} open tabIndex={-1} aria-modal="true" className="bio-dialog" aria-labelledby="bio-detail-title" onCancel={() => setSelected(null)}>
        <div className="bio-dialog-heading"><h2 id="bio-detail-title">{selected.name}</h2><button type="button" onClick={() => setSelected(null)} aria-label="Закрыть" title="Закрыть"><X size={19} /></button></div>
        <dl><dt>Метод / endpoint</dt><dd>{selected.method}</dd><dt>Контекст</dt><dd>{selected.scope}</dd><dt>Статус</dt><dd>{selected.status === "key" ? "Ответы ассистента требуют настроенного ключа API; они не являются прогнозом обученной QSAR-модели." : matchingModels(selected).length ? "В реестре есть модели этого endpoint. Статус, контекст и метрики каждой модели указаны в AI Research Lab; наличие артефакта не означает независимую валидацию." : "Обученная модель не подключена. Прогноз для этого направления не рассчитывается."}</dd></dl>
        <div className="bio-dialog-actions">
          {selected.tab && <button type="button" onClick={() => onTab(selected.tab!)}>Открыть раздел <ArrowRight size={15} /></button>}
          {selected.preset && <button className="bio-primary" type="button" onClick={() => onResearch(selected.preset)}>Подготовить задачу <Workflow size={15} /></button>}
          {matchingModels(selected).length > 0 && <button type="button" onClick={() => onResearch()}>Открыть реестр <Database size={15} /></button>}
          {!selected.tab && !selected.preset && <span>Модуль запланирован; модель и pipeline отсутствуют.</span>}
        </div>
      </dialog>
    </div>}
  </section>;
}
