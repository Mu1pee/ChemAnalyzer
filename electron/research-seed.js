"use strict";
const fs = require("node:fs");
const path = require("node:path");

// Only build-bundled, UUID-addressed research artifacts are seeded. Existing
// user records retain their review/approval state and are never replaced.
function seedResearchData(seedRoot, userData) {
  let copied = 0;
  for (const category of ["tasks", "runs", "models"]) {
    const source = path.join(seedRoot, category);
    if (!fs.existsSync(source)) continue;
    for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
      if (!entry.isDirectory() || !/^[a-f0-9]{32}$/.test(entry.name)) continue;
      const target = path.join(userData, "research_agent", category, entry.name);
      if (fs.existsSync(target)) continue;
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.cpSync(path.join(source, entry.name), target, {
        recursive: true, force: false, errorOnExist: true,
        filter: file => !fs.lstatSync(file).isSymbolicLink(),
      });
      copied++;
    }
  }
  return copied;
}

module.exports = { seedResearchData };
