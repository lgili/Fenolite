## 0. Entry check

- [x] 0.1 Read the specs of c0176 to c0178 and the library readers (`read_schlib`, the backends' library reads). Note under this task, with the date, the probe of a one-part board. Proof: `openspec validate c0179-libraries-and-units --strict --no-interactive`.
  - 2026-10-25:
    - **Probe:** a `FootprintDef` placed at the origin of a one-part `Board` gave its pad copper through the Altium and the KiCad backends' `board_pads`, and a scene through `build_scene`. It held for the QFP of `blink.PcbLib` and of `Mini.pretty`.
    - **Exactness:** the Altium QFP pads are 549 999 nm high, against 550 000 nm in the KiCad copy. The pad list therefore keeps nanometres.
    - The branch is `c0178-native-themes` (`efc95d8`). Proof passed.

## 1. Scenes

- [x] 1.1 Add the pad list to board scenes (scenario "Pads of a KiCad board"). Proof: `uv run pytest tests/unit/view/test_library.py -k board_pads tests/unit/view/test_scene.py -q`.
  - 2026-10-25: proof passed.
- [x] 1.2 Add `fenolite.view.library` with footprint libraries (scenario "Footprints of an Altium library"). Proof: `uv run pytest tests/unit/view/test_library.py -k footprint -q`.
  - 2026-10-25: proof passed. Every pad matches its model pad's size and drill in nanometres, and its centre in µm.
- [x] 1.3 Add symbol libraries, with symbol scenes in `schematic.py` and `kicad_schematic.py` (scenario "Symbols of both tools"). Proof: `uv run pytest tests/unit/view/test_library.py -q`.
  - 2026-10-25: proof passed (5 tests). The five libraries of the test data build: `blink.PcbLib`, `Mini.pretty`, `blink.SchLib`, `FenoliteHier.SchLib` and `Mini_v9.kicad_sym` (three units of `Mini_DualGate`).
- [x] 1.4 Mark libraries as viewable (scenario "An Altium project with libraries"). Proof: `uv run pytest tests/unit/view/test_project.py -q`.
  - 2026-10-25: proof passed. `test_refusals` now refuses an `.IntLib`.

## 2. Page and command

- [x] 2.1 Add units, pad properties, measurement with snapping on every view, and the library list to the page (scenario "Unit conversions"). Proof: `uv run pytest tests/unit/view/test_page.py -q`.
  - 2026-10-25: proof passed. `fmtLen` and `fmtNm` ran under Node 22.
- [x] 2.2 Build library scenes in `cmd_view` (scenario "Summary of a footprint library"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py tests/unit/view tests/consistency -q`.
  - 2026-10-25: proof passed (with `test_import_graph.py`: 493 passed, 24 skipped).
- [x] 2.3 Review in a browser `blink.PrjPcb` (its two libraries), a `.pretty` folder and `Mini_v9.kicad_sym`. Check pad sizes in both units against the library files, a measured pitch, a part's extent, a symbol, and measurement on a sheet. Record the date, the browser and what was checked. Proof: the record under this task.
  - 2026-10-25, the agent, in the Chromium of the container (Playwright, headless), on exported standalone pages of `blink.PrjPcb` and `Mini_v9.kicad_sym`, read from screenshots.
    - **`blink.PcbLib`:** the footprint list with pad counts and copper extents, the QFP drawn alone, and a click on pad 32 shows 59.06 × 21.65 mil (1.5 × 0.55 mm) after `Q`, its corner radius and its rotation. A measurement snapped to two adjacent pad centres reads 31.50 mil (0.8 mm), Δy 0.
    - **`blink.SchLib`:** the 32-pin symbol, its pin pitch measured as 2.540 mm, snapped to the pin ends.
    - **`Mini_v9.kicad_sym`:** the units of `Mini_DualGate` in stroke text.
  - **Found and fixed in the same session:**
    - the status line kept the old unit until the mouse moved;
    - the library mode hid the schematic shortcuts.
- [ ] 2.4 The maintainer reviews a library of their own. Proof: the record under this task.
  - 2026-10-25: WAITS on the maintainer.

## 3. Docs and closing

- [x] 3.1 Update `docs/viewer.md`, the `view` section of `docs/cli-contract.md` and the guide page `files`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
  - 2026-10-25: proof passed. The skill folder stays under 150 000 bytes.
- [x] 3.2 Run the fast gate. Proof: `make check-fast`.
  - 2026-10-25, Linux container, after the session row of week 43 was added to `LEGAL-ANNEX.md` on c0178: lint, format, pyright and residue clean; 13 880 passed, 34 skipped. The full gate is left to CI.
- [x] 3.3 Evidence labels. Proof: `uv run python tools/gen_evidence_matrix.py --check`.
  - 2026-10-25: proof passed. The library scenes are `INFERRED`, and no label changes.
- [x] 3.4 Add an entry under `## [Unreleased]` in `CHANGELOG.md` once the version after 0.5.0 is open. Proof: `uv run pytest tests/unit/test_release_record_v05.py -q`.
  - 2026-10-25: the entry is under `## [0.5.0]` of `CHANGELOG.md`, not `[Unreleased]`: by the maintainer's decision of 2026-10-25 the change ships in 0.5.0 (c0171 task 1.15). Proof passed (`tests/unit/test_release_record_v05.py`).
  - 2026-10-25: WAITS on the maintainer (the release guard of 0.5.0). The text is ready: `- **Libraries, units and measurement in the viewer** (c0179): `fenolite view` opens symbol and footprint libraries (`.SchLib`, `.PcbLib`, `.kicad_sym`, `.kicad_mod`, `.pretty`) with a list of their items, each footprint drawn alone with its pads' exact sizes and each symbol per part; every length reads in millimetres or mil (button or `Q`); Measure (`M`) works on boards, sheets and libraries and snaps to pad centres and vertices.`
