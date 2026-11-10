const qsar = require("./electron-builder.qsar.cjs");

module.exports = {
  ...qsar,
  directories: { output: "build/quality-release", buildResources: "assets" },
  extraResources: qsar.extraResources.map(resource => resource.to === "backend"
    ? { from: "build/release-3.2.2-backend/chemanalyzer-backend", to: "backend" } : resource),
};
