## 0. Entry check

- [x] 0.1 Read c0176's and c0177's specs, `docs/formats/kicad/schematic.md` and `libraries.md`, and `LEGAL.md` block A. Note under this task, with the date, the maintainer's choice of colour source and the facts the theme reader needs. Proof: `openspec validate c0178-native-themes --strict --no-interactive`.
  - 2026-10-25: asked in the session, the maintainer chose "a palette in KiCad's manner, plus the user's own theme". The other options were transcribing KiCad's built-in values, which block A forbids for GPL sources, or the user's theme alone.
  - The theme facts come from S-0813 and S-0814: the form of the theme file, the key names, the `colors` folder and the settings folders. The placement rule comes from `schematic.md` (`H-K-SCH-PINFRAME`, `H-K-SCH-PINFRAME-ORDER`).
  - This change is on `c0177-schematic-viewer` (`39b7e7a`). Proof passed.

## 1. Themes

- [x] 1.1 Write `docs/formats/kicad/color-theme.md`, add its sources and the hypothesis `H-K-THEME`. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py -q`.
  - 2026-10-25: proof passed (with `test_evidence_matrix_page.py`: 70 passed).
- [x] 1.2 Add `fenolite.view.themes` with the two palettes, the theme per backend, the theme file reader and the folder lookup (scenarios "Each backend gets its palette" and "An authored theme file"). Proof: `uv run pytest tests/unit/view/test_themes.py -q`.
  - 2026-10-25: proof passed (8 tests).

## 2. KiCad schematics

- [x] 2.1 Add `fenolite.view.kicad_schematic` (scenarios "Counts and pin points of a KiCad sheet" and "Wires carry their label's net"). Proof: `uv run pytest tests/unit/view/test_kicad_schematic.py -q`.
  - 2026-10-25: proof passed (6 tests). On three sheets, every visible pin's line starts at `schlayout.pin_point`, which `test_pin_frame_oracle.py` checks against `kicad-cli`. Every `.kicad_sch` under `tests/` builds a scene without an error.
- [x] 2.2 Mark `.kicad_sch` as viewable (scenario "A lone KiCad sheet"). Proof: `uv run pytest tests/unit/view/test_project.py -q`.
  - 2026-10-25: proof passed.

## 3. Page and command

- [x] 3.1 Theme the page (scenario "The page reads the theme"). Proof: `uv run pytest tests/unit/view/test_page.py -q`.
  - 2026-10-25: proof passed.
- [x] 3.2 Add `--theme` and the KiCad sheet scenes to `fenolite view` (scenario "A theme file on a KiCad board"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py tests/unit/view tests/consistency -q`; `uv run python tools/gen_agent_guide.py --check`.
  - 2026-10-25: proof passed (444 passed, 24 skipped). The skill folder holds fewer than 150 000 bytes after the paragraph of the guide page `files` was shortened.
- [x] 3.3 Review in a browser a KiCad project (`tests/data/acceptance/board_40parts_t10/` or the schematic fixtures) and the Altium test projects. Record the date, the browser and what was checked. Proof: the record under this task.
  - 2026-10-25, the agent, in the Chromium of the container (Playwright, headless), on exported standalone pages, read from screenshots:
    - **`board_40parts_t10`:** the navy board with red and blue copper and the KiCad palette's note.
    - **`board6.PcbDoc`:** the black board with the Altium palette.
    - **`flat.kicad_sch`, KiCad palette:**
      - the A4 paper with its frame, zones and title block;
      - the dotted grid and green wires with a junction;
      - dark red symbols on pale yellow bodies;
      - global labels as flags;
      - stroke texts;
      - the power symbols.
    - **`flat.kicad_sch`, an authored dark theme file:** every role took the file's colours.
  - No defect was found that needed a change of code. One note was misleading: the Altium board's note offered `--theme`, which only applies to KiCad documents, and was corrected.
- [ ] 3.4 The maintainer reviews a KiCad project of their own, with and without their KiCad theme. Proof: the record under this task.
  - 2026-10-25: WAITS on the maintainer. `H-K-THEME` stays open until a theme file that KiCad wrote has been read.

## 4. Docs and closing

- [x] 4.1 Update `docs/viewer.md` and the `view` section of `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/agent -q`.
  - 2026-10-25: proof passed (81 passed, 12 skipped).
- [x] 4.2 Run the fast gate. Proof: `make check-fast`.
  - 2026-10-25, Linux container: lint, format, pyright and residue clean; 13 871 passed, 34 skipped. The full gate is left to CI.
- [x] 4.3 Evidence labels. Proof: `uv run python tools/gen_evidence_matrix.py --check`.
  - 2026-10-25: proof passed. The theme file and the KiCad sheet scene are `INFERRED`, and no other label changes.
- [ ] 4.4 Add an entry under `## [Unreleased]` in `CHANGELOG.md` once the version after 0.5.0 is open. Proof: `uv run pytest tests/unit/test_release_record_v05.py -q`.
  - 2026-10-25: WAITS on the maintainer (the release guard of 0.5.0). The text is ready: `- **Native looks** (c0178): `fenolite view` draws each document in the look of its tool: KiCad boards and sheets in a palette in KiCad's manner (or the user's KiCad colour theme with `--theme`), Altium boards in a palette in Altium's manner, and Altium sheets in their own colours; KiCad schematics are now drawn — symbols, pins, wires, labels, power symbols, sheets, frame and title block, stroke texts — with net highlight, Navigator and cross-probing.`
