## ADDED Requirements

### Requirement: Stack-up note in exports
`fenolite export` SHALL note when a kind it runs states a stack-up and the board holds none, because KiCad then states its own default (`H-K-STACKUP-DEFAULT`).
- `exports.plan.STACKUP_KINDS` MUST hold `gerbers`, whose job file states the stack-up. When a selected kind is in it and the read board's `Board.stackup` is `None`, one `export.stackup-default` (info; `where` the kind) MUST say that KiCad states there 0.035 mm copper, 0.01 mm masks, equal FR4 dielectrics that fill the board thickness, and the finish `None`; its hint MUST name `design.stackup()` and KiCad's Board Setup.
- `exports.codes.ISSUE_CODES` MUST gain `export.stackup-default` with severity `info`. An info MUST NOT stop the writes: by `cli-contract` "Export command" (MODIFIED by this change, on the text of `export-documents`) only an issue of severity `error` stops them.
- The note MUST NOT change the files that `kicad-cli` writes.

#### Scenario: Board without a stack-up
- **GIVEN** a fake `kicad-cli` 10.0.6 that writes the Gerbers and the job file of `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k stackup` runs `fenolite export <board> --out fab --gerbers --dry-run --json`
- **THEN** the exit code is 0, the issues hold one `export.stackup-default` info with `where` `gerbers`, and the plan lists every file the fake wrote

#### Scenario: Board with a stack-up
- **GIVEN** the same fake and the copy of `two_layer.kicad_pcb` with a complete node of "Stack-up thicknesses in analyze"
- **WHEN** the same command runs
- **THEN** the issues hold no `export.stackup-default`

#### Scenario: Other kinds
- **WHEN** the command runs on `two_layer.kicad_pcb` with `--drill --pos` only
- **THEN** the issues hold no `export.stackup-default`
