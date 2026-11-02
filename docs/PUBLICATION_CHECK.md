# Publication verification

Verified on Windows, 2026-11-02.

- Original commit 41d6f57 exists on main; history preserved.
- Origin: https://github.com/Mu1pee/ChemAnalyzer.git. Remote advertised no refs during inspection.
- Backend: 113 tests passed. Dependencies installed in backend/.venv.
- Backend selftest: passed with Python -X utf8 (default console encoding cannot print all symbols).
- Electron: 17 tests passed during the preceding inspection.
- Frontend: TypeScript and Vite production build passed after adding the events browser implementation and Vite alias.
- Frontend dependency lockfile generated for reproducibility.
- Generated Ketcher resources, TypeScript cache, pytest cache and local environment files excluded from Git.
- Initial tracked-file scan found no typical credential patterns. This is not an exhaustive security audit.
- Showcase copyright and third-party notices preserved.

## Outstanding findings

- npm audit reports five moderate findings in the Ketcher -> dpdm -> glob/minimatch dependency chain (GHSA-3g3m-2fjr-6pw4, GHSA-g3hv-75wg-m249).
- npm proposes a breaking Ketcher downgrade; it was not applied automatically.
- miew-react 0.11.0 declares React 18 peer dependencies while this project uses React 19. Runtime compatibility requires verification.
- Vite reports eval in 3Dmol and a large application bundle.
- Windows installer packaging and clean-machine desktop smoke testing have not been performed.
- No public push performed: the user's authorization was conditional on satisfactory checks.

Before publishing, resolve or explicitly accept the dependency findings and verify the editor/3D viewer at runtime. Publish source only with the existing experimental-feature limitations; do not describe this as a validated installer release.
