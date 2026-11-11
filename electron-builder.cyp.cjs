const quality = require("./electron-builder.quality.cjs");
module.exports = {
  ...quality,
  directories: { output: "build/cyp-release", buildResources: "assets" },
  extraResources: quality.extraResources.map(resource => resource.to === "backend"
    ? { from: "build/release-3.2.3-backend/chemanalyzer-backend", to: "backend" } : resource),
};
