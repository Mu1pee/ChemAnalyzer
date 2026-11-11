"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { seedResearchData } = require("../research-seed");

test("failed seed copy can be retried without retaining a partial model", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "chem-seed-"));
  const copy = fs.cpSync;
  try {
    const id = "b".repeat(32);
    const seed = path.join(root, "seed");
    const user = path.join(root, "user");
    const source = path.join(seed, "models", id);
    fs.mkdirSync(source, { recursive: true });
    fs.writeFileSync(path.join(source, "metadata.json"), '{}');
    fs.writeFileSync(path.join(source, "model.joblib"), "complete model");
    fs.cpSync = (_source, target) => {
      fs.mkdirSync(target, { recursive: true });
      fs.writeFileSync(path.join(target, "metadata.json"), '{}');
      throw new Error("simulated disk error");
    };
    assert.throws(() => seedResearchData(seed, user), /simulated disk error/);
    const target = path.join(user, "research_agent", "models", id);
    assert.equal(fs.existsSync(target), false);
    fs.cpSync = copy;
    assert.equal(seedResearchData(seed, user), 1);
    assert.equal(fs.readFileSync(path.join(target, "model.joblib"), "utf8"), "complete model");
    assert.deepEqual(fs.readdirSync(path.dirname(target)), [id]);
  } finally {
    fs.cpSync = copy;
    assert.ok(path.resolve(root).startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("research seed copies only UUID records and preserves existing user metadata", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "chem-seed-"));
  try {
    const identifier = "a".repeat(32);
    const seed = path.join(root, "seed");
    const user = path.join(root, "user");
    const source = path.join(seed, "models", identifier);
    fs.mkdirSync(source, { recursive: true });
    fs.mkdirSync(path.join(seed, "models", "not-a-model"));
    fs.writeFileSync(path.join(source, "metadata.json"), '{"status":"experimental"}');
    assert.equal(seedResearchData(seed, user), 1);
    const target = path.join(user, "research_agent", "models", identifier, "metadata.json");
    assert.equal(JSON.parse(fs.readFileSync(target)).status, "experimental");
    fs.writeFileSync(target, '{"status":"validated"}');
    assert.equal(seedResearchData(seed, user), 0);
    assert.equal(JSON.parse(fs.readFileSync(target)).status, "validated");
    assert.equal(fs.existsSync(path.join(user, "research_agent", "models", "not-a-model")), false);
    assert.equal(seedResearchData(path.join(root, "absent"), user), 0);
  } finally {
    // mkdtemp returns a unique test-only directory under the OS temp directory.
    assert.ok(path.resolve(root).startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(root, { recursive: true, force: true });
  }
});
