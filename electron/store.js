"use strict";
/**
 * Хранилище состояния интерфейса (история, тема) в папке данных пользователя.
 *
 * Зачем: localStorage привязан к origin, а у desktop-версии порт backend
 * случайный, поэтому при каждом запуске origin новый и localStorage пуст.
 * Файлы в папке данных от порта не зависят.
 *
 * Чистый Node (без Electron) — тестируется отдельно.
 */
const fs = require("node:fs");
const path = require("node:path");

const ALLOWED_KEYS = new Set(["history", "theme"]);
const MAX_BYTES = 2 * 1024 * 1024;

function createStore(baseDir) {
  const dir = path.join(baseDir, "state");

  const fileFor = (key) => path.join(dir, `${key}.json`);

  return {
    /** Возвращает сохранённую строку или null. */
    get(key) {
      if (typeof key !== "string" || !ALLOWED_KEYS.has(key)) return null;
      try {
        return fs.readFileSync(fileFor(key), "utf8");
      } catch {
        return null;
      }
    },

    /** Атомарная запись (временный файл + переименование). */
    set(key, value) {
      if (typeof key !== "string" || !ALLOWED_KEYS.has(key)) return false;
      if (typeof value !== "string" || Buffer.byteLength(value, "utf8") > MAX_BYTES) return false;
      try {
        fs.mkdirSync(dir, { recursive: true });
        const target = fileFor(key);
        const tmp = `${target}.${process.pid}.tmp`;
        fs.writeFileSync(tmp, value, "utf8");
        fs.renameSync(tmp, target);
        return true;
      } catch {
        return false;
      }
    },
  };
}

module.exports = { createStore, ALLOWED_KEYS, MAX_BYTES };
