## 0. Entry check

- [x] 0.1 This change adds requirements to `board-viewer`, a capability of the open change c0176, and modifies the living "Capabilities command". Note under this task, with the date, the order of archiving: c0176 first, then c0193. 
  - 2026-10-25: c0176 (open, on `c0176-board-viewer`) adds `board-viewer`; this change adds to it and must be archived after it. Proof passed.
  - 2026-10-25, later: brought into `release-0.5.0` from the maintainer's local branch, after c0176 was archived. The id became c0193 (c0192 is `guide-room`), the module `fenolite.view.findings` (c0189's review marks hold `fenolite.view.review`), and the source S-0816 (S-0815 is the BOM document of c0190). 

## 1. Altium body models

- [x] 1.1 Measure the placement of embedded models on the eight public PCB documents of the corpus.
  - Count the bodies whose placed model matches the stored outline and heights, for a bottom half turn about x and about y, and with and without the rotations of the `Models/Data` record.
  - Add the rows to `docs/formats/altium/pcb-bodies.md`, the source to `docs/evidence/sources.md` and `H-A-BODY-MODEL-PLACE` to `docs/hypotheses.md`.

  Proof: `uv run python tools/gen_evidence_matrix.py --check`.
  - 2026-10-25, eight documents, gmsh 4.15.2: 465 of 472 bodies match as placed. Bottom: 181 of 181 with a half turn about x, 151 about y. With the `Models/Data` rotations applied, 193 of 472. The 7 others are top bodies centred on their outline, whose stored outline or overall height differs from the model's. The stroke text boxes of the same documents are recorded on `pcb-records.md` (decision 12). Proof passed.
- [x] 1.2 Add `BodyModel` and `BodyModelSource` to `backends.base`, `backends.altium.models3d` and `AltiumBackend.body_models` (scenarios "Altium backend is a body model source", "An authored document without models", "Models of a corpus document"). Proof: `uv run pytest tests/unit/backends/test_base_types.py tests/unit/backends/altium/test_models3d.py -q`; `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_bodies.py -k body_models -q`.
  - 2026-10-25: proof passed (with `tests/unit/backends/altium/test_project.py` and `adapter/test_codes.py`, whose pinned lists name the new module and code); the corpus run gives 8 of 8 documents, and `-k body_models` also runs the placement count of `PLACED` (2 min 42 s).

## 2. Meshes and placement

- [x] 2.1 Add `fenolite.view.meshes` (scenario "X3D of an authored model"), with the gmsh run tested where gmsh is installed. Proof: `uv run pytest tests/unit/view/test_meshes.py -q`.
  - 2026-10-25: proof passed; a stand-in script plays gmsh, the real run is the corpus test.
- [x] 2.2 Add `fenolite.view.models.attach_models` (scenario "Placement and fit"). Proof: `uv run pytest tests/unit/view/test_models.py -q`.
  - 2026-10-25: proof passed.

## 3. Review findings

- [x] 3.1 Add `fenolite.view.findings` (scenarios "Corners of authored tracks" and "Silkscreen and copper outside the board"). Proof: `uv run pytest tests/unit/view/test_findings.py tests/unit/test_import_graph.py -q`.
  - 2026-10-25: proof passed. On a local 260-part Altium board of the maintainer: 1 acute corner (a track doubling back), 16 tracks off-angle, 0 zone corners, 29 / 19 / 22 silkscreen findings, one cluster of 165 vias outside the board, in 1.8 s.

## 4. Command, page and capabilities

- [x] 4.1 Extend `fenolite view` (scenarios "Findings in the summary", "Port in use", "A findings file is drawn"), and add `gmsh` to `detect_tools` (the MODIFIED "Capabilities command"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py tests/unit/cli/test_capabilities.py tests/consistency -q`.
  - 2026-10-25: proof passed (`tests/unit/cli/test_explain_cmd.py` too: `altium.import.model-unread` has its entry).
- [x] 4.2 The page: the findings panel by group, the snap, and the meshes in 3D (scenario "Snap targets in the page"). Proof: `uv run pytest tests/unit/view/test_page.py -q`.
  - 2026-10-25: proof passed; the page script is checked with `node --check`.
- [x] 4.3 Review the page in a browser on an Altium board with embedded models. Check the findings panel, an item's fit, the snap to a centre and to an edge, and the 3D with models, fitted bodies and extruded ones. Record the date, the browser and what was checked. Proof: the record under this task.
  - 2026-10-25, the Chromium-based browser pane of the maintainer's desktop app, macOS, `fenolite view --serve` on a local Altium project of the maintainer (two boards, schematics, libraries; not in the repository). Checked:
    - the findings panel (eleven groups with counts, a group hidden by its box, an item listed and fitted with its box);
    - a findings file of another tool drawn at its place;
    - the snap to a pad centre and to a pad edge;
    - the 3D, with 168 models placed as the file places them, 10 fitted and 6 bodies extruded;
    - the click on a 3D body, and `View.ZoneEdge`.
  - Three defects were found and fixed in the session: gmsh writes unescaped `&` in X3D names (read with expressions); a gmsh launcher installed by a Python package needs the interpreter beside it; Altium texts need their own anchor and width (decision 12).

## 5. Docs and closing

- [x] 5.1 Update `docs/viewer.md` and the `view` section of `docs/cli-contract.md`, and run `tools/gen_agent_guide.py` for the options on the generated page `commands`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
  - 2026-10-25: proof passed; the help of the new options is short, the skill folder stays under its budget.
- [x] 5.2 Run `make check-fast`. Proof: its result recorded under this task.
  - 2026-10-25, macOS: lint, format, pyright and residue clean (0 hits in 3 776 files). Tests: 13 817 passed, 74 skipped, 2 failed.
    - `tests/unit/lens/test_altium_pcb_complete.py::test_altium_samples_of_earlier_changes_keep_their_bytes` fails as c0176 recorded on a clean `release-0.5.0`.
    - `tests/unit/cli/test_explain_cmd.py::test_table_is_complete` asked for the entry of the new code, which was added.
    - After the entry, the zone-edge layer and the 3D click: `make lint format types residue` clean, and 726 tests of the changed areas passed. The full gate is left to CI.
- [x] 5.3 The `CHANGELOG.md` entry waits, as c0176's does, for the version after 0.5.0. The text is recorded under this task. Proof: `uv run pytest tests/unit/test_release_record_v05.py -q`.
  - 2026-10-25: WAITS on the maintainer, as c0176's entry does. The text is ready: `- **Viewer review aids** (c0193): `fenolite view` draws review findings by group (45° corners, silkscreen, copper outside the board, open connections) and findings files of other tools, measures with snap, and shows an Altium board's embedded 3D models (meshed by gmsh as a separate process, placed as the native tool places them); `BodyModelSource` is a new backend protocol.`
  - 2026-10-25, later: the maintainer's decision of that day puts everything done in `0.5.0`, so the entry is under `### Added` of `[0.5.0]` and the change has its row in `docs/release/v0.5.md`. Proof passed.
