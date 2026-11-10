const fs = require("node:fs");
const path = require("node:path");
const { build: original } = require("./package.json");
const seed = process.env.CHEMANALYZER_RESEARCH_SEED_DIR;
if (!seed || !fs.statSync(seed).isDirectory()) {
  throw new Error("Set CHEMANALYZER_RESEARCH_SEED_DIR to a reviewed local ResearchAgent registry");
}

module.exports = {
  ...original,
  directories: { output: "build/bioactivity-release", buildResources: "assets" },
  extraMetadata: { chemanalyzerResearchBundle: true },
  extraResources: [
    { from: "build/bioactivity-backend/chemanalyzer-backend", to: "backend" },
    { from: "frontend/dist", to: "frontend" },
    { from: path.resolve(seed), to: "research-seed" },
    { from: "LICENSE_NOTICES.md", to: "LICENSE_NOTICES.md" },
    ...(process.env.CHEMANALYZER_QSAR_RELEASE_DIR ? [
      { from: path.resolve(process.env.CHEMANALYZER_QSAR_RELEASE_DIR), to: "qsar-models" }
    ] : []),
  ],
  compression: "store",
  win: { ...original.win, target: [{ target: "portable", arch: ["x64"] }] },
  portable: { ...original.portable, useZip: true, artifactName: "ChemAnalyzer-${version}-QSAR-Portable.exe" },
};
