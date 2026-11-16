// Quality-admission patch; the reviewed 3.2.12 scientific artifacts are preserved.
const previous = require("./electron-builder.specialized.cjs");
module.exports = {
  ...previous,
  directories: { output: "build/baseline-release", buildResources: "assets" },
  extraResources: previous.extraResources.map(resource => resource.to === "backend"
    ? { from: "build/release-3.2.13-backend/chemanalyzer-backend", to: "backend" } : resource),
};
