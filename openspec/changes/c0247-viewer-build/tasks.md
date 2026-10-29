## 1. Entry

- [ ] 1.1 Validate this change; read the page, the tests that read its source (`test_page.py`, `test_scene_v1.py`, `test_filter.py`, `test_edge_measure.py`), `tests/visual/harness.js` and the job scripts that call page globals; run the visual tests on the unchanged page as the baseline. Proof: `~/.npm/_npx/20f2b75ddc8bce88/node_modules/.bin/openspec validate c0247-viewer-build --strict --no-interactive`; `uv run pytest tests/visual -q` (69 passed).

## 2. The Node project and the build

- [ ] 2.1 `viewer/package.json` with exact versions (esbuild 0.28.2, TypeScript 5.9.3, Preact 10.29.8), `package-lock.json`, `tsconfig.json`, `node_modules/` ignored; `viewer/build.mjs`: the type-checked program, the linker in `main.ts` order with the unique-name rule, the esbuild vendor chunk with the namespace rewrite, the CSS bundle, the outputs and `manifest.json`, `--check` (decisions 3, 4, 6, 8). Proof: `cd viewer && npm ci && node build.mjs && node build.mjs --check`.
- [ ] 2.2 `tools/build_viewer.py` (`npm ci` when needed, build, `--check`) and the `Makefile` targets `viewer` and `viewer-check`. Proof: `uv run python tools/build_viewer.py --check`; `make viewer-check`.

## 3. The port

- [ ] 3.1 The shell `viewer/src/page.html` (the markup, the `EMBED` and `LIVE` script, the two placeholders) and the stylesheet split into `viewer/src/styles/` in the original rule order (decision 7). Proof: `node viewer/build.mjs`; the shell's markup equals the old page's between `<body>` and `<script>`.
- [ ] 3.2 The core, board, measure and 3D modules with their types and setters (decisions 2, 4, 5), the test markers kept. Proof: `node viewer/build.mjs` (no diagnostic).
- [ ] 3.3 The sheet, table, library, SVG, links, marks, project review, catalog dialog and tree modules, and `main.ts` with the link order. Proof: `node viewer/build.mjs`; the linked script defines every top-level name the old script defined (a one-off comparison recorded under this task).
- [ ] 3.4 The Changes, Messages, Findings and Navigator panels as Preact components with the same elements, classes, titles and texts (decision 6, requirement "Viewer sources"). Proof: `node viewer/build.mjs`; `uv run pytest tests/visual -q` after task 4.1.

## 4. The Python side

- [ ] 4.1 `template()` assembles the page from `src/fenolite/view/static/`; `page.html` leaves `src/fenolite/view/`; the wheel holds the four static files (modified requirement "Viewer page", scenario "The wheel holds the bundle and no sources"). Proof: `uv run pytest tests/unit/view tests/unit/cli/test_view_cmd.py -q -n 2`; `uv build --out-dir <scratch>` and the wheel's file list.
- [ ] 4.2 `tests/unit/view/test_viewer_bundle.py`: the manifest digests, the assembled page, the Preact chunk and panels, the notices (scenarios "A stale bundle fails without Node", "The served page is the assembled page", "Panels render through Preact", "Bundled viewer code"). Proof: `uv run pytest tests/unit/view/test_viewer_bundle.py -q`.
- [ ] 4.3 The unchanged tests pass: the page's unit tests and the visual tests with their references, locally and in the `viewer` job; served pages of a KiCad project, a KiCad board, an Altium board and an Altium sheet compared before and after the port. Proof: `uv run pytest tests/unit/view tests/unit/cli/test_view_cmd.py tests/unit/agent tests/consistency tests/unit/test_import_graph.py -q -n 2`; `uv run pytest tests/visual -q`.

## 5. CI, notices and documents

- [ ] 5.1 The `viewer` job runs `uv run python tools/build_viewer.py --check` before the visual tests (scenario "The viewer job rebuilds"). Proof: `uv run pytest tests/unit/test_ci_workflow.py -q`; the job on the branch.
- [ ] 5.2 `NOTICE` lists Preact (MIT); `viewer.js` carries its notice; `tools/residue/scope.toml` excludes `viewer/package-lock.json` (modified requirement "NOTICE lists only real derivations"). Proof: `uv run pytest tests/unit/view/test_viewer_bundle.py -k notice -q`; `uv run python tools/residue/scan.py`.
- [ ] 5.3 `docs/viewer.md` and `CONTRIBUTING.md` say where the page's sources are and how to rebuild; c0243 and c0244 re-planned on the modules and Preact panels (designs and tasks; requirements kept); the c0247 row in `openspec/README.md`. Proof: `~/.npm/_npx/20f2b75ddc8bce88/node_modules/.bin/openspec validate c0243-viewer-shell --strict --no-interactive` and the same for c0244; `uv run pytest tests/consistency -q -n 2`.

## 6. Closing

- [ ] 6.1 Run the tests and the residue scan. Proof: the focused run of task 4.3 and `uv run python tools/residue/scan.py`; `make check` in CI on the branch (the maintainer's rule of 2026-10-14).
- [ ] 6.2 Confirm that no evidence label changes (no format fact is involved). Proof: `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 6.3 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit -k "release_record or changelog" -q -n 2`.
