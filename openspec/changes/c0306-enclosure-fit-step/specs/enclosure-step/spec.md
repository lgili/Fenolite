## ADDED Requirements

### Requirement: Enclosure footprint
`fenolite enclosure place` SHALL add one footprint `Fenolite_Enclosure:ENC_<stem>` without pads, courtyard or `fenolite.path`, with the attributes `board_only`, `exclude_from_pos_files`, `exclude_from_bom` and `allow_missing_courtyard`, locked, holding one `model` whose offset carries only Z and whose rotation is zero. It MUST also plan the footprint in `lib/Fenolite_Enclosure.pretty/`.

#### Scenario: The written footprint
- **GIVEN** the blink built in `tmp_path` and a STEP file `box.step`
- **WHEN** `uv run pytest tests/unit/cli/test_enclosure_place.py -k footprint` runs `fenolite enclosure place <dir> --step box.step --at 30mm,20mm --z 1.6mm --rot 90 --confirm`
- **THEN** the board holds one footprint `ENC1` at (30 mm, 20 mm) and 90°, with no pad, the three exclusion attributes and one model `${KIPRJMOD}/enclosure/box.step` with offset (0, 0, 1.6), and a rebuild of the script keeps it with `layout.board-only`

### Requirement: Enclosure STEP stays local
The command SHALL plan a copy of the STEP to `<board folder>/enclosure/<file>` unless `--in-place` is given, SHALL refuse a file that does not start with `ISO-10303-21;` with exit 3 and `FEN-3010`, and SHALL give `enclosure.step-local` (info) on every plan. No reply value MAY hold an absolute path.

#### Scenario: Not a STEP file
- **GIVEN** a text file `box.step` that starts with `solid box`
- **WHEN** `fenolite enclosure place <board> --step box.step --at 0mm,0mm --dry-run --json` runs
- **THEN** the exit code is 3, stderr carries `FEN-3010`, and nothing is planned

#### Scenario: In place
- **WHEN** the command runs with `--in-place --dry-run --json`
- **THEN** no copy is planned, `result.place.model` is `<in-place>/box.step`, and the issues hold one `enclosure.step-local`

### Requirement: Enclosure reference handling
A second `place` with the reference of an enclosure footprint SHALL replace that footprint and its model with `enclosure.replaced` (info). A reference held by any other footprint MUST give `enclosure.ref-taken` (error), plan nothing and exit 5.

#### Scenario: Reference taken
- **GIVEN** a board whose `R1` is a resistor
- **WHEN** `fenolite enclosure place <board> --step box.step --at 0mm,0mm --ref R1 --dry-run` runs
- **THEN** the exit code is 5, the issues hold `enclosure.ref-taken` with `where == "R1"`, and `result.plan` is empty

### Requirement: Combined STEP and render
After `enclosure place`, `fenolite export --step` SHALL locate the copied STEP as a `project` model and write one STEP holding the board, its parts and the box; `fenolite render --png` SHALL show the box. `result.place.filter` MUST give a `--component-filter` value that leaves the box out.

#### Scenario: The box reaches the STEP
- **GIVEN** the blink with a box STEP that `kicad-cli pcb export step --board-only` wrote from a board authored for Fenolite, placed with `enclosure place`
- **WHEN** `uv run pytest tests/kicad/enclosure/test_combined_step.py` runs `fenolite export <dir> --out fab --step --confirm` with `kicad-cli` 9.0.x and 10.0.x
- **THEN** `result.models` lists the box with source `project`, and the STEP text holds the box's product name and one more `MANIFOLD_SOLID_BREP` than the export without the footprint, or the 9.0 result is recorded in `H-K-ENCL-STEP` and `docs/enclosures.md`

### Requirement: Altium enclosure checklist
`docs/enclosures.md` SHALL hold a numbered checklist that places the same STEP as an Altium 3D Body at the pose of `result.place`, citing S-0950 to S-0953, and SHALL say that its result is an author report (`H-A-ENCL-IMPORT`).

#### Scenario: Checklist present
- **WHEN** `uv run pytest tests/unit/docs/test_enclosures_doc.py -k checklist` reads `docs/enclosures.md`
- **THEN** the section "Altium" holds numbered steps naming Place » 3D Body, the X, Y, rotation and Z of `result.place`, and the hypothesis id
