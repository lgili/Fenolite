## ADDED Requirements

### Requirement: Library action words
`fenolite library` SHALL read its first positional as an action when it is `symbol`, `check`, `review`, `import`, `propose` or `seed`, and as the board path of the existing form otherwise. An action that is not available in the installed version MUST exit 2 with `FEN-2001`. The forms `fenolite library BOARD --out LIB.pretty` and `--diff LIBRARY` MUST behave as before.

#### Scenario: Existing form unchanged
- **WHEN** `fenolite library board.kicad_pcb --out lib.pretty --dry-run --json` runs on the example board
- **THEN** its result and plan equal those of the base commit

#### Scenario: Reserved action
- **WHEN** `fenolite library seed --json` runs before c0266 lands
- **THEN** it exits 2 with `FEN-2001` and writes nothing

### Requirement: Library symbol command
`fenolite library symbol PINS... --out FILE` SHALL plan one symbol library holding the generated symbols of the given pin tables: a `.kicad_sym` (with `--target 9|10`) or a `.SchLib`. It MUST use dry-run, confirmation, staged plans and receipts, list per symbol its units, pins per side and findings, and refuse an absolute `--out` or another suffix with `FEN-2001`.

#### Scenario: Plan and write
- **WHEN** `fenolite library symbol pins/EXB6202.toml --out lib/Example.kicad_sym --dry-run --json` runs and is confirmed with its plan id
- **THEN** the dry run writes nothing and lists one symbol and one variant, and the confirmation writes exactly the staged bytes with their receipt hash

#### Scenario: Wrong suffix
- **WHEN** `--out lib/Example.lib` is given
- **THEN** the command exits 2 with `FEN-2001` and writes nothing
