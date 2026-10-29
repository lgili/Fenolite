## ADDED Requirements

### Requirement: Copper command
`fenolite copper PATH` SHALL plan role copper for a KiCad board or built project (schema `fenolite.copper.v0`, `cli/cmd_copper.py`), a writing command of "Mutation protocol" that writes the board, `.fenolite/role-copper.json` and, when the plan has role rules (`role.sw.*`, `role.hv.*`), the project's `.kicad_dru` together. A `.PcbDoc` and a bad option MUST be `FEN-2001`; `--gate drc` without `kicad-cli` exits 6. `docs/cli-contract.md` MUST document it under `copper`.

#### Scenario: Plan, then write
- **GIVEN** a KiCad build of the buck reference board without its power, switch-node and ground copper
- **WHEN** `uv run pytest tests/unit/cli/test_copper_cmd.py -k plan` runs `fenolite copper <board> --dry-run --json`, then `--confirm --plan <plan_id>`
- **THEN** the first exits 0 with `result.nets` and writes nothing, and the second writes the board and the manifest with both in `receipt`

#### Scenario: Confirmation and refusals
- **WHEN** `fenolite copper <board>` runs without `--dry-run`, and `fenolite copper board.PcbDoc --dry-run` runs
- **THEN** the first exits 4 with `FEN-4001`, the second exits 2 with `FEN-2001` and a hint naming `design.role_copper()`

### Requirement: Copper command without change
When the plan of `fenolite copper` changes nothing on the board, the command SHALL write nothing, give no `plan_id` and report `result.changed` false.

#### Scenario: A run on its own output
- **WHEN** `uv run pytest tests/unit/roles/test_copper_repeat.py` runs `fenolite copper --dry-run` on the board it has just written
- **THEN** `result.changed` is false, no `plan_id` is given and the board's bytes are unchanged
