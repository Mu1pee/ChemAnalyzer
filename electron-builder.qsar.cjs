const research = require("./electron-builder.research.cjs");
if (!process.env.CHEMANALYZER_QSAR_RELEASE_DIR) {
  throw new Error("Set CHEMANALYZER_QSAR_RELEASE_DIR to the accepted, reviewed model bundle");
}

module.exports = {
  ...research,
  directories: { output: "build/qsar-release", buildResources: "assets" },
  extraResources: research.extraResources.map(resource => resource.to === "backend"
    ? { from: "build/release-3.2.1-backend/chemanalyzer-backend", to: "backend" } : resource),
  compression: "normal",
  win: { ...research.win, target: [{ target: "portable", arch: ["x64"] }, { target: "nsis", arch: ["x64"] }] },
  nsis: { ...research.nsis, useZip: true, differentialPackage: false, artifactName: "ChemAnalyzer-${version}-QSAR-Setup.exe" },
};
