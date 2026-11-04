"use strict";
/**
 * Чистые функции безопасности (без зависимостей от Electron — их можно тестировать).
 */
const path = require("node:path");

// Внешние сайты, которые разрешено открывать в браузере по умолчанию.
const EXTERNAL_HOSTS = new Set([
  "pubchem.ncbi.nlm.nih.gov",
  "www.ebi.ac.uk",
  "github.com",
  "zenodo.org",
  "alphafold.ebi.ac.uk",
  "www.rcsb.org",
  "console.anthropic.com",
  "docs.claude.com",
]);

function isAllowedExternalUrl(raw) {
  try {
    const url = new URL(String(raw));
    return (
      url.protocol === "https:" &&
      !url.username &&
      !url.password &&
      EXTERNAL_HOSTS.has(url.hostname)
    );
  } catch {
    return false;
  }
}

/**
 * Content-Security-Policy для окна приложения.
 * 'wasm-unsafe-eval' нужен WASM-движку Ketcher (Indigo).
 * relaxed=true добавляет 'unsafe-eval' — запасной вариант, если Ketcher
 * в упакованной сборке не стартует из-за CSP (см. DESKTOP_BUILD_GUIDE.md).
 */
function buildCsp({ relaxed = false } = {}) {
  const script = ["'self'", "'wasm-unsafe-eval'"];
  if (relaxed) script.push("'unsafe-eval'");
  return [
    "default-src 'self'",
    `script-src ${script.join(" ")}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

const ALLOWED_EXTENSIONS = new Set([
  ".smi", ".json", ".csv", ".svg", ".png", ".pdf",
  ".sdf", ".mol", ".pdb", ".cif", ".txt",
]);

const RESERVED = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i;

/** Безопасное имя файла: без путей, управляющих символов и зарезервированных имён Windows. */
function sanitizeFileName(name, fallbackBase = "chemanalyzer") {
  const raw = path.basename(String(name || "").replace(/\\/g, "/"));
  let ext = path.extname(raw).toLowerCase();
  let base = raw.slice(0, raw.length - ext.length);

  base = base
    // eslint-disable-next-line no-control-regex
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_")
    .replace(/[. ]+$/g, "")
    .trim()
    .slice(0, 100);

  if (!base || RESERVED.test(base)) base = fallbackBase;
  if (!ALLOWED_EXTENSIONS.has(ext)) ext = ".txt";
  return base + ext;
}

function isAllowedExtension(name) {
  return ALLOWED_EXTENSIONS.has(path.extname(String(name || "")).toLowerCase());
}

module.exports = {
  EXTERNAL_HOSTS,
  ALLOWED_EXTENSIONS,
  isAllowedExternalUrl,
  buildCsp,
  sanitizeFileName,
  isAllowedExtension,
};
