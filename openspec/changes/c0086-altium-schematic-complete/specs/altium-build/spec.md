## ADDED Requirements

### Requirement: Readable schematic in an Altium build
`fenolite build --target altium` SHALL write symbol graphics, the module tree, directions, buses, parameters and texts as `altium-schematic-writer` requires, and the nets and designators of a design MUST be the ones the build gave before this change.
- `--altium-directions on|off` (default `on`) MUST select the directions. `--altium-sheets flat|modules` keeps its meaning.
- `result.schematic` MUST hold the count of sheets, of symbols drawn from graphics and of symbols simplified.

#### Scenario: Nets unchanged
- **WHEN** `uv run pytest tests/unit/lens/test_altium_schematic_complete.py -k nets_unchanged` builds every example script before and after
- **THEN** the netlist read from each built project equals the recorded one

#### Scenario: Tree sample
- **WHEN** `uv run pytest tests/unit/lens/test_altium_schematic_complete.py -k tree` builds the sample
- **THEN** the built files equal the committed `tests/data/altium/tree/`, and `result.schematic.sheets` is 4
