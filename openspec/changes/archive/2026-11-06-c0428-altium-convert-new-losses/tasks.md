# Tasks: c0428

## 1. Arrays

- [x] 1.1 Arrays turned by 180 and 270 degrees; the origin or the shape's corner as the reference point
  (design, Decisions 1 and 2). Proof: `uv run pytest tests/unit/convert/test_embedded_arrays.py -q`.
- [x] 1.2 Look for a referenced document by project path, file name and stored path (Decision 3). Proof:
  `uv run pytest tests/unit/convert/test_embedded_arrays.py tests/unit/api/test_conversion_scope.py -q`.
- [x] 1.3 Copies carry their zones' arc outlines, their models and the referenced board's cut-outs, and
  the ring check explains them (Decision 4). Proof:
  `uv run pytest tests/unit/convert/test_embedded_arrays.py -q -k "models or cutouts or arc or rings"`.

## 2. Board and schematic

- [x] 2.1 Drill layers take user rows. Proof: `uv run pytest tests/unit/convert/test_to_kicad.py -q`.
- [x] 2.2 Duplicate designators keep the schematic (Decision 5). Proof:
  `uv run pytest tests/unit/convert/test_new_losses.py -q`.
- [x] 2.3 Predefined special strings and the parameters of a board's own project (Decision 6). Proof:
  `uv run pytest tests/unit/convert/test_new_losses.py tests/unit/convert/test_project_parameters.py -q`.

## 3. Close

- [x] 3.1 `docs/formats/altium/pcb-document.md`, `docs/formats/altium/project.md`,
  `docs/formats/kicad/project.md`, `docs/evidence/sources.md` (S-1870), `docs/conversion.md`, `CHANGELOG.md`.
- [x] 3.2 Light checks (ruff, ruff format, pyright, generators `--check`, `model_review --check`, residue)
  and the focused tests, each file alone, on 3.13 and 3.11; census pins of rows `-01` to `-07` measured
  (`uv run pytest tests/corpus/test_convert_altium_census.py -q`). The heavy suite and row `-08` are the
  coordinator's combined run at integration.
