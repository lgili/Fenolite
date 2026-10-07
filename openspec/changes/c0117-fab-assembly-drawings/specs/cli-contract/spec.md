## ADDED Requirements

### Requirement: Drawing options of the export command
`fenolite export` SHALL take `--fab-drawing`, `--assembly-drawing` and `--drawing-spec FILE`, and SHALL run the drawing kinds of `manufacturing-exports` beside the kinds of the requirement "Export command", under its board, tool, source, write and exit-code rules.
- Each flag MUST select its kind. A drawing kind MUST count as a selected kind for the rule that a call selecting none exits 2, and `--all` MUST NOT select one. `result.kinds` MUST list the drawing kinds after the other selected kinds, `fab-drawing` first.
- `--drawing-spec` MUST be read before any tool runs. Without a drawing flag it MUST exit 2 with `FEN-2001`; a missing file MUST exit 3 with `FEN-3001`; a `SpecError` MUST exit 3 with `FEN-3004` and list its problems in the message. Without the option, `drawing_spec.DEFAULT` MUST apply.
- `cmd_export` MUST compute each page's obstacles: through `templates.layout` for the spec's or the project's drawing sheet, through `drawing.default_sheet_obstacles` when the project names none. A sheet that cannot be read or built MUST give `drawing.sheet-unread` (error).
- A drawing issue of severity error MUST make the command plan no write and exit 5, as `export.failed` does; an info or a warning MUST NOT change the exit code.
- `result.drawings` MUST hold one object per page, in the order fabrication, assembly top, assembly bottom, with `kind`, `path`, `paper`, `portrait`, `sheet` (`spec`, `project` or `kicad-default`) and `blocks` (each with `name`, `at` and `size` in integer nanometres), and, for an assembly page, `side` and `designators_added`. No value MUST hold a temporary path, the home directory or a date.
- With a drawing kind selected, the envelope's evidence MUST be `Evidence.combine` of `exports.EVIDENCE` and `exports.drawings.EVIDENCE`, with the oracle `kicad-cli <version>`.
- `docs/cli-contract.md` MUST describe the three options and `result.drawings`, and `docs/drawings.md` the spec file, the pages, the tables and the seven `drawing.*` codes.

#### Scenario: Plan, then write
- **GIVEN** a fake `kicad-cli` 10.0.6 that writes the files of both drawing kinds
- **WHEN** `uv run pytest tests/unit/cli/test_export_drawings.py -k plan` runs `fenolite export <board> --out fab --fab-drawing --assembly-drawing --dry-run` and then the same with `--confirm`
- **THEN** the first exits 0, plans the drawing files under `fab/drawings/` and writes nothing, and the second writes them with a receipt that lists each file with its SHA-256

#### Scenario: A spec without a drawing flag
- **WHEN** `fenolite export <board> --out fab --gerbers --drawing-spec d.toml --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: An invalid spec runs no tool
- **GIVEN** `d.toml` holding `[page] paper = "B9"` and `subprocess.run` patched to record its calls
- **WHEN** `fenolite export <board> --out fab --fab-drawing --drawing-spec d.toml --dry-run` runs
- **THEN** the exit code is 3, stderr carries `FEN-3004` naming `page.paper`, and no `kicad-cli` run was made

#### Scenario: No room writes nothing
- **GIVEN** `d.toml` with `[page] paper = "A4"` and a board whose outline reaches y = 279 mm
- **WHEN** `fenolite export <board> --out fab --fab-drawing --drawing-spec d.toml --confirm` runs
- **THEN** the exit code is 5, the issues hold `drawing.no-room`, and `fab` does not exist

#### Scenario: The reply describes the pages
- **WHEN** the first command of "Plan, then write" runs with `--json`
- **THEN** `result.drawings` holds one object per page produced, each with its `paper`, `sheet` `kicad-default` and its blocks, and `result.kinds` ends with `fab-drawing`, `assembly-drawing`
