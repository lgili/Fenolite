## ADDED Requirements

### Requirement: Import record marks a copy
`PROVENANCE.json` written by the import SHALL hold `"copy": true`. `fenolite.importer.provenance.copy_mode(data)` SHALL return whether a provenance value marks a copy: an import record (`schema` `fenolite.import-provenance.v0`), or a record whose member `import` is one, whose `copy` is not `false`. A record without the member counts as a copy.

#### Scenario: Written and read
- **WHEN** `uv run pytest tests/unit/importer/test_copy_mode.py` imports the authored two-sheet project
- **THEN** the planned `PROVENANCE.json` holds `copy` `true`, `copy_mode` of it is true, of a library record holding it as `import` true, of a record with `copy` `false` false, and of a provenance file without an import record false

### Requirement: Pads on no net in the vendored symbols
The symbol drawn for a vendored footprint SHALL have no pin for a pad number that is on no net in every instance of that footprint in the source, so the build leaves those pads on no net; a number on a net in any instance keeps its pin.

#### Scenario: Shield pads stay on no net
- **GIVEN** an authored board whose connector has two pads `0` on no net beside numbered pads on nets
- **WHEN** `uv run pytest tests/unit/importer/test_no_net_pads.py` imports it and builds the emitted code with its schematic
- **THEN** the symbol has no pin `0`, both pads `0` of the built board are on no net, and level 2 against the source reports no difference

### Requirement: Outline width and layer table reported
The import SHALL report the unexpressed kind `outline-width` for the root `Edge.Cuts` items whose stroke width is not the 0.1 mm a DSL board writes, and `layer-table` when the names of the source's non-copper layers differ from those of the DSL board of its copper count.

#### Scenario: Wide outline and short layer table
- **GIVEN** an authored board whose outline is drawn 0.2 mm wide and whose layer table has no `Eco1.User` and `Eco2.User`
- **WHEN** `uv run pytest tests/unit/importer/test_unexpressed_c0281.py` imports it with `--allow-lossy --dry-run`
- **THEN** `result.unexpressed` holds `outline-width` with the count of outline items and `layer-table` naming the missing layers, and without `--allow-lossy` the exit code is 7
