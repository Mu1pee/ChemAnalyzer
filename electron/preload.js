"use strict";
/**
 * Безопасный мост между интерфейсом и главным процессом.
 * Наружу отдаётся ТОЛЬКО перечисленный набор функций; ipcRenderer, require
 * и Node API странице недоступны (contextIsolation + sandbox).
 */
const { contextBridge, ipcRenderer } = require("electron");

const arg = process.argv.find((a) => a.startsWith("--api-origin="));
const apiOrigin = arg ? arg.slice("--api-origin=".length) : null;

contextBridge.exposeInMainWorld(
  "chemAnalyzer",
  Object.freeze({
    isDesktop: true,
    apiOrigin,
    getInfo: () => ipcRenderer.invoke("app:info"),
    getStored: (key) => ipcRenderer.invoke("store:get", key),
    setStored: (key, value) => ipcRenderer.invoke("store:set", key, value),
    saveFile: (payload) => ipcRenderer.invoke("file:save", payload),
    exportPdf: (payload) => ipcRenderer.invoke("report:pdf", payload),
    openDataFolder: () => ipcRenderer.invoke("shell:open-data"),
    openExternal: (url) => ipcRenderer.invoke("shell:open-external", url),
    quit: () => ipcRenderer.invoke("app:quit"),
  })
);
