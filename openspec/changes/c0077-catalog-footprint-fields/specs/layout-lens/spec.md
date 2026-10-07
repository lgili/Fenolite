## ADDED Requirements

### Requirement: Kept footprints gain missing mandatory fields
A rebuild SHALL give a kept footprint the `Reference` or `Value` field that its board node lacks, taken from the built copy of the footprint, so that a board written before the generated fields existed is repaired by its next build.
- The field MUST be added before the node's first field, `Reference` before `Value`, with the id, the uuid and the placement of the built copy's field, and with the script's reference or value as its text.
- A field that the board's node has MUST NOT be changed by this requirement: the precedence of `fenolite.lens.fields.merge_fields` stays, and a request of `Part.field` applies to an added field as an unlocked request applies to a library field.
- Everything else of the kept node MUST stay: position, rotation, side, pads, the other properties and their order.
- A re-placed footprint is the built copy and already holds both fields.
- The build MUST report no issue for an added field. `docs/lens.md` MUST describe the rule under "Footprint fields".

#### Scenario: Board written before the fields existed
- **GIVEN** the catalog blink of `tests/_catalog_design.py` built into `tmp_path`, routed by its scripted tracks, and then every `Reference` and `Value` property removed from the board's footprints by a token edit in the test
- **WHEN** `uv run pytest tests/unit/cli/test_catalog_only.py -k older_board` builds the design again over that folder
- **THEN** each footprint holds both fields again with the script's reference and value, and each footprint's position, rotation and pad nets and every track equal the ones before the rebuild

#### Scenario: A field edited in KiCad stays
- **GIVEN** the same board with the `Reference` field of `R1` moved by 2 mm in the test
- **WHEN** the design is built again
- **THEN** that field keeps its moved position

#### Scenario: A second rebuild changes nothing
- **WHEN** the repaired project is built once more with `--dry-run`
- **THEN** the plan holds no file with changed bytes
