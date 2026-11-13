const resilience = require("./electron-builder.fixed.cjs");
module.exports = {
  ...resilience,
  directories: { output: "build/chembl-pagination-release", buildResources: "assets" },
  extraResources: resilience.extraResources.map(resource => resource.to === "backend"
    ? { from: "build/release-3.2.10-backend/chemanalyzer-backend", to: "backend" } : resource),
};
