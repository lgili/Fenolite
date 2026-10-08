## Why

On the public document `altium-third-party-pcbdoc-03` Fenolite's copper check reports seven clearance findings between pad `J2-1` and seven segments of the track of `Net*_4` on the bottom layer, 126 991 and 126 992 nm apart under the rule `Clearance_2` of 5 mil (127 000 nm). Altium Designer 26.5.0's own rule check reports none (S-0616, step D5 of c0088). c0131 left the cause open and the findings as errors; this change finds the cause and settles them.

## Outcome in one paragraph

**The 8 to 9 nm are in the document, not in Fenolite's conversion, and Altium passes them.** The pad is a rectangle of 637 795 × 637 795 file units (63.7795 mil, an odd number, so its edge lies on a half unit) and the straight segment along its left edge is 50 000 units wide at x = 58 806 106: the document's own integers put the two edges 49 996.5 units apart, 3.5 units (8.89 nm) inside 50 000. Fenolite reads that gap as 126 991 nm against an exact 126 991.11 nm: its geometry is exact within the model's resolution. No rounding of coordinates, of track ends or of a polygonised shape takes part (no arc, no round end is involved). What differs is the comparison: Altium's check does not report copper 3.5 units inside its clearance. The copper check on Altium input now lowers each clearance rule by 9 nm instead of 5: the observed tolerance, 3.5 units, in whole nanometres.

## What Changes

- `backends/altium/backend.py`: `ALTIUM_PASSED_UNITS` (7/2, from S-0616), `ALTIUM_PASSED_NM` (8.89 nm) and `CLEARANCE_SLACK_NM` = max(`UNIT_SLACK_NM`, ceil(`ALTIUM_PASSED_NM`)) = 9, by which `_with_unit_slack` lowers the rules. `UNIT_SLACK_NM` (c0131) stays the slack of the unit.
- One fact row on `docs/formats/altium/import.md`, `ALTIUM-VERIFIED(author-report)`.
- Tests: on authored records, a pad of an odd size and a track 3.5 units inside a 5 mil clearance is no finding and 4.5 units inside is one; two tracks 3 and 4 units inside; on the model 9 nm inside is none and 10 nm one. A corpus test on `-03` derives the 3.5 units from the records and asserts no clearance finding.
- Counts: the class of 25 findings 8 to 20 nm short becomes 9 that are 10 to 20 nm short (1 on `-01`, 0 on `-03`, 8 on `-08`).

Size: 0.5 design-day (a size, not time).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-verification`: MODIFIED "Clearance rules of a PCB document" (the slack is the larger of the unit's and Altium's observed tolerance).

## Non-goals

- No change of `checks/copper.py`, `checks/clearance.py` or of any KiCad path: KiCad boards stay judged strictly at the nanometre (`tests/unit/checks/test_copper.py::test_strict_comparison`).
- No tolerance beyond what Altium was seen to pass; no slack by pair kind; no allow-list. The 9 findings that stay were not checked in Altium and stay errors.
- No claim of what Altium's tolerance is: only that it is at least 3.5 units. No public source states it.
- No change of the import, of a written file, or of any code or constant from a private project or organisation; the test records are authored for Fenolite.

## Evidence level required

The tolerance rests on one author report (S-0616): `ALTIUM-VERIFIED(author-report)` for "Altium Designer 26.5.0 does not report a pad-to-track pair 3.5 file units inside a 5 mil Clearance". The shortfall in the document's integers and the counts are `CORPUS-VERIFIED`. The stage's level is unchanged (that of c0088).

## Impact

- Changed: `backends/altium/backend.py`; tests `tests/unit/backends/altium/adapter/test_rules.py`, `tests/unit/backends/altium/test_frame.py`, `tests/corpus/test_altium_copper.py`.
- Pages: `docs/formats/altium/import.md`, `docs/evidence/altium-pcb.md` (Part D), `docs/evidence/altium-roundtrip.md`, `docs/roadmap.md`, `openspec/README.md`, `LEGAL-ANNEX.md`, `CHANGELOG.md`.
- Behaviour: on Altium input, copper 6 to 9 nm inside a clearance rule is no longer a finding.
- Depends on: c0088, c0125, c0130, c0131, c0132. Archive after them.
