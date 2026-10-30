## ADDED Requirements

### Requirement: Enclosure place command
`fenolite enclosure place PATH --step FILE --at X,Y [--z Z] [--rot DEG] [--ref REF] [--in-place] [--drc] [--kicad-cli PATH]` SHALL be registered by `cli/cmd_enclosure.py` with `mutates=True`, take a KiCad board, follow the mutation protocol and answer with `result.place`. An Altium input or a length without a unit MUST exit 2 with `FEN-2001`. `FEN-3010` MUST be in the error registry.

#### Scenario: Altium input refused
- **WHEN** `fenolite enclosure place tests/data/altium/blink/blink.PcbDoc --step box.step --at 0mm,0mm --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: The reply of a plan
- **WHEN** `uv run pytest tests/unit/cli/test_enclosure_place.py -k reply` runs the command with `--at 30mm,20mm --z 1.6mm --dry-run --json`
- **THEN** `result.place` holds `ref`, `footprint`, `model`, `at` `{x: 30000000, y: 20000000}`, `z` `1600000`, `rotation` `0` and `filter`, and the plan lists the board, the library footprint and the copy of the STEP

#### Scenario: Error code registered
- **WHEN** `uv run fenolite explain FEN-3010 --json` runs
- **THEN** the exit code is 0 and `result.meaning` says the file is not an ISO 10303-21 file
