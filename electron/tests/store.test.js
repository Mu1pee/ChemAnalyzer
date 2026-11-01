"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { createStore, MAX_BYTES } = require("../store");

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), "chemanalyzer-store-"));

test("запись и чтение переживают «перезапуск» (новый экземпляр хранилища)", () => {
  const dir = tmp();
  const value = JSON.stringify([{ smiles: "CCO", title: "Этанол" }]);
  assert.equal(createStore(dir).set("history", value), true);
  assert.equal(createStore(dir).get("history"), value);
  assert.equal(createStore(dir).get("theme"), null);
});

test("ключи вне белого списка и попытки выйти из каталога отклоняются", () => {
  const dir = tmp();
  const s = createStore(dir);
  for (const bad of ["../../evil", "..\\evil", "settings", "", "history/../x", null, undefined, 5]) {
    assert.equal(s.set(bad, "x"), false, String(bad));
    assert.equal(s.get(bad), null, String(bad));
  }
  assert.equal(fs.existsSync(path.join(dir, "evil.json")), false);
});

test("слишком большое и нестроковое значение не записывается", () => {
  const s = createStore(tmp());
  assert.equal(s.set("history", "x".repeat(MAX_BYTES + 1)), false);
  assert.equal(s.set("history", { a: 1 }), false);
  assert.equal(s.set("history", null), false);
  assert.equal(s.get("history"), null);
});

test("после записи не остаётся временных файлов, перезапись заменяет значение", () => {
  const dir = tmp();
  const s = createStore(dir);
  s.set("theme", "dark");
  s.set("theme", "light");
  assert.equal(s.get("theme"), "light");
  assert.deepEqual(fs.readdirSync(path.join(dir, "state")), ["theme.json"]);
});

test("кириллица сохраняется без искажений", () => {
  const s = createStore(tmp());
  s.set("history", "Название: аспирин ✓");
  assert.equal(s.get("history"), "Название: аспирин ✓");
});

test("повреждённая или недоступная папка не приводит к исключению", () => {
  const dir = tmp();
  fs.writeFileSync(path.join(dir, "state"), "я — файл, а не папка");
  const s = createStore(dir);
  assert.equal(s.set("history", "x"), false);
  assert.equal(s.get("history"), null);
});
