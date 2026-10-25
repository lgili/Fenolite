## ADDED Requirements

### Requirement: View command shows libraries
`fenolite view` SHALL show the schematic and footprint libraries of a project (`library-viewer`): `PATH` may also be a `.PcbLib`, `.SchLib`, `.kicad_sym`, `.kicad_mod` or `.pretty` folder, and `--doc` may name a library. For a library, `result.summary` SHALL hold `kind` `library`, `lib` (`pcb` or `schematic`), `counts.items` and the item names.

#### Scenario: Summary of a footprint library
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k library` runs `fenolite view tests/data/altium/blink/blink.PrjPcb --doc blink.PcbLib --json`
- **THEN** the exit code is 0, `result.summary.kind` is `library`, `result.summary.lib` is `pcb` and `result.summary.counts.items` is 3
