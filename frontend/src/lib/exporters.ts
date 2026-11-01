import { bridge } from "./desktop";
import {
  VERDICT_LABEL,
  evaluateCriteria,
  qedVerdict,
  summarizeLipinski,
  DRUGLIKE_DISCLAIMER
} from "./druglike";
import type {
  ActivityResponse,
  AdmeResponse,
  ChemblResponse,
  IdentificationResult,
  MoleculeResponse
} from "../types/molecule";

// ---------------------------------------------------------------- текст

export function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Ячейка CSV. Строки, начинающиеся с = + - @ (формулы Excel), экранируются
 * апострофом — защита от CSV-инъекций через данные внешних баз. Числа не трогаем.
 */
export function csvCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "";
  if (typeof value === "boolean") return value ? "true" : "false";

  let text = String(value);
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[",\r\n;]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function buildCsv(
  result: MoleculeResponse,
  identification: IdentificationResult | null,
  qed: number | null
): string {
  const lip = summarizeLipinski(evaluateCriteria(result));
  const columns: Array<[string, unknown]> = [
    ["input_smiles", result.input_smiles],
    ["canonical_smiles", result.canonical_smiles],
    ["formula", result.formula],
    ["molecular_weight", result.molecular_weight],
    ["logp", result.logp],
    ["tpsa", result.tpsa],
    ["hbd", result.hbd],
    ["hba", result.hba],
    ["rotatable_bonds", result.rotatable_bonds],
    ["rings", result.rings],
    ["heavy_atoms", result.heavy_atoms],
    ["aromatic_atoms", result.aromatic_atoms],
    ["atom_count", result.atom_count],
    ["bond_count", result.bond_count],
    ["lipinski_violations", lip.violations],
    ["lipinski_verdict", VERDICT_LABEL[lip.verdict]],
    ["qed", qed],
    ["identification_status", identification?.status ?? ""],
    ["identification_match", identification?.match_type ?? ""],
    ["pubchem_cid", identification?.match_type === "exact" ? identification.cid : ""],
    ["pubchem_title", identification?.match_type === "exact" ? identification.title : ""],
    ["pubchem_inchikey", identification?.match_type === "exact" ? identification.inchikey : ""],
    ["pubchem_candidate_cid", identification?.match_type === "connectivity" ? identification.cid : ""],
    ["pubchem_candidate_title", identification?.match_type === "connectivity" ? identification.title : ""],
    ["pubchem_candidate_inchikey", identification?.match_type === "connectivity" ? identification.inchikey : ""]
  ];

  const header = columns.map(([name]) => csvCell(name)).join(",");
  const row = columns.map(([, value]) => csvCell(value)).join(",");
  // BOM — чтобы Excel правильно открыл кириллицу в UTF-8.
  return `\ufeff${header}\r\n${row}\r\n`;
}

// ---------------------------------------------------------------- отчёт

export interface ReportData {
  generatedAt: Date;
  appVersion: string;
  result: MoleculeResponse;
  svg: string | null;
  identification: IdentificationResult | null;
  activity: ActivityResponse | null;
  chembl: ChemblResponse | null;
  adme?: AdmeResponse | null;
}

function utf8Base64(text: string): string {
  return btoa(unescape(encodeURIComponent(text)));
}

function reportTitle(id: IdentificationResult | null): string {
  if (id?.found && id.title) {
    return id.match_type === "connectivity"
      ? `${id.title} (совпадение только по связности)`
      : id.title;
  }
  if (id?.status === "unavailable") return "Название не определено (PubChem недоступен)";
  return "Название не определено (структура не подтверждена PubChem)";
}

function row(label: string, value: unknown): string {
  return `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(value)}</td></tr>`;
}

export function buildReportHtml(d: ReportData): string {
  const r = d.result;
  const id = d.identification;
  const criteria = evaluateCriteria(r);
  const lip = summarizeLipinski(criteria);
  const qed = d.activity?.druglikeness.qed ?? null;

  // Изображение вставляется как <img data:...>: так даже "вредный" SVG не
  // сможет выполнить скрипт, а отчёт печатается в окне без JavaScript.
  const picture = d.svg
    ? `<img class="mol" alt="Структура" src="data:image/svg+xml;base64,${utf8Base64(d.svg)}" />`
    : `<p class="muted">Изображение структуры недоступно.</p>`;

  const criteriaRows = criteria
    .map(
      (c) =>
        `<tr><td>${escapeHtml(c.label)}</td><td>${escapeHtml(c.value)}</td>` +
        `<td>≤ ${escapeHtml(c.limit)} (${escapeHtml(c.rule)})</td>` +
        `<td class="v-${c.verdict}">${VERDICT_LABEL[c.verdict]}</td></tr>`
    )
    .join("");

  const idRows = id
    ? [
        row("Статус", id.status === "found" ? "Найдено в PubChem" : id.status === "unavailable" ? "PubChem недоступен" : "Точное соединение не найдено"),
        row("Тип совпадения", id.match_type === "exact" ? "точное (с учётом стереохимии)" : id.match_type === "connectivity" ? "только по связности" : "—"),
        row(id.match_type === "connectivity" ? "CID кандидата" : "CID", id.cid ?? "—"),
        row(id.match_type === "connectivity" ? "IUPAC кандидата (не подтверждён)" : "IUPAC", id.iupac_name ?? "—"),
        row(id.match_type === "connectivity" ? "InChIKey кандидата" : "InChIKey", id.inchikey ?? "—")
      ].join("")
    : row("Статус", "идентификация не выполнялась");

  const similar =
    id && id.similar.length > 0
      ? `<p class="muted">Похожие вещества (не то же самое соединение): ${id.similar
          .map((s) => escapeHtml(`${s.title ?? "без названия"} (CID ${s.cid})`))
          .join("; ")}.</p>`
      : "";

  const chembl = d.chembl;
  const chemblBlock = chembl?.found
    ? `<table>${row("ChEMBL ID", chembl.chembl_id)}${row("Название", chembl.name ?? "—")}${row(
        "Механизмы",
        chembl.mechanisms.map((m) => m.action).filter(Boolean).join("; ") || "—"
      )}${row(
        "Показания",
        chembl.indications.map((i) => i.name).join("; ") || "—"
      )}</table>`
    : `<p class="muted">${escapeHtml(
        chembl?.message ?? "Экспериментальные данные не найдены."
      )}</p>`;

  return `<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>ChemAnalyzer — отчёт</title>
<style>
  @page { size: A4; margin: 16mm; }
  body { font-family: "Segoe UI", Arial, sans-serif; color: #14233a; font-size: 11pt; }
  h1 { font-size: 20pt; margin: 0 0 2pt; }
  h2 { font-size: 13pt; margin: 18pt 0 6pt; border-bottom: 1px solid #c9d4e2; padding-bottom: 3pt; }
  .sub { color: #566a82; margin: 0 0 10pt; }
  code { font-family: Consolas, monospace; font-size: 9.5pt; word-break: break-all; }
  table { border-collapse: collapse; width: 100%; }
  th, td { text-align: left; padding: 3pt 6pt; border-bottom: 1px solid #e3e9f1; vertical-align: top; }
  th { width: 34%; color: #566a82; font-weight: 600; }
  .mol { max-width: 100%; height: auto; border: 1px solid #e3e9f1; }
  .muted { color: #566a82; }
  .v-pass { color: #0f7b3d; font-weight: 700; }
  .v-warn { color: #a36a00; font-weight: 700; }
  .v-fail { color: #b3261e; font-weight: 700; }
  .note { margin-top: 18pt; padding: 8pt 10pt; background: #f1f5fa; font-size: 9.5pt; color: #33475f; }
</style></head><body>
<h1>${escapeHtml(reportTitle(id))}</h1>
<p class="sub">${escapeHtml(r.formula)} · ChemAnalyzer ${escapeHtml(d.appVersion)} · ${escapeHtml(d.generatedAt.toLocaleString("ru-RU"))}</p>

<h2>Структура</h2>
${picture}
<p><strong>SMILES:</strong> <code>${escapeHtml(r.canonical_smiles)}</code></p>

<h2>Основные свойства</h2>
<table>
${row("Молекулярная масса", r.molecular_weight)}
${row("LogP (Crippen)", r.logp)}
${row("TPSA, Å²", r.tpsa)}
${row("HBD / HBA", `${r.hbd} / ${r.hba}`)}
${row("Вращаемые связи", r.rotatable_bonds)}
${row("Кольца", r.rings)}
${row("Тяжёлые атомы", r.heavy_atoms)}
${row("Ароматические атомы", r.aromatic_atoms)}
${row("Атомов (без H) / связей", `${r.atom_count} / ${r.bond_count}`)}
</table>

${d.adme ? `<h2>ADME (BOILED-Egg)</h2>
<table>
${row("Всасывание в ЖКТ", d.adme.pharmacokinetics.gi_absorption)}
${row("Проникновение через ГЭБ", d.adme.pharmacokinetics.bbb_permeant)}
${row("Растворимость ESOL (log S)", `${d.adme.solubility.esol_logs} — ${d.adme.solubility.esol_class}`)}
${row("WLOGP / TPSA (S и P учтены)", `${d.adme.boiled_egg.wlogp} / ${d.adme.boiled_egg.tpsa}`)}
</table>
<p class="muted">Модель BOILED-Egg: Daina &amp; Zoete, ChemMedChem 2016. P-gp и CYP не рассчитываются.</p>` : ""}

<h2>Drug-likeness</h2>
<table>
<tr><th>Показатель</th><th>Значение</th><th>Предел</th><th>Оценка</th></tr>
${criteriaRows}
</table>
<p><strong>Правило Липински:</strong> <span class="v-${lip.verdict}">${VERDICT_LABEL[lip.verdict]}</span> — ${escapeHtml(lip.text)}
${qed !== null ? `<br><strong>QED:</strong> ${escapeHtml(qed)} (<span class="v-${qedVerdict(qed)}">${VERDICT_LABEL[qedVerdict(qed)]}</span>)` : ""}</p>

<h2>Идентификация (PubChem)</h2>
<table>${idRows}</table>
${similar}

<h2>ChEMBL</h2>
${chemblBlock}

<h2>Источники данных</h2>
<ul class="muted">
  <li>Дескрипторы и 2D/3D: RDKit (расчёт, локально)</li>
  <li>Идентификация: PubChem (NCBI)${id?.source_url ? ` — ${escapeHtml(id.source_url)}` : ""}</li>
  <li>Экспериментальные данные: ChEMBL (EMBL-EBI)${chembl?.source_url ? ` — ${escapeHtml(chembl.source_url)}` : ""}</li>
</ul>

<div class="note">${escapeHtml(DRUGLIKE_DISCLAIMER)} Расчётные значения и прогнозы
требуют экспериментальной проверки. Название присвоено только при подтверждении
внешней базой; «похожее вещество» — не то же самое вещество.</div>
</body></html>`;
}

// ---------------------------------------------------------------- сохранение

function browserDownload(name: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
    reader.onerror = () => reject(new Error("Не удалось прочитать данные."));
    reader.readAsDataURL(blob);
  });
}

export interface SaveOutcome {
  ok: boolean;
  canceled?: boolean;
  path?: string;
  message?: string;
}

/** Сохранение текстового файла: диалог Windows в desktop, скачивание в браузере. */
export async function saveText(name: string, text: string, mime = "text/plain"): Promise<SaveOutcome> {
  if (bridge) {
    const r = await bridge.saveFile({ name, text });
    return { ok: r.saved, canceled: r.canceled, path: r.path, message: r.error };
  }
  browserDownload(name, new Blob([text], { type: `${mime};charset=utf-8` }));
  return { ok: true };
}

export async function saveBlob(name: string, blob: Blob): Promise<SaveOutcome> {
  if (bridge) {
    const r = await bridge.saveFile({ name, base64: await blobToBase64(blob) });
    return { ok: r.saved, canceled: r.canceled, path: r.path, message: r.error };
  }
  browserDownload(name, blob);
  return { ok: true };
}

function svgSize(svg: string): { w: number; h: number } {
  const w = /width=['"]([\d.]+)/.exec(svg);
  const h = /height=['"]([\d.]+)/.exec(svg);
  return { w: w ? parseFloat(w[1]) : 520, h: h ? parseFloat(h[1]) : 380 };
}

/** SVG -> PNG (в 2 раза крупнее, на белом фоне). */
export function svgToPng(svg: string, scale = 2): Promise<Blob> {
  const { w, h } = svgSize(svg);
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(w * scale);
      canvas.height = Math.round(h * scale);
      const ctx = canvas.getContext("2d");
      if (!ctx) return reject(new Error("Canvas недоступен."));
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error("Не удалось создать PNG."))),
        "image/png"
      );
    };
    image.onerror = () => reject(new Error("Не удалось отрисовать изображение."));
    image.src = `data:image/svg+xml;base64,${utf8Base64(svg)}`;
  });
}

export async function savePdfReport(name: string, html: string): Promise<SaveOutcome> {
  if (bridge) {
    const r = await bridge.exportPdf({ html, name });
    return { ok: r.saved, canceled: r.canceled, path: r.path, message: r.error };
  }
  // Браузер: открываем отчёт и вызываем печать («Сохранить как PDF»).
  const url = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
  const win = window.open(url, "_blank");
  if (!win) {
    URL.revokeObjectURL(url);
    return { ok: false, message: "Браузер заблокировал окно печати." };
  }
  win.addEventListener("load", () => win.print());
  return { ok: true };
}
