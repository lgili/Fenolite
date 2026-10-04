## ADDED Requirements

### Requirement: Contract page names every command
`docs/cli-contract.md` SHALL describe every registered command that is not hidden: the page MUST hold the text `fenolite <name>`, or a level-2 heading that is the command's name with or without backticks. `tests/consistency/test_cli_consistency.py` SHALL check this over the command registry with `undescribed_commands(names, page)`, so a command added later fails the suite until the page describes it.
- The page MUST hold a section `## template` that states the command line `fenolite template build SPEC --target kicad -o OUT`, that the command is mutating and runs no tool, the keys of `result` (`sheet`, `target`, `kicad_version`, `drawn`, `output`), the exit codes 0, 2, 3 (`FEN-3001`, `FEN-3004`), 4 and 7, and the evidence (`INFERRED`, `H-K-WKS-CORNER`).
- The page MUST name every code of `fenolite.templates.ISSUE_CODES` in backticks.
- The section MUST describe the command as it behaves: each statement is checked against a run of the command before the section is merged.

#### Scenario: Every command is described
- **WHEN** `uv run pytest tests/consistency/test_cli_consistency.py -k contract_names` reads the registry and the page
- **THEN** it passes, and `undescribed_commands(["template"], page)` returns `["template"]` for a copy of the page without the `template` section

#### Scenario: Template codes are listed
- **WHEN** `uv run pytest tests/consistency/test_cli_consistency.py -k template_codes` runs
- **THEN** every code of `fenolite.templates.ISSUE_CODES` is found in backticks on the page

#### Scenario: Section matches a run
- **WHEN** `uv run fenolite template build src/fenolite/templates/examples/iso5457_generic.sheet.toml --target kicad -o out.kicad_wks --json --dry-run` runs
- **THEN** the exit code is 0, `result` holds exactly the keys `sheet`, `target`, `kicad_version`, `drawn`, `output` and `plan`, the evidence is `INFERRED` with `H-K-WKS-CORNER`, and nothing is written
