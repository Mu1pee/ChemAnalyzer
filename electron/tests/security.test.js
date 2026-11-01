"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const s = require("../security");

test("внешние URL: разрешены только https и белый список хостов", () => {
  assert.equal(s.isAllowedExternalUrl("https://pubchem.ncbi.nlm.nih.gov/compound/2244"), true);
  assert.equal(s.isAllowedExternalUrl("https://www.ebi.ac.uk/chembl/compound_report_card/CHEMBL25"), true);
  for (const bad of [
    "http://pubchem.ncbi.nlm.nih.gov/x",
    "https://evil.com/",
    "https://pubchem.ncbi.nlm.nih.gov.evil.com/",
    "https://user:pw@pubchem.ncbi.nlm.nih.gov/",
    "file:///C:/Windows/System32/calc.exe",
    "javascript:alert(1)",
    "ms-msdt:/id PCWDiagnostic",
    "\\\\server\\share",
    "",
    null,
    undefined,
  ]) {
    assert.equal(s.isAllowedExternalUrl(bad), false, String(bad));
  }
});

test("CSP: нет unsafe-eval по умолчанию, есть при relaxed", () => {
  const strict = s.buildCsp();
  assert.ok(!strict.includes("'unsafe-eval'"));
  assert.ok(strict.includes("'wasm-unsafe-eval'"));
  assert.ok(strict.includes("connect-src 'self'"));
  assert.ok(strict.includes("object-src 'none'"));
  assert.ok(s.buildCsp({ relaxed: true }).includes("'unsafe-eval'"));
});

test("имена файлов: нет обхода каталогов, зарезервированных имён и опасных расширений", () => {
  assert.equal(s.sanitizeFileName("report.pdf"), "report.pdf");
  assert.equal(s.sanitizeFileName("../../Windows/evil.pdf"), "evil.pdf");
  assert.equal(s.sanitizeFileName("C:\\Users\\x\\a.csv"), "a.csv");
  assert.equal(s.sanitizeFileName("calc.exe"), "calc.txt");
  assert.equal(s.sanitizeFileName("run.bat"), "run.txt");
  assert.equal(s.sanitizeFileName("CON.pdf"), "chemanalyzer.pdf");
  assert.equal(s.sanitizeFileName('bad<>:"|?*.json'), "bad_______.json");
  assert.equal(s.sanitizeFileName(""), "chemanalyzer.txt");
  assert.equal(s.sanitizeFileName("a".repeat(500) + ".csv").length <= 104, true);
  assert.equal(s.isAllowedExtension("x.EXE"), false);
  assert.equal(s.isAllowedExtension("x.SDF"), true);
});
