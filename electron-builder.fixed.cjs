// Reliability release with the reviewed 3.2.6 scientific model bundles.
const hlm = require("./electron-builder.hlm.cjs");
module.exports = {
  ...hlm,
  directories: { output: "build/resilience-release", buildResources: "assets" },
  extraResources: hlm.extraResources.map(resource => resource.to === "backend"
    ? { from: "build/release-3.2.7-backend/chemanalyzer-backend", to: "backend" } : resource),
};
