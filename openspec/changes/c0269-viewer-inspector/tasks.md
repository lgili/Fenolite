## 1. Entry

- [x] 1.1 Validate this change and list every caller of `showInfo`, `buildTabs`, `#lsmenu` and `#bar3d` in `viewer/src` with the tests that read them; check that `make viewer-check` passes. Proof: `~/.npm/_npx/20f2b75ddc8bce88/node_modules/.bin/openspec validate c0269-viewer-inspector --strict --no-interactive`; `uv run pytest tests/unit/view/test_page.py -q -n 2`.

## 2. Inspector

- [x] 2.1 Add the right dock (`panels/dock.tsx`) with its Properties and Layers tabs, collapse (`I`) and resize, keeping the id `info` for the Properties body. Proof: `uv run pytest tests/unit/view/test_page.py -k dock -q -n 2`; `uv run pytest tests/visual/test_interaction.py tests/visual/test_navigation.py -q` in the `viewer` CI job.
- [x] 2.2 Replace the HTML strings of `select`, `compInfo`, `padInfo`, the sheet, library, drawing, keep-out and finding selections by inspector models (`inspect/model.ts`) rendered by `renderInspector` (`panels/inspector.tsx`), with copy controls and "Copy all" (requirement "Docked inspector", scenarios "A pad's size, copied" and "Missing values are left out"). Proof: `uv run pytest tests/unit/view/test_page.py -k inspector -q -n 2`; `uv run pytest tests/visual/test_inspector.py -k pad tests/visual/test_catalog.py -q` in the `viewer` CI job.
- [x] 2.3 Add the inspector actions as registry commands of `core/commands.ts` (scenario "Show in schematic"). Proof: `uv run pytest tests/visual/test_inspector.py -k cross_probe -q` in the `viewer` CI job.
- [x] 2.4 Make the dock a bottom sheet at 760 px and below (scenario "A 390-pixel window"). Proof: `uv run pytest tests/visual/test_inspector.py -k narrow tests/visual/test_interaction.py -k fit_the_viewport -q` in the `viewer` CI job.

## 3. Net emphasis

- [x] 3.1 Draw picked nets, parts and query results (`board/draw.ts`) in their own colours with the emphasis outline, zone fills of the net lighter and outlined, Dim at 0.22 (scenario "A ground net stands out"). Proof: `uv run pytest tests/visual/test_inspector.py -k emphasis -q` in the `viewer` CI job.

## 4. Layers panel

- [x] 4.1 Build the Layers panel (`panels/layers.tsx`) with groups, visibility, opacity, current layer and presets; remove layer tabs from the bottom bar on boards and footprints, keep sheet tabs (scenarios "Long names are not cut", "Opacity and shortcuts"). Proof: `uv run pytest tests/unit/view/test_page.py -k layer -q -n 2`; `uv run pytest tests/visual/test_layers.py -q` in the `viewer` CI job.

## 5. 3D

- [x] 5.1 Hide 2D-only controls in 3D, add the view cube (`three/view-cube.ts`) and the front, back, left and right presets, the 3D panel, the new lighting and the body colour (requirement "3D view controls", scenario "The view cube"). Proof: `uv run pytest tests/visual/test_3d.py -q` in the `viewer` CI job.

## 6. References and documentation

- [ ] 6.1 Regenerate the screenshot references with the dock and add `kicad_board_net.png` with `uv run python tools/update_view_refs.py` in the `viewer` job's environment; the maintainer reviews the images before they are committed (requirement "Net emphasis reference"). Proof: `uv run pytest tests/visual -q` in the `viewer` CI job on the commit that holds the references.
- [ ] 6.2 Update `docs/viewer.md` ("The page": Layers panel instead of layer tabs, the inspector, net emphasis, the 3D controls; "Units and measurement": the inspector rows). Proof: `uv run pytest tests/unit -k "docs and viewer" -q -n 2`; `make check-fast`.

## 7. Closing

- [ ] 7.1 Run the tests and the residue scan; the committed bundle is a fresh build. Proof: `uv run python tools/build_viewer.py --check`; `make check-fast`, then the CI jobs of the branch, `viewer` included.
- [x] 7.2 Confirm that no evidence label changes (no format fact is involved). Proof: `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 7.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]` for each closed task. Proof: `uv run pytest tests/unit -k "release_record or changelog" -q -n 2`.

Open on the branch (2026-10-29): 6.1 — the references were regenerated with the dock (and `kicad_board_net.png` added) by `tools/update_view_refs.py` in this session's Linux container (Playwright 1.63.0's Chromium, `tests/visual/fonts.conf`), where the unchanged references of `dev` had passed pixel for pixel; they wait for the maintainer's review and the `viewer` CI job. 6.2 — `docs/viewer.md` is updated ("The page": inspector, Layers panel, net emphasis, 3D controls; "Units and measurement": the inspector's rows); its proof `tests/unit -k "docs and viewer"` selects no test, and `make check-fast` is left to the maintainer's machine. 7.1 — `tools/build_viewer.py --check` passes; `make check-fast` and the CI jobs are open; focused checks ran here: ruff check and format of `tests` and `tools`, the residue scan, `tests/unit/view`, `tests/unit/cli/test_view_cmd.py`, `tests/unit/agent`, `tests/consistency`, `tests/unit/test_import_graph.py` and `tests/visual` (101 passed, `FENOLITE_REQUIRE=browser`). The dock keeps the design's resize handle (240 to 480 px); the decided "no resize handle" concerns the side bar of c0268.
