## MODIFIED Requirements

### Requirement: Copper stage issue codes
`fenolite.checks.codes.ISSUE_CODES` SHALL also hold these keys with these severities ("Check issue codes"), and `docs/cli-contract.md` MUST document each. The build guard (`design-dsl`, "Copper guard before writing") emits the same codes into the `build` envelope, where they pass through unchanged as `design-dsl` "Build issue codes" allows for codes that later requirements add.

| code | severity | when |
|---|---|---|
| `copper.short` | error | copper of two nets touches or overlaps on a shared copper layer |
| `copper.clearance` | error, warning | a gap below the clearance in force; the governing rule sets the severity |
| `copper.zone-overlap` | warning | zones of different nets and equal priority overlap on a shared layer |
| `copper.rules-incomplete` | warning | a clearance rule stayed opaque, a project file was not read, or no rules source was given |
| `copper.item-unsupported` | warning | copper items left out of the check, per kind |
| `copper.clearance-unset` | info | item pairs judged for shorts only, because no clearance is in force |
| `copper.edge-clearance` | error, warning | copper closer to the board edge, a cut-out or a slot than the edge clearance in force; the governing rule sets the severity |
| `copper.hole-in-cutout` | error | a drilled hole breaks into a cut-out or a slot, or crosses the board edge |
| `copper.hole-overlap` | warning | two drilled holes overlap |

#### Scenario: Copper literals are keys
- **WHEN** `uv run pytest tests/unit/checks -k codes` collects every issue-code literal under `src/fenolite/checks/`
- **THEN** each `copper.*` literal is a key of `ISSUE_CODES` with the severities of this table

#### Scenario: Copper codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** the nine `copper.*` codes of this table appear in `docs/cli-contract.md`

#### Scenario: The check never gives info for a finding
- **GIVEN** the boards of `tests/unit/checks/test_copper.py`
- **WHEN** `check_copper` runs on each without any waiver
- **THEN** no `copper.short`, `copper.clearance` or `copper.zone-overlap` issue has severity `info`
