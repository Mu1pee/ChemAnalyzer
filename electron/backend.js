"use strict";
/**
 * Управление локальным Python-backend: свободный порт -> запуск -> health-check
 * -> остановка. Не зависит от Electron, поэтому тестируется обычным Node.
 */
const { spawn, execFile } = require("node:child_process");
const { EventEmitter } = require("node:events");
const net = require("node:net");
const http = require("node:http");

const HOST = "127.0.0.1";

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, HOST, () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

function getJson(port, urlPath, timeoutMs = 1500) {
  return new Promise((resolve, reject) => {
    const req = http.get(
      { host: HOST, port, path: urlPath, timeout: timeoutMs },
      (res) => {
        let body = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => {
          body += chunk;
          if (body.length > 65536) req.destroy(new Error("слишком большой ответ"));
        });
        res.on("end", () => {
          try {
            resolve({ status: res.statusCode, json: JSON.parse(body) });
          } catch {
            resolve({ status: res.statusCode, json: null });
          }
        });
      }
    );
    req.on("timeout", () => req.destroy(new Error("timeout")));
    req.on("error", reject);
  });
}

class BackendError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "BackendError";
    this.code = code; // EXITED | TIMEOUT | SPAWN
  }
}

/** Ждёт, пока /health ответит от НАШЕГО backend (проверяем поле application). */
async function waitForHealth({ port, timeoutMs, intervalMs = 250, isAlive }) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (!isAlive()) throw new BackendError("EXITED", "backend завершился при запуске");
    try {
      const { status, json } = await getJson(port, "/health");
      if (status === 200 && json && json.application === "ChemAnalyzer") return json;
    } catch {
      // сервер ещё не поднялся — пробуем снова
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new BackendError("TIMEOUT", `backend не ответил за ${Math.round(timeoutMs / 1000)} с`);
}

class BackendManager extends EventEmitter {
  /**
   * @param {object} o
   * @param {string} o.command        исполняемый файл
   * @param {(port:number)=>string[]} o.buildArgs
   * @param {object} [o.env]          дополнительные переменные окружения
   * @param {string} [o.cwd]
   * @param {number} [o.healthTimeoutMs]
   * @param {number} [o.attempts]     сколько раз пробовать другой порт
   * @param {(chunk:Buffer)=>void} [o.onLog]
   */
  constructor(o) {
    super();
    this.command = o.command;
    this.buildArgs = o.buildArgs;
    this.env = o.env || {};
    this.cwd = o.cwd;
    this.healthTimeoutMs = o.healthTimeoutMs ?? 90000;
    this.attempts = o.attempts ?? 3;
    this.onLog = o.onLog || (() => {});
    this.child = null;
    this.port = null;
    this.exited = true;
    this.tail = "";
  }

  get origin() {
    return this.port ? `http://${HOST}:${this.port}` : null;
  }

  _spawn(port) {
    this.tail = "";
    this.exited = false;
    const child = spawn(this.command, this.buildArgs(port), {
      cwd: this.cwd,
      env: { ...process.env, ...this.env },
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    });
    const collect = (chunk) => {
      this.onLog(chunk);
      this.tail = (this.tail + chunk.toString("utf8")).slice(-4000);
    };
    child.stdout.on("data", collect);
    child.stderr.on("data", collect);
    child.on("exit", (code, signal) => {
      this.exited = true;
      this.emit("exit", code, signal);
    });
    child.on("error", (error) => {
      this.exited = true;
      this.tail += `\n${error.message}`;
      this.emit("spawn-error", error);
    });
    this.child = child;
    return child;
  }

  async start() {
    let lastError;
    for (let attempt = 1; attempt <= this.attempts; attempt += 1) {
      const port = await findFreePort();
      this.port = port;
      this._spawn(port);

      try {
        await waitForHealth({
          port,
          timeoutMs: this.healthTimeoutMs,
          isAlive: () => !this.exited,
        });
        return { port, origin: this.origin };
      } catch (error) {
        lastError = error;
        await this.stop();
        // Порт мог быть занят между поиском и запуском — пробуем другой.
        // Таймаут повторять нет смысла: backend просто медленный или сломан.
        if (!(error instanceof BackendError) || error.code !== "EXITED") break;
      }
    }
    this.port = null;
    const detail = this.tail.trim() ? `\n\n${this.tail.trim()}` : "";
    const error = new BackendError(
      lastError && lastError.code ? lastError.code : "SPAWN",
      `${lastError ? lastError.message : "не удалось запустить backend"}${detail}`
    );
    throw error;
  }

  /** Останавливает backend вместе с дочерними процессами. */
  async stop(graceMs = 3000) {
    const child = this.child;
    if (!child || this.exited) {
      this.child = null;
      return;
    }

    const exited = new Promise((resolve) => {
      if (this.exited) resolve();
      else child.once("exit", resolve);
    });

    if (process.platform === "win32") {
      await new Promise((resolve) =>
        execFile("taskkill", ["/pid", String(child.pid), "/T", "/F"], () => resolve())
      );
    } else {
      child.kill("SIGTERM");
      setTimeout(() => {
        if (!this.exited) child.kill("SIGKILL");
      }, graceMs).unref();
    }

    await Promise.race([exited, new Promise((r) => setTimeout(r, graceMs + 2000))]);
    this.child = null;
  }

  /** Синхронное аварийное завершение (для обработчика process.on("exit")). */
  killNow() {
    if (this.child && !this.exited) {
      try {
        if (process.platform === "win32") {
          require("node:child_process").spawnSync("taskkill", [
            "/pid", String(this.child.pid), "/T", "/F",
          ]);
        } else {
          this.child.kill("SIGKILL");
        }
      } catch {
        // процесс уже завершён
      }
    }
  }
}

module.exports = { BackendManager, BackendError, findFreePort, waitForHealth, getJson, HOST };
