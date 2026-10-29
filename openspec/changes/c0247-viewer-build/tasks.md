## 1. Entry

- [x] 1.1 Validate this change; read the page, the tests that read its source (`test_page.py`, `test_scene_v1.py`, `test_filter.py`, `test_edge_measure.py`), `tests/visual/harness.js` and the job scripts that call page globals; run the visual tests on the unchanged page as the baseline. Proof: `~/.npm/_npx/20f2b75ddc8bce88/node_modules/.bin/openspec validate c0247-viewer-build --strict --no-interactive`; `uv run pytest tests/visual -q` (69 passed).
  - 2026-10-29: valid; on the unchanged page (`d647b54`) `uv run pytest tests/visual -q` gave 69 passed in this
    container (Playwright's Chromium, DejaVu).

## 2. The Node project and the build

- [x] 2.1 `viewer/package.json` with exact versions (esbuild 0.28.2, TypeScript 5.9.3, Preact 10.29.8), `package-lock.json`, `tsconfig.json`, `node_modules/` ignored; `viewer/build.mjs`: the type-checked program, the linker in `main.ts` order with the unique-name rule, the esbuild vendor chunk with the namespace rewrite, the CSS bundle, the outputs and `manifest.json`, `--check` (decisions 3, 4, 6, 8). Proof: `cd viewer && npm ci && node build.mjs && node build.mjs --check`.
  - 2026-10-29: from an empty `viewer/node_modules`, `npm ci` then `node build.mjs --check` reported the committed
    bundle current: two installs and builds gave the same bytes.
- [x] 2.2 `tools/build_viewer.py` (`npm ci` when needed, build, `--check`) and the `Makefile` targets `viewer` and `viewer-check`. Proof: `uv run python tools/build_viewer.py --check`; `make viewer-check`.
  - 2026-10-29: both pass; a module declaring a second top-level `draw` made `--check` exit 1 with
    `two modules declare the top-level name "draw": core/dup.ts and board/draw.ts` (scenario "A name declared twice
    fails the build").

## 3. The port

- [x] 3.1 The shell `viewer/src/page.html` (the markup, the `EMBED` and `LIVE` script, the two placeholders) and the stylesheet split into `viewer/src/styles/` in the original rule order (decision 7). Proof: `node viewer/build.mjs`; the shell's markup equals the old page's between `<body>` and `<script>`.
  - 2026-10-29: the shell holds lines 154 to 270 of the old page verbatim; the stylesheet is ten files in the
    original rule order.
- [x] 3.2 The core, board, measure and 3D modules with their types and setters (decisions 2, 4, 5), the test markers kept. Proof: `node viewer/build.mjs` (no diagnostic).
- [x] 3.3 The sheet, table, library, SVG, links, marks, project review, catalog dialog and tree modules, and `main.ts` with the link order. Proof: `node viewer/build.mjs`; the linked script defines every top-level name the old script defined (a one-off comparison recorded under this task).
  - 2026-10-29: the old script declared 288 top-level names; the assembled page declares all of them and ten
    more (`preact` and the setters `setProject`, `setDoc`, `setS`, `setCtx`, `setP2D`, `setDpr`, `setFitted`,
    `setLinkReady`, `setLib`).
- [x] 3.4 The Changes, Messages, Findings and Navigator panels as Preact components with the same elements, classes, titles and texts (decision 6, requirement "Viewer sources"). Proof: `node viewer/build.mjs`; `uv run pytest tests/visual -q` after task 4.1.
  - 2026-10-29: the side bar, info card, status bar, tabs and toolbar of the old and new pages, normalised
    (attributes sorted, styles and `checked` as the browser reads them, adjacent text merged), are equal after
    each of thirteen steps (open, hide and visit a finding group, open, select and close a message group, a
    change, the navigator's filter and clicks, the unit) on a KiCad board with `--compare` and `--check run`, an
    Altium board, an Altium sheet with `--check run` and the hierarchical Altium sheet.

## 4. The Python side

- [x] 4.1 `template()` assembles the page from `src/fenolite/view/static/`; `page.html` leaves `src/fenolite/view/`; the wheel holds the four static files (modified requirement "Viewer page", scenario "The wheel holds the bundle and no sources"). Proof: `uv run pytest tests/unit/view tests/unit/cli/test_view_cmd.py -q -n 2`; `uv build --out-dir <scratch>` and the wheel's file list.
  - 2026-10-29: 164 passed; the wheel holds the four files of `fenolite/view/static/` and no file of
    `viewer/`; installed in a fresh environment with no `node` on `PATH`, `template()` and `page(live=True)` work.
- [x] 4.2 `tests/unit/view/test_viewer_bundle.py`: the manifest digests, the assembled page, the Preact chunk and panels, the notices (scenarios "A stale bundle fails without Node", "The served page is the assembled page", "Panels render through Preact", "Bundled viewer code"). Proof: `uv run pytest tests/unit/view/test_viewer_bundle.py -q`.
  - 2026-10-29: 7 passed.
- [x] 4.3 The unchanged tests pass: the page's unit tests and the visual tests with their references, locally and in the `viewer` job; served pages of a KiCad project, a KiCad board, an Altium board and an Altium sheet compared before and after the port. Proof: `uv run pytest tests/unit/view tests/unit/cli/test_view_cmd.py tests/unit/agent tests/consistency tests/unit/test_import_graph.py -q -n 2`; `uv run pytest tests/visual -q`.
  - 2026-10-29: 871 passed, 34 skipped; `tests/visual`: 69 passed, unchanged references. Served with
    `fenolite view --serve` and screenshotted at 1440 × 900 before and after the port (open, a selected part,
    a filter or a net, 3D): the blink project, `CM5_MINIMA_3.kicad_pcb`, `PCB1.PcbDoc` and the corpus SchDoc are
    pixel-identical except the clock of the status bar's "live · updated" text.

## 5. CI, notices and documents

- [ ] 5.1 The `viewer` job runs `uv run python tools/build_viewer.py --check` before the visual tests (scenario "The viewer job rebuilds"). Proof: `uv run pytest tests/unit/test_ci_workflow.py -q`; the job on the branch.
  - 2026-10-29: `tests/unit/test_ci_workflow.py` passes (47 tests, the new one included); the job's run on the
    branch is open until the batch is published.
- [x] 5.2 `NOTICE` lists Preact (MIT); `viewer.js` carries its notice; `tools/residue/scope.toml` excludes `viewer/package-lock.json` (modified requirement "NOTICE lists only real derivations"). Proof: `uv run pytest tests/unit/view/test_viewer_bundle.py -k notice -q`; `uv run python tools/residue/scan.py`.
  - 2026-10-29: the notice test passes; the residue scan reports 0 hits in 4 498 files.
- [x] 5.3 `docs/viewer.md` and `CONTRIBUTING.md` say where the page's sources are and how to rebuild; c0243 and c0244 re-planned on the modules and Preact panels (designs and tasks; requirements kept); the c0247 row in `openspec/README.md`. Proof: `~/.npm/_npx/20f2b75ddc8bce88/node_modules/.bin/openspec validate c0243-viewer-shell --strict --no-interactive` and the same for c0244; `uv run pytest tests/consistency -q -n 2`.
  - 2026-10-29: both valid; the consistency tests pass within the run of task 4.3. c0244's MODIFIED "Viewer
    page" is rebased on this change's wording and carries its scenario "The served page is the assembled page".

## 6. Closing

- [ ] 6.1 Run the tests and the residue scan. Proof: the focused run of task 4.3 and `uv run python tools/residue/scan.py`; `make check` in CI on the branch (the maintainer's rule of 2026-10-14).
  - 2026-10-29: the focused run and the residue scan pass locally; `make check` in CI is open until the batch is
    published.
- [x] 6.2 Confirm that no evidence label changes (no format fact is involved). Proof: `uv run python tools/gen_evidence_matrix.py --check`.
  - 2026-10-29: no label changes; the matrix check passes.
- [x] 6.3 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit -k "release_record or changelog" -q -n 2`.
  - 2026-10-29: passes once `0.7.0.dev0` is open (`b86a1b8`, as `21f7407` opened `0.6.0.dev0`): the guard of the
    0.6.0 record keeps `[Unreleased]` empty only at the released version.
