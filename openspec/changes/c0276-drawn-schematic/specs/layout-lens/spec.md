## ADDED Requirements

### Requirement: Drawn schematic in the source tree
For a design that loads a drawn schematic, `fenolite sync DESIGN --out DIR --to-source` SHALL extract the built project's sheets and plan the drawn file beside the script when its canonical text differs. With `--freeze-schematic` it SHALL plan `schematic.toml` from a generated schematic, with `drawn.frozen` (info) and a hint to call `design.load_schematic`. The script is never rewritten.

#### Scenario: Wire moved in KiCad
- **GIVEN** a confirmed build of the drawn example whose sheet then gets one wire moved by token edit, its connectivity unchanged
- **WHEN** `fenolite sync examples/drawn/design.py --out B --to-source --dry-run --json` runs
- **THEN** `result.plan` lists `schematic.toml`, and after `--confirm --plan <id>` a new build writes the moved wire

#### Scenario: Freeze the blink
- **GIVEN** a confirmed build of the blink
- **WHEN** `fenolite sync examples/blink_2layer/design.py --out B --to-source --freeze-schematic --dry-run --json` runs
- **THEN** `result.plan` lists `schematic.toml` and `issues` holds `drawn.frozen`

### Requirement: Drawn schematic sync refuses changed nets
Before it plans a drawn file, sync SHALL resolve the extracted sheets and compare them with the recorded circuit. A connectivity difference MUST plan nothing and exit 5 with `drawn.netlist-differs`, because a sync never changes nets; value, footprint and reference edits keep the rules of `edits.toml` (c0250).

#### Scenario: Net changed in KiCad
- **GIVEN** the build whose sheet gets one wire end moved to another pin
- **WHEN** sync runs with `--to-source`
- **THEN** the exit code is 5, `result.plan` lists no `schematic.toml`, and one `drawn.netlist-differs` error names the pin
