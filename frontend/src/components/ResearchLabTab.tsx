import { useEffect, useState } from "react";
import { API_ORIGIN } from "../api/base";
import type { ResearchPreset } from "../lib/bioactivity";

type Json = Record<string, any>;

async function request(path: string, body?: unknown): Promise<any> {
  const response = await fetch(`${API_ORIGIN}/api/research${path}`, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
  return data;
}

const QSAR_TASK = {
  name: "QSAR: экспериментальная активность по одной мишени",
  domain: "qsar", kind: "classification", endpoint: "", units: "0/1", context: ""
};

export default function ResearchLabTab({ initialPreset = "default", initialTask }: { initialPreset?: "default" | "qsar"; initialTask?: ResearchPreset }) {
  const [status, setStatus] = useState<Json | null>(null);
  const [config, setConfig] = useState("");
  const [tasks, setTasks] = useState<Json[]>([]);
  const [selected, setSelected] = useState("");
  const [runs, setRuns] = useState<Json[]>([]);
  const [models, setModels] = useState<Json[]>([]);
  const [sources, setSources] = useState<Json[]>([]);
  const [detail, setDetail] = useState<Json | null>(null);
  const [csv, setCsv] = useState("");
  const [provenance, setProvenance] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [reviewer, setReviewer] = useState("");
  const [evidence, setEvidence] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [smiles, setSmiles] = useState("CCO");
  const [prediction, setPrediction] = useState<Json | null>(null);

  async function refresh() {
    const [t, r, m] = await Promise.all([request("/tasks"), request("/runs"), request("/models")]);
    setTasks(t); setRuns(r); setModels(m);
  }
  useEffect(() => {
    let mounted = true;
    request("/status").then(async s => {
      if (!mounted) return;
      setStatus(s); setConfig(JSON.stringify(initialTask ?? (initialPreset === "qsar" ? QSAR_TASK : s.default_task), null, 2));
      if (s.enabled) await refresh();
    }).catch(e => mounted && setError(String(e.message)));
    return () => { mounted = false; };
  }, [initialPreset, initialTask]);
  useEffect(() => {
    if (!status?.enabled) return;
    const timer = window.setInterval(() => refresh().catch(e => setError(String(e.message))), 2000);
    return () => window.clearInterval(timer);
  }, [status?.enabled]);

  async function act(work: () => Promise<void>) {
    setBusy(true); setError(""); setMessage("");
    try { await work(); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  const running = runs.some(r => ["running", "queued"].includes(r.status));

  return <section className="research-lab">
    <h2>AI Research Lab</h2>
    <p>Исследовательские прогнозы требуют экспериментальной проверки. Новые модели сохраняются как experimental.</p>
    {error && <p role="alert" className="research-error">{error}</p>}
    {message && <p role="status">{message}</p>}
    {!status ? <p>Подключение к исследовательскому движку…</p> : !status.enabled ?
      <p>Режим выключен. Для включения установите CHEMANALYZER_RESEARCH_ENABLED=1 в окружении backend и перезапустите приложение. Датасеты автоматически не загружаются.</p> : <>
      <details open={initialTask || initialPreset === "qsar" ? true : undefined}><summary>Создать исследовательскую задачу</summary>
        <div className="research-actions">
          <button disabled={busy} onClick={() => setConfig(JSON.stringify(QSAR_TASK, null, 2))}>QSAR: обучение активности</button>
          <button disabled={busy} onClick={() => setConfig(JSON.stringify(status.default_task, null, 2))}>FreeSolv: гидратация</button>
          {Object.entries(status.cyp_tasks ?? {}).map(([isoform, task]) =>
            <button key={isoform} disabled={busy} onClick={() => setConfig(JSON.stringify(task, null, 2))}>{isoform}: ингибирование</button>)}
          {Object.entries(status.screening_tasks ?? {}).map(([key, task]) =>
            <button key={key} disabled={busy} onClick={() => setConfig(JSON.stringify(task, null, 2))}>{key === "hiv" ? "ВИЧ: NCI" : "HepG2: 24 часа"}</button>)}
        </div>
        <p>Для QSAR заполните endpoint и context: мишень, организм, assay, тип измерения и заранее обоснованное правило меток 0/1. Импортируйте экспериментальный CSV с provenance. Для непрерывных измерений задайте kind: regression и соответствующие units.</p>
        <p>Для классификации требуется минимум 30 уникальных молекул каждого класса и достаточное число scaffold-групп. Обученная в лаборатории модель проходит отдельную проверку и утверждение; её создание не снимает сообщение об отсутствии рабочих QSAR-моделей.</p>
        <p>Укажите один endpoint, единицы и сопоставимые условия. Режимы автоматизации описаны в руководстве.</p>
        <textarea aria-label="Конфигурация задачи JSON" rows={10} value={config} onChange={e => setConfig(e.target.value)} />
        <button disabled={busy} onClick={() => act(async () => {
          const task = await request("/tasks", JSON.parse(config)); setSelected(task.id); setMessage("Задача создана");
        })}>Создать задачу</button>
      </details>
      <label>Исследовательская задача <select value={selected} onChange={e => setSelected(e.target.value)}>
        <option value="">Выберите задачу</option>
        {tasks.map(t => <option key={t.id} value={t.id}>{t.name} · {t.id.slice(0, 8)}</option>)}
      </select></label>
      <div className="research-actions">
        <button disabled={busy || !selected} onClick={() => act(async () => {
          const task = tasks.find(t => t.id === selected);
          const data = await request(`/sources?endpoint=${encodeURIComponent(task?.endpoint || "")}`); setSources(data.sources);
        })}>Найти источники</button>
        <button disabled={busy || !selected} onClick={() => act(async () => {
          const result = await request(`/tasks/${selected}/freesolv`, {});
          setMessage(`FreeSolv импортирован: ${result.measurements} измерений. SHA256 ${result.dataset_sha256}`);
        })}>Импорт FreeSolv</button>
        <button disabled={busy || !selected || !tasks.find(t => t.id === selected)?.endpoint?.match(/^cyp.*_inhibition_veith$/)} onClick={() => act(async () => {
          const result = await request(`/tasks/${selected}/tdc-cyp`, {});
          setMessage(`TDC CYP импортирован: ${result.measurements} исходных записей. SHA256 ${result.dataset_sha256}`);
        })}>Импорт TDC CYP</button>
        {(["hiv", "hepg2"] as const).map(key => <button key={key} disabled={busy || !selected || tasks.find(t => t.id === selected)?.endpoint !== status.screening_tasks?.[key]?.endpoint} onClick={() => act(async () => {
          const result = await request(`/tasks/${selected}/tdc-${key}`, {});
          setMessage(`${key === "hiv" ? "NCI HIV" : "ToxCast HepG2"}: импортировано ${result.measurements} измерений. SHA256 ${result.dataset_sha256}`);
        })}>Импорт {key === "hiv" ? "NCI HIV" : "ToxCast HepG2"}</button>)}
        <button disabled={busy || running || !selected} onClick={() => act(async () => {
          await request(`/tasks/${selected}/prepare`, {}); setMessage("Подготовка запущена в отдельном процессе");
        })}>Подготовить данные</button>
        <button disabled={busy || running || !selected} onClick={() => act(async () => {
          await request(`/tasks/${selected}/train`, {}); setMessage("Обучение запущено в отдельном процессе");
        })}>Обучить и оценить</button>
      </div>
      {sources.length > 0 && <ul>{sources.map(s => <li key={s.id}><a href={s.url} target="_blank" rel="noreferrer">{s.name}</a> · {s.status} · {s.license || "лицензию нужно проверить"}</li>)}</ul>}
      <details><summary>Импорт пользовательского CSV</summary>
        <p>Колонки smiles,value. Отдельный JSON provenance: source_url, doi, license, license_url, source_version, retrieved_at, endpoint, units, context, experimental, curator. Метаданные источника проверяет куратор. Файлы остаются локально.</p>
        <label>CSV <input type="file" accept=".csv" onChange={e => {
          const file = e.target.files?.[0];
          if (file && file.size <= 8000000) file.text().then(setCsv).catch(e => setError(String(e)));
          else if (file) setError("CSV превышает 8 MB");
        }} /></label>
        <label>Provenance JSON <input type="file" accept=".json" onChange={e => {
          const file = e.target.files?.[0];
          if (file && file.size <= 16000) file.text().then(setProvenance).catch(e => setError(String(e)));
          else if (file) setError("JSON превышает 16 KB");
        }} /></label>
        <button disabled={busy || !selected || !csv || !provenance} onClick={() => act(async () => {
          const result = await request(`/tasks/${selected}/import`, { csv_text: csv, provenance: JSON.parse(provenance) });
          setMessage(`Импортировано ${result.measurements} измерений`);
        })}>Проверить и импортировать</button>
      </details>
      <h3>История экспериментов</h3>
      {runs.length === 0 && <p>Запусков пока нет.</p>}
      {runs.map(r => <article key={r.id}>
        <strong>{r.id.slice(0, 8)}</strong> · {r.status} · {r.stage}
        {r.error && <p role="alert">{r.error}</p>}
        <button disabled={busy} onClick={() => act(async () => setDetail(await request(`/runs/${r.id}`)))}>Результаты и ошибки</button>
        {["running", "queued"].includes(r.status) && <button disabled={busy} onClick={() => act(async () => { await request(`/runs/${r.id}/cancel`, {}); })}>Отменить</button>}
      </article>)}
      {detail && <details open><summary>Отчёт эксперимента</summary><pre>{JSON.stringify(detail, null, 2)}</pre></details>}
      <h3>Сравнение моделей</h3>
      <p>CV и validation выбирают алгоритм; test используется после выбора. Показатели разных endpoint и датасетов не сопоставимы напрямую.</p>
      <label>Рецензент <input value={reviewer} onChange={e => setReviewer(e.target.value)} /></label>
      <label>Документированная независимая проверка <textarea rows={3} value={evidence} onChange={e => setEvidence(e.target.value)} /></label>
      <label><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Подтверждаю активацию выбранной модели в исследовательском реестре</label>
      <label>SMILES для исследовательского прогноза <input value={smiles} onChange={e => setSmiles(e.target.value)} /></label>
      {models.map(m => <article key={m.id}>
        <strong>{m.task.name}</strong> · {m.status} · {m.evaluation.selected} · {m.id.slice(0, 8)}
        <p>Test: {JSON.stringify(m.evaluation.test)} · Baseline: {JSON.stringify(m.evaluation.baseline_test)}</p>
        <p>{m.quality?.passed ? "Порог качества пройден" : "Порог качества не пройден"}
          {" · "}{m.quality?.metric}: {m.quality?.value ?? "нет оценки"}
          {m.quality?.metric === "r2" ? " · R² не является процентом точности" : " · Требуется сбалансированная точность > 60%"}
        </p>
        {m.quality?.reasons?.length > 0 && <p>{m.quality.reasons.join("; ")}</p>}
        <button disabled={busy || !m.quality?.passed} onClick={() => act(async () => { setPrediction(await request(`/models/${m.id}/predict`, { smiles })); })}>Исследовательский прогноз</button>
        {m.status === "experimental" && <button disabled={busy || !m.quality?.passed || reviewer.length < 3 || evidence.length < 30} onClick={() => act(async () => {
          await request(`/models/${m.id}/review`, { reviewer, evidence });
        })}>Сохранить рецензию</button>}
        {m.status === "validated" && <button disabled={busy || !m.quality?.passed || !confirmed || reviewer.length < 3 || evidence.length < 30} onClick={() => act(async () => {
          await request(`/models/${m.id}/approve`, { reviewer, evidence, confirm_activation: confirmed }); setConfirmed(false);
        })}>Утвердить эту модель</button>}
      </article>)}
      {prediction && <pre role="status">{JSON.stringify(prediction, null, 2)}</pre>}
    </>}
  </section>;
}
