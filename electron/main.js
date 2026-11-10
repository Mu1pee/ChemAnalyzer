"use strict";
/**
 * ChemAnalyzer — главный процесс Electron.
 *
 * Схема запуска:
 *   найти свободный порт -> запустить Python-backend -> дождаться /health
 *   -> открыть окно с интерфейсом, который отдаёт сам backend (тот же origin).
 *
 * Безопасность: contextIsolation, sandbox, без nodeIntegration, CSP,
 * запрет навигации и window.open на чужие адреса, белый список внешних
 * сайтов, проверка отправителя IPC.
 */
const { app, BrowserWindow, ipcMain, dialog, shell, session, Menu } = require("electron");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const { BackendManager } = require("./backend");
const security = require("./security");
const { createStore } = require("./store");
const { seedResearchData } = require("./research-seed");
const RESEARCH_BUNDLE = require("../package.json").chemanalyzerResearchBundle === true;

const ROOT = path.resolve(__dirname, "..");
const DEV_URL = process.env.CHEMANALYZER_DEV_URL || ""; // например http://localhost:5173
const IS_DEV = !app.isPackaged && Boolean(DEV_URL);
const DEVTOOLS = IS_DEV || process.env.CHEMANALYZER_DEVTOOLS === "1";

let mainWindow = null;
let backend = null;
let origin = null;
let quitting = false;

// ---------------------------------------------------------------- пути

function dataDir() {
  return app.getPath("userData");
}

function backendLaunch() {
  if (app.isPackaged) {
    const exe = path.join(process.resourcesPath, "backend", "chemanalyzer-backend.exe");
    return {
      command: exe,
      buildArgs: (port) => ["--port", String(port)],
      cwd: path.dirname(exe),
      frontendDist: path.join(process.resourcesPath, "frontend"),
    };
  }
  // Режим разработки: backend запускается из исходников.
  const python = process.env.CHEMANALYZER_PYTHON || "python";
  const backendDir = path.join(ROOT, "backend");
  return {
    command: python,
    buildArgs: (port) => [path.join(backendDir, "chemanalyzer_server.py"), "--port", String(port)],
    cwd: backendDir,
    frontendDist: path.join(ROOT, "frontend", "dist"),
  };
}

function ensureDataFiles() {
  const dir = dataDir();
  fs.mkdirSync(path.join(dir, "models"), { recursive: true });
  fs.mkdirSync(path.join(dir, "logs"), { recursive: true });
  if (app.isPackaged && RESEARCH_BUNDLE) {
    seedResearchData(path.join(process.resourcesPath, "research-seed"), dir);
  }

  const envFile = path.join(dir, ".env");
  if (!fs.existsSync(envFile)) {
    fs.writeFileSync(
      envFile,
      [
        "# Секреты ChemAnalyzer. Файл читает только локальный backend.",
        "# Ключ создаётся на https://console.anthropic.com",
        "ANTHROPIC_API_KEY=",
        "# CLAUDE_MODEL=claude-sonnet-5-5",
        "",
      ].join("\n"),
      "utf8"
    );
  }
}

// ---------------------------------------------------------------- backend

async function startBackend() {
  const launch = backendLaunch();
  const logFile = path.join(dataDir(), "logs", "backend.log");
  const log = fs.createWriteStream(logFile, { flags: "w" });

  backend = new BackendManager({
    command: launch.command,
    buildArgs: launch.buildArgs,
    cwd: launch.cwd,
    env: {
      CHEMANALYZER_DESKTOP: DEV_URL ? "0" : "1",
      CHEMANALYZER_DATA_DIR: dataDir(),
      CHEMANALYZER_FRONTEND_DIST: DEV_URL ? "" : launch.frontendDist,
      CHEMANALYZER_RESEARCH_ENABLED: process.env.CHEMANALYZER_RESEARCH_ENABLED ?? (RESEARCH_BUNDLE ? "1" : "0"),
      PYTHONUNBUFFERED: "1",
      PYTHONIOENCODING: "utf-8",
    },
    onLog: (chunk) => log.write(chunk),
    healthTimeoutMs: 120000, // первый запуск RDKit/sklearn может быть медленным
  });

  const { origin: backendOrigin } = await backend.start();
  return backendOrigin;
}

// ---------------------------------------------------------------- окно

function isTrusted(event) {
  try {
    const url = event.senderFrame ? event.senderFrame.url : event.sender.getURL();
    return Boolean(origin) && (url === origin || url.startsWith(`${origin}/`) ||
      (DEV_URL && url.startsWith(DEV_URL)));
  } catch {
    return false;
  }
}

function openExternalSafe(url) {
  if (security.isAllowedExternalUrl(url)) {
    shell.openExternal(url);
    return true;
  }
  return false;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1480,
    height: 920,
    minWidth: 1100,
    minHeight: 700,
    show: false,
    backgroundColor: "#07101c",
    title: "ChemAnalyzer",
    icon: path.join(ROOT, "assets", "icon.png"),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      devTools: DEVTOOLS,
      spellcheck: false,
      additionalArguments: [`--api-origin=${origin || ""}`],
    },
  });

  mainWindow.once("ready-to-show", () => mainWindow.show());

  // Никаких переходов на сторонние адреса внутри приложения.
  mainWindow.webContents.on("will-navigate", (event, url) => {
    const inApp = (origin && url.startsWith(origin)) || (DEV_URL && url.startsWith(DEV_URL));
    if (!inApp) {
      event.preventDefault();
      openExternalSafe(url);
    }
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    openExternalSafe(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  return mainWindow;
}

function setupSession() {
  const ses = session.defaultSession;
  const csp = security.buildCsp({ relaxed: process.env.CHEMANALYZER_RELAXED_CSP === "1" });

  ses.webRequest.onHeadersReceived((details, callback) => {
    const headers = { ...details.responseHeaders };
    if (!DEV_URL && details.url.startsWith(origin || "\0")) {
      headers["Content-Security-Policy"] = [csp];
    }
    callback({ responseHeaders: headers });
  });

  // Разрешаем только то, что реально нужно интерфейсу. Чтение буфера обмена нужно
  // Ketcher (кнопка «Вставить» структуру из другого приложения) и разрешено ТОЛЬКО
  // страницам нашего origin; навигация на чужие адреса заблокирована выше.
  const always = new Set(["fullscreen", "clipboard-sanitized-write"]);
  const ownOnly = new Set(["clipboard-read"]);
  const isOwn = (url) =>
    Boolean(url) && ((origin && (url === origin || url.startsWith(`${origin}/`))) ||
      Boolean(DEV_URL && url.startsWith(DEV_URL)));

  ses.setPermissionRequestHandler((_wc, permission, callback, details) =>
    callback(always.has(permission) || (ownOnly.has(permission) && isOwn(details && details.requestingUrl)))
  );
  ses.setPermissionCheckHandler((_wc, permission, requestingOrigin) =>
    always.has(permission) || (ownOnly.has(permission) && isOwn(requestingOrigin))
  );
}

// ---------------------------------------------------------------- IPC

function registerIpc() {
  ipcMain.handle("app:info", (event) => {
    if (!isTrusted(event)) return null;
    return {
      version: app.getVersion(),
      electron: process.versions.electron,
      platform: process.platform,
      dataDir: dataDir(),
    };
  });

  // История и тема: хранятся в папке данных, а не в localStorage (его origin меняется с портом).
  const store = createStore(dataDir());
  ipcMain.handle("store:get", (event, key) => (isTrusted(event) ? store.get(key) : null));
  ipcMain.handle("store:set", (event, key, value) =>
    isTrusted(event) ? store.set(key, value) : false
  );

  ipcMain.handle("file:save", async (event, payload) => {
    if (!isTrusted(event)) return { saved: false, error: "untrusted" };
    try {
      const name = security.sanitizeFileName(payload && payload.name);
      const buffer = payload.base64
        ? Buffer.from(String(payload.base64), "base64")
        : Buffer.from(String(payload.text ?? ""), "utf8");
      if (buffer.length > 100 * 1024 * 1024) return { saved: false, error: "too-large" };

      const ext = path.extname(name).slice(1);
      const result = await dialog.showSaveDialog(mainWindow, {
        defaultPath: path.join(app.getPath("documents"), name),
        filters: [{ name: ext.toUpperCase(), extensions: [ext] }],
      });
      if (result.canceled || !result.filePath) return { saved: false, canceled: true };

      // Расширение, выбранное пользователем, тоже должно быть из белого списка.
      if (!security.isAllowedExtension(result.filePath)) {
        return { saved: false, error: "bad-extension" };
      }
      fs.writeFileSync(result.filePath, buffer);
      return { saved: true, path: result.filePath };
    } catch (error) {
      return { saved: false, error: String(error && error.message ? error.message : error) };
    }
  });

  ipcMain.handle("report:pdf", async (event, payload) => {
    if (!isTrusted(event)) return { saved: false, error: "untrusted" };
    const html = String((payload && payload.html) || "");
    if (!html || html.length > 3 * 1024 * 1024) return { saved: false, error: "bad-html" };

    const tmp = path.join(os.tmpdir(), `chemanalyzer-report-${process.pid}-${Date.now()}.html`);
    let win = null;
    try {
      fs.writeFileSync(tmp, html, "utf8");
      // Отдельное окно без JavaScript и без доступа к Node: отчёт — статичный HTML.
      win = new BrowserWindow({
        show: false,
        webPreferences: {
          sandbox: true,
          contextIsolation: true,
          nodeIntegration: false,
          javascript: false,
        },
      });
      await win.loadFile(tmp);
      const pdf = await win.webContents.printToPDF({
        printBackground: true,
        pageSize: "A4",
        margins: { marginType: "default" },
      });

      const name = security.sanitizeFileName(payload.name || "report.pdf", "report");
      const result = await dialog.showSaveDialog(mainWindow, {
        defaultPath: path.join(app.getPath("documents"), name.endsWith(".pdf") ? name : "report.pdf"),
        filters: [{ name: "PDF", extensions: ["pdf"] }],
      });
      if (result.canceled || !result.filePath) return { saved: false, canceled: true };
      fs.writeFileSync(result.filePath, pdf);
      return { saved: true, path: result.filePath };
    } catch (error) {
      return { saved: false, error: String(error && error.message ? error.message : error) };
    } finally {
      if (win) win.destroy();
      fs.rm(tmp, { force: true }, () => {});
    }
  });

  ipcMain.handle("shell:open-data", async (event) => {
    if (!isTrusted(event)) return false;
    await shell.openPath(dataDir());
    return true;
  });

  ipcMain.handle("shell:open-external", (event, url) => {
    if (!isTrusted(event)) return false;
    return openExternalSafe(url);
  });

  ipcMain.handle("app:quit", (event) => {
    if (isTrusted(event)) app.quit();
  });
}

// ---------------------------------------------------------------- жизненный цикл

function showFatal(error) {
  const logFile = path.join(dataDir(), "logs", "backend.log");
  dialog.showErrorBox(
    "ChemAnalyzer не запустился",
    `Не удалось запустить локальный движок (Python/RDKit).\n\n${error.message}\n\n` +
      `Журнал: ${logFile}`
  );
}

async function main() {
  if (!app.requestSingleInstanceLock()) {
    app.quit();
    return;
  }
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  await app.whenReady();
  Menu.setApplicationMenu(null); // меню — внутри интерфейса приложения
  ensureDataFiles();
  registerIpc();

  // Сразу показываем окно-заставку, пока стартует backend.
  const splash = new BrowserWindow({
    width: 420, height: 260, frame: false, resizable: false, show: true,
    backgroundColor: "#07101c", alwaysOnTop: true,
    webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false, javascript: false },
  });
  splash.loadFile(path.join(__dirname, "loading.html"));

  try {
    origin = await startBackend();
  } catch (error) {
    splash.destroy();
    showFatal(error);
    app.exit(1);
    return;
  }

  setupSession();
  const win = createWindow();
  win.once("ready-to-show", () => splash.destroy());
  await win.loadURL(DEV_URL || `${origin}/`);
}

app.on("before-quit", (event) => {
  if (quitting || !backend) return;
  event.preventDefault();
  quitting = true;
  backend.stop().finally(() => app.exit(0));
});

app.on("window-all-closed", () => app.quit());
process.on("exit", () => backend && backend.killNow());

main().catch((error) => {
  dialog.showErrorBox("ChemAnalyzer", String(error && error.message ? error.message : error));
  app.exit(1);
});
