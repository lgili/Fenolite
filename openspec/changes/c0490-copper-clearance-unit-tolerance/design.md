# Design: c0490

## D1 The rule value stays the document's

Today `AltiumBackend.design_rules` returns `_with_unit_slack(design)`: every `clearance` rule with
`min - CLEARANCE_SLACK_NM`. The check then prints that lowered `min` as the clearance in force, so a 0.2 mm
rule shows as 0.199991 mm.

Instead `design_rules` leaves the rules as read and sets
`clearance_tolerance = GRID_TOLERANCE_UNITS · FILE_UNIT_NM`, rounded up to whole nanometres as
`CLEARANCE_SLACK_NM` is today. `checks.copper` already subtracts `clearance_tolerance` in `_Judge._too_close`
and `_hole_clearance_findings` (c0281, c0420). So the verdicts stay the same for the same tolerance, and
only the message changes.

`_with_unit_slack` is removed. Its one other effect, leaving a rule at or below the slack untouched, follows
from `value <= 0` in `_too_close`.

## D2 Where the shortfall comes from (task 1.1)

The slack in force covers the import's rounding: up to 3.18 nm per item, 9 nm per pair with Altium's
observed 8.89 nm (`ALTIUM_PASSED_UNITS`). A shortfall of several units means one of these:

1. **The document.** Altium saved copper closer than its own rule, and its DRC passes it (as on public
   row `-03`, `ALTIUM_PASSED_UNITS`).
2. **The rule text.** A rule saved in mil with four decimals (`GAP=9.8425mil`) reads as a value that is not
   the metric rule the user typed.
3. **A computed pour.** Fenolite's pour (c0215, c0463) wrote the copper. Then this is a pour defect: it
   goes to c0496 or a new change, not into the tolerance.

Task 1.1 builds an authored document for each case with Fenolite's writer and measures the shortfall of
each pair kind. `GRID_TOLERANCE_UNITS` is the least whole number of units that covers cases 1 and 2. Its
derivation goes in `import.md`, with hypothesis `H-A-CHK-GRID-TOL`. Case 3 is never covered by the tolerance.

## D3 Messages and summary

`_Judge.pair` and `_hole_clearance` add the clause `, less a tolerance of <mm> mm (<source>)` when
`tolerance > 0`. The source is a text from the rules view: `DesignRules.tolerance_source`, a new field
whose default is `""`. Altium gives `<n> units of the Altium grid`, KiCad gives `KiCad's DRC epsilon`. The
clause goes after the rule source, so codes, `gap`, `value` and `where` do not change.

`_Judge._too_close` counts a pair that is closer than `found.value` and not closer than `found.value -
tolerance`. `_run` writes that count as `summary["tolerated"]`, only when it is not zero.

## Hypotheses registered by this change

| id | statement |
|---|---|
| `H-A-CHK-GRID-TOL` | a gap below an Altium clearance rule by at most `GRID_TOLERANCE_UNITS` file units comes from the document's unit grid, and Altium Designer's DRC passes it |
