// Preserve the reviewed model seed; package the complete-snapshot cache fix.
const previous = require("./electron-builder.baseline.cjs");
module.exports = {
  ...previous,
  directories: { output: "build/snapshot-release", buildResources: "assets" },
  extraResources: previous.extraResources.map(resource => resource.to === "backend"
    ? { from: "build/release-3.2.14-backend/chemanalyzer-backend", to: "backend" } : resource),
};
