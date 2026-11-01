"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const net = require("node:net");
const path = require("node:path");
const { BackendManager, BackendError, findFreePort, getJson } = require("../backend");

const FAKE = path.join(__dirname, "fake-backend.js");
const make = (mode, extra = {}) =>
  new BackendManager({
    command: process.execPath,
    buildArgs: (port) => [FAKE, "--port", String(port)],
    env: { FAKE_MODE: mode },
    healthTimeoutMs: 4000,
    ...extra,
  });

const alive = (pid) => {
  try { process.kill(pid, 0); return true; } catch { return false; }
};

test("findFreePort возвращает реально свободный порт", async () => {
  const port = await findFreePort();
  assert.ok(port >= 1024 && port <= 65535);
  await new Promise((resolve, reject) => {
    const s = net.createServer().listen(port, "127.0.0.1", () => s.close(resolve));
    s.on("error", reject);
  });
});

test("start: запускает backend, дожидается /health и отдаёт origin", async () => {
  const b = make("ok");
  const { port, origin } = await b.start();
  try {
    assert.equal(origin, `http://127.0.0.1:${port}`);
    const { status, json } = await getJson(port, "/health");
    assert.equal(status, 200);
    assert.equal(json.application, "ChemAnalyzer");
  } finally {
    await b.stop();
  }
});

test("stop: процесс действительно завершается", async () => {
  const b = make("ok");
  await b.start();
  const pid = b.child.pid;
  assert.ok(alive(pid));
  await b.stop();
  await new Promise((r) => setTimeout(r, 200));
  assert.equal(alive(pid), false, "процесс backend остался жить");
});

test("stop безопасен без запуска и при повторном вызове", async () => {
  const b = make("ok");
  await b.stop();
  await b.start();
  await b.stop();
  await b.stop();
});

test("backend падает при старте: ошибка EXITED с хвостом лога, попытки исчерпаны", async () => {
  const b = make("crash", { attempts: 2 });
  await assert.rejects(b.start(), (err) => {
    assert.ok(err instanceof BackendError);
    assert.equal(err.code, "EXITED");
    assert.match(err.message, /boom: порт занят/);
    return true;
  });
  assert.equal(b.origin, null);
});

test("backend не отвечает: ошибка TIMEOUT и процесс не остаётся висеть", async () => {
  const b = make("silent", { healthTimeoutMs: 800 });
  await assert.rejects(b.start(), (err) => err.code === "TIMEOUT");
  assert.equal(b.child, null);
});

test("посторонний сервис на порту не принимается за backend", async () => {
  const b = make("foreign", { healthTimeoutMs: 800 });
  await assert.rejects(b.start(), (err) => err.code === "TIMEOUT");
});

test("несуществующий исполняемый файл даёт понятную ошибку, а не зависание", async () => {
  const b = new BackendManager({
    command: path.join(__dirname, "no-such-binary"),
    buildArgs: () => [],
    healthTimeoutMs: 2000,
    attempts: 1,
  });
  await assert.rejects(b.start(), (err) => err instanceof BackendError);
});
