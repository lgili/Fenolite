# c0490: `copper.clearance` tolerates the Altium unit grid and says so

Found on: reviewing a private maintainer board on 2026-11-11 (codes only; nothing from the board is in
this change).

## Why

`fenolite check` on an Altium PCB document reports `copper.clearance` errors for pairs whose gap is short
of the rule by a few tens of nanometres, a few units of the document's own grid (1/10 000 mil, 2.54 nm).
Altium's own DRC passes those pairs. The finding is noise, and it hides real ones.

Two things make it worse:

- The Altium rules view lowers every clearance rule by `CLEARANCE_SLACK_NM` (9 nm,
  `backends.altium.backend._with_unit_slack`) before the check sees it. The finding then states the lowered
  value as "the clearance is …", a value the document does not hold. A reader compares the gap with a rule
  that looks 9 nm off and cannot tell why.
- The shortfall seen is larger than the 9 nm slack. The slack covers the rounding of the import
  (`docs/formats/altium/import.md`, "Clearance of the copper check"), not whatever made this gap. Where
  the rest comes from is not known yet.

## What Changes

- The Altium rules view stops lowering the rules. It gives the tolerance in
  `DesignRules.clearance_tolerance`, the field KiCad's rules already use (c0281). So `copper.clearance` and
  `copper.hole-clearance` judge against the document's rule value less the tolerance.
- The tolerance is a declared whole number of file units, `GRID_TOLERANCE_UNITS`, in
  `backends.altium.backend`. Its value comes from a measured rounding with a derivation in `import.md`. Task
  1.1 finds where the shortfall comes from. If Fenolite's own reading or writing makes it, that is fixed
  there and the tolerance does not grow.
- Every finding judged with a tolerance names the rule's own value and the tolerance and where it comes
  from, for example `the clearance is 0.25 mm (rule Clearance), less a tolerance of 0.0000254 mm (10
  units of the Altium grid)`.
- `summary.tolerated` counts the pairs that are closer than the rule and are passed only because of the
  tolerance. It is absent when there are none.

## Impact

- `src/fenolite/backends/altium/backend.py` (`_with_unit_slack`, `CLEARANCE_SLACK_NM`, `design_rules`).
- `src/fenolite/checks/copper.py` (`_Judge._too_close`, `_hole_clearance_findings`, the messages, `_run`
  summary).
- `docs/formats/altium/import.md` ("Clearance of the copper check").
- A KiCad board keeps its tolerance (500 nm, `H-K-COPPER-EPSILON`). Its messages gain the tolerance
  clause. Other output stays the same.
