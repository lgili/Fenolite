## 0. Entry check

- [x] 0.1 Read the living `cli-contract` and `package-layering` specs. Note under this task, with the date, which open change holds a delta of "Allowed import edges". When one is archived first, regenerate the MODIFIED block from the living text. Proof: `openspec validate c0176-board-viewer --strict --no-interactive`.
  - 2026-10-25: c0173 (open, merged into `release-0.5.0`) holds a MODIFIED delta of "Allowed import edges" that adds `panel`; the living text does not yet name it. This change's block adds `view` to the living text; whichever change is archived second regenerates its block from the archived text. The test table already holds both. Proof passed.

## 1. Scene and tree

- [x] 1.1 Add `view` to the layering table, and add `fenolite.view.scene` with the palette, the primitives, texts, components, bodies and notes (scenarios "Counts of a KiCad board" and "An Altium board without mask layers"). Proof: `uv run pytest tests/unit/view/test_scene.py tests/unit/test_import_graph.py -q`.
  - 2026-10-25: proof passed. The scene of an Altium board of 261 parts (6 073 primitives) is about 0.8 MB of JSON.
- [x] 1.2 Add `fenolite.view.project` (scenario "An Altium project"), with KiCad projects, folders and single boards. Proof: `uv run pytest tests/unit/view/test_project.py -q`.
  - 2026-10-25: proof passed.

## 2. Page, export and server

- [x] 2.1 Add `page.html`, with the left project panel, the bottom layer tabs, the 2D view, the 3D view and the overlays, and `fenolite.view.export` (scenario "Standalone page round-trips"). Proof: `uv run pytest tests/unit/view/test_page.py -q`.
  - 2026-10-25: proof passed.
- [x] 2.2 Add `fenolite.view.server` (scenario "A saved board is reloaded"). Proof: `uv run pytest tests/unit/view/test_server.py -q`.
  - 2026-10-25: proof passed.
- [x] 2.3 Review the page in a browser, on `two_layer.kicad_pcb` and on `board6.PcbDoc` through `fenolite view --serve`. Record the date, the browser, and what was checked: tree, tabs, current layer, single-layer mode, flip, search, measure and 3D. Proof: the record under this task.
  - 2026-10-25, the Chromium-based browser pane of the maintainer's desktop app, macOS: `fenolite view --serve` on the KiCad project `tests/data/acceptance/blink_2layer_t9/blink.kicad_pro` and on a local Altium project of the maintainer (261 parts, two boards, schematics, libraries, an output job and drawings; the project itself is not in the repository). Checked: the tree with its groups and the click that opens a board; the tabs, the current layer drawn last, a layer hidden by its swatch, `Shift+S` single-layer mode; net highlight on click; search by reference (zoom and part details); measurement; the Bottom view (texts of the back side readable, the front mirrored); and the 3D view with the textured faces and the extruded bodies. Three defects were found and fixed in the same session: `Shift+S` was missed when the browser reported the key as `s`; a click picked a zone outline before the copper under it; and the search box kept the keyboard after a click on the board, so the shortcuts were ignored. The board6 test board was not opened in the browser: its scene is covered by `test_scene.py`.

## 3. Command and docs

- [x] 3.1 Add `fenolite view` (scenarios of "View command"), with the overlays of an `analyze` reply. Proof: `uv run pytest tests/unit/cli/test_view_cmd.py tests/consistency -q`.
  - 2026-10-25: proof passed (with `tests/unit/agent` and `tests/unit/test_import_graph.py`: 565 passed, 24 skipped).
- [x] 3.2 Write `docs/viewer.md` and the `view` section of `docs/cli-contract.md`. Add a tested line to the guide page `files`, add `view` to `HOME["files"]`, and run `tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
  - 2026-10-25: proof passed. The skill folder holds 149 693 bytes against its budget of 150 000 on this branch.

## 4. Closing

- [x] 4.1 Run the tests and the residue scan. Proof: `make check-fast`.
  - 2026-10-25, macOS: lint, format, pyright and residue clean (0 hits in 3 761 files); tests 13 802 passed, 74 skipped, 1 failed. The failure, `tests/unit/lens/test_altium_pcb_complete.py::test_altium_samples_of_earlier_changes_keep_their_bytes`, fails the same way on a clean worktree of `origin/release-0.5.0` (`a979b412`); it is not caused by this change. The full gate is left to CI.
- [x] 4.2 Evidence labels: the scene is `INFERRED`, and no label of another capability changes. Proof: `uv run python tools/gen_evidence_matrix.py --check`.
  - 2026-10-25: proof passed.
- [x] 4.3 Add an entry under `## [Unreleased]` in `CHANGELOG.md` once the version after 0.5.0 is open. Proof: `uv run pytest tests/unit/test_release_record_v05.py -q`.
  - 2026-10-25: the entry is under `## [0.5.0]` of `CHANGELOG.md`, not `[Unreleased]`: by the maintainer's decision of 2026-10-25 the change ships in 0.5.0 (c0171 task 1.15). Proof passed (`tests/unit/test_release_record_v05.py`).
  - 2026-10-25: WAITS on the maintainer: the release guard keeps `[Unreleased]` empty while the version is `0.5.0`. The text is ready: `- **Board viewer** (c0176): `fenolite view PATH` shows the boards of an Altium or KiCad project in a browser without either tool — the project's documents in a side panel, layer tabs along the bottom, Top and Bottom views, net highlight, search, measurement, a 3D view with part bodies and the paths of an `analyze` reply; `--serve` serves it live on `127.0.0.1`, `--export` writes one standalone page; the package `fenolite.view` builds the scene from the neutral model with the standard library only.`
