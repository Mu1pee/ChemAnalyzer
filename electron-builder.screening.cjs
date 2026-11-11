const cyp = require("./electron-builder.cyp.cjs");
module.exports = {
  ...cyp,
  directories: { output: "build/screening-release-final", buildResources: "assets" },
  extraResources: cyp.extraResources.map(resource => resource.to === "backend"
    ? { from: "build/release-3.2.4-backend-final/chemanalyzer-backend", to: "backend" } : resource),
};
