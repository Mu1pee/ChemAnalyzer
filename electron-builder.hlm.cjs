const reliability = require("./electron-builder.reliability.cjs");
module.exports = {
  ...reliability,
  directories: { output: "build/hlm-release", buildResources: "assets" },
  // Standard compressed payload keeps large-bundle NSIS compilation bounded.
  portable: { ...reliability.portable, useZip: false },
  extraResources: reliability.extraResources.map(resource => resource.to === "backend"
    ? { from: "build/release-3.2.6-backend/chemanalyzer-backend", to: "backend" } : resource),
};
