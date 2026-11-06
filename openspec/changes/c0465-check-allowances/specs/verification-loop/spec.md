## ADDED Requirements

### Requirement: Allowances in the DRC stage
`drc_stage` SHALL judge the entries of a DRC report against the design's `short` and `antenna` rules (change
c0465), before waivers ("Waivers in the check"). No code is shared with `checks.waivers`.
- The rules MUST be those of the `.fenolite/` model of a built project, as for waivers, with those of the
  board read: a KiCad file holds none.
- A `shorting_items` entry MUST resolve its two items by uuid, through the native ids `item_locations` reads,
  to their design items, and MUST be judged as `copper-check` "Allowed shorts" judges a `copper.short`.
- A `track_dangling` or `via_dangling` entry MUST resolve its item and measure its stub with
  `checks.allowances.stub` (design D3 of change c0465). Within the governing `antenna` rule's `max`, the issue
  MUST take severity `info` and end with ` (stub <length> within <max> of rule <name>)`.
- An entry whose item resolves to no design item or to several MUST stay unchanged, and the stage MUST give
  one info `check.allowance-unresolved` per such entry.
- `summary["allowed"]` MUST count, per code, the entries an allowance accepted, and MUST be absent when none
  was. A stage whose every error was allowed or waived MUST have status `ok`. No entry is removed, and
  evidence does not change.
- `check.allowance-unresolved` MUST be a key of `checks.codes.ISSUE_CODES` with severity `info`, and MUST be
  documented in `docs/cli-contract.md`.

#### Scenario: A stub within the tolerance
- **GIVEN** an authored board with a 1.0 mm and a 2.0 mm open-ended track of net `SIG`, an `antenna` rule of
  `max` 1.5 mm on net `SIG`, and a stored DRC report with one `track_dangling` entry for each track
- **WHEN** `uv run pytest tests/unit/checks/test_drc_allowances_c0465.py -q -n 0` runs `drc_stage` on the
  stored report
- **THEN** the 1.0 mm entry is `info` and ends with `(stub 1mm within 1.5mm of rule SIG_STUB)`, the 2.0 mm
  entry keeps its severity, and `summary["allowed"]` is `{"kicad.drc.track-dangling": 1}`

#### Scenario: A short entry between allowed nets
- **GIVEN** the board of `copper-check` "Two grounds joined" and a stored report with a `shorting_items`
  entry for each short
- **WHEN** the same test runs `drc_stage`
- **THEN** the `AGND`–`DGND` entry is `info` and the `VIN`–`DGND` entry an `error`; an entry whose uuid names no
  item gives `check.allowance-unresolved`

#### Scenario: The stub stops at other copper
- **WHEN** the same test measures the stub of a track that runs 1 mm from its open end to a junction of
  three tracks, of a track ending in a via that joins nothing else, and of a track open at both ends
- **THEN** the stubs are 1 mm, the run from the via to the first other copper, and the whole track
