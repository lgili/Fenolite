## ADDED Requirements

### Requirement: View command shows schematics
`fenolite view` SHALL show the Altium schematic documents of a project as it shows its boards (`schematic-viewer`): `PATH` may also be a single `.SchDoc`, and `--doc` may name a schematic.
- With `--doc` naming a schematic, and without `--serve` and `--export`, the reply MUST hold `summary` with `kind` `"schematic"` and the count of each object kind, and nothing MUST be written.
- `--export FILE` MUST embed the scene of every viewable schematic beside the boards.

#### Scenario: Summary of a sheet
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k schematic` runs `fenolite view tests/data/altium/hier/altium_hier.PrjPcb --doc altium_hier.SchDoc --json`
- **THEN** the exit code is 0, `result.summary.kind` is `"schematic"`, `result.summary.counts.components` equals the sheet's component count, and nothing is written
