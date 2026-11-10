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
  ],
  compression: "store",
  win: { ...original.win, target: [{ target: "portable", arch: ["x64"] }] },
  portable: { ...original.portable, useZip: true, artifactName: "ChemAnalyzer-Bioactivity-3.2.0-Portable.exe" },
};
