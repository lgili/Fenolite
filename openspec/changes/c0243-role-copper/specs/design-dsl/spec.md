## ADDED Requirements

### Requirement: Role copper in the DSL
`Design.role_copper(*, kinds=…, layers=None, ground_layers=None, ground_fill="reference", connection=None, stitch_pitch=None, temp_rise=None, widen=None, corridors=True, keep=(), regenerate=())` SHALL record plain data, returned by `fenolite.dsl.role_copper(design)`. A second call, an unknown kind, mode or layer MUST raise `DslError`. The build MUST resolve it after the roles, script copper and generated records.

#### Scenario: Recorded and built
- **WHEN** `uv run pytest tests/unit/dsl/test_role_copper.py` records valid and invalid calls and builds `examples/roles/buck_shunt/good_roles.py` for KiCad
- **THEN** `role_copper(design)` holds the record, a second call or `kinds=("motor",)` raises `DslError`, and the board holds locked zones whose names start with `role.`

## MODIFIED Requirements

### Requirement: Generated copper codes
The codes `kicad.generate.altium`, `unknown`, `off-board`, `no-hole`, `no-plan`, `no-zone`, `size-missing`, `pieces`, `name-taken`, `crossing` (error), `unplaced`, `band-narrow`, `encloses` and `stitch-short` (warning) SHALL be the table `GENERATE_ISSUE_CODES` of `fenolite.backends.kicad.generate`, each explained by `fenolite explain`. An error of a call MUST create nothing for that call and stop the build's write. `kicad.generate.altium` MUST be given only with `--copper-from`.

#### Scenario: Every code is explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs
- **THEN** every `kicad.generate.*` code has an entry

#### Scenario: Generated copper reaches Altium
- **WHEN** `uv run pytest tests/unit/lens/test_altium_generated.py` builds a blink variant with `band` and `stitch_pieces` for `--target altium --dry-run`, then again with `--copper-from` a KiCad build
- **THEN** the first exits 0 with the band's polygon and vias in `result.copper`, and the second exits 5 with `kicad.generate.altium`
