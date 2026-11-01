"use strict";
/**
 * Режим разработки: Vite (hot reload) + Electron, который сам запускает backend.
 *   npm run dev
 * Переменные: CHEMANALYZER_PYTHON — путь к python из venv backend.
 */
const { spawn } = require("node:child_process");
const http = require("node:http");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const isWin = process.platform === "win32";
const npm = isWin ? "npm.cmd" : "npm";
const VITE_URL = "http://localhost:5173";
const children = [];

function run(cmd, args, options = {}) {
  const child = spawn(cmd, args, { stdio: "inherit", shell: isWin, ...options });
  children.push(child);
  return child;
}

function waitFor(url, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const tick = () => {
      http
        .get(url, (res) => { res.resume(); resolve(); })
        .on("error", () => {
          if (Date.now() > deadline) reject(new Error(`Не дождались ${url}`));
          else setTimeout(tick, 400);
        });
    };
    tick();
  });
}

function shutdown() {
  for (const child of children) {
    try { child.kill(); } catch { /* уже завершён */ }
  }
}
process.on("SIGINT", () => { shutdown(); process.exit(0); });
process.on("exit", shutdown);

(async () => {
  run(npm, ["--prefix", "frontend", "run", "dev", "--", "--port", "5173", "--strictPort"], { cwd: root });
  await waitFor(VITE_URL);
  const electron = require("electron");
  const app = run(electron, ["."], {
    cwd: root,
    shell: false,
    env: { ...process.env, CHEMANALYZER_DEV_URL: VITE_URL },
  });
  app.on("exit", (code) => { shutdown(); process.exit(code ?? 0); });
})().catch((error) => {
  console.error(error.message);
  shutdown();
  process.exit(1);
});
