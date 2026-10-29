## ADDED Requirements

### Requirement: Copper command
`fenolite copper PATH` SHALL plan role copper for a KiCad board or built project (schema `fenolite.copper.v0`, `cli/cmd_copper.py`), a writing command of "Mutation protocol" that writes the board and `.fenolite/role-copper.json` together. A `.PcbDoc` and a bad option MUST be `FEN-2001`; `--gate drc` without `kicad-cli` exits 6. `docs/cli-contract.md` MUST document it under `copper`.

#### Scenario: Plan, then write
- **GIVEN** a copy of the KiCad build of `examples/roles/buck_shunt/good.py` without its power zones
- **WHEN** `uv run pytest tests/unit/cli/test_copper_cmd.py -k plan` runs `fenolite copper <board> --dry-run --json`, then `--confirm --plan <plan_id>`
- **THEN** the first exits 0 with `result.nets` and writes nothing, and the second writes the board and the manifest with both in `receipt`

#### Scenario: Confirmation and refusals
- **WHEN** `fenolite copper <board>` runs without `--dry-run`, and `fenolite copper board.PcbDoc --dry-run` runs
- **THEN** the first exits 4 with `FEN-4001`, the second exits 2 with `FEN-2001` and a hint naming `design.role_copper()`
