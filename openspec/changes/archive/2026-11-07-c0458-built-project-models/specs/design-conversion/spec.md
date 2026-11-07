## ADDED Requirements

### Requirement: Model paths read as KiCad reads them
The direction from KiCad to Altium SHALL find the file of a footprint's `model` child as KiCad finds it ("Models of a KiCad board in an Altium target", change c0449; `docs/formats/kicad/libraries.md`, "3D models"): `${KIPRJMOD}` or `$(KIPRJMOD)` is the folder of the source board, a relative path is read from that folder, an absolute path where it is, and a path that climbs out of the folder is followed (change c0458).
- A path under a variable other than `KIPRJMOD`, and a KiCad embedded file, MUST keep their c0449 losses.
- An absent file MUST be lost with the reason "the model file is not found in the project folder" when the path lies inside the folder, and "the model file is not found at its path" otherwise. A Windows drive path read on another system names no file.

#### Scenario: Model paths outside the project
- **GIVEN** a project folder and, beside it, a folder holding a STEP box
- **WHEN** `uv run pytest tests/unit/convert/test_built_models.py -k paths` resolves the box's absolute path, `${KIPRJMOD}/../shared/box.step`, `$(KIPRJMOD)/../shared/box.step` and `../shared/box.step`
- **THEN** each names the box; an absent file outside the folder gives "not found at its path", inside it "not found in the project folder"

#### Scenario: A built design converted to Altium
- **GIVEN** the build of "A built project keeps its own models" (capability design-dsl)
- **WHEN** `uv run pytest tests/unit/convert/test_built_models.py -k copies` converts its board to Altium
- **THEN** the row `model` has `written` 1, and the two official models are lost under their variable
