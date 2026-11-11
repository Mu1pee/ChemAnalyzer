const screening = require("./electron-builder.screening.cjs");
module.exports = {
  ...screening,
  directories: { output: "build/reliability-release", buildResources: "assets" },
  extraResources: screening.extraResources.map(resource => resource.to === "backend"
    ? { from: "build/release-3.2.5-backend/chemanalyzer-backend", to: "backend" } : resource),
};
