## Why

The copper check on Altium input lowers every clearance rule by a constant, `UNIT_SLACK_NM = 5` (c0088), so that copper at exactly its clearance in the document's unit is no finding after the conversion to whole nanometres. The constant was a measured number with a sentence of explanation. c0125 then found pad-to-track pairs 8 and 9 nm short on one public document and the same class on another, and asked whether the slack is right. The maintainer decided on 2026-10-06 that the slack becomes a stated rule: **one file unit per item of the pair**.

## Outcome in one paragraph

**The stated rule gives the number the check already used, so no finding changes.** A file unit is 1/10 000 mil = 2.54 nm; two items are 5.08 nm; a rule holds whole nanometres and the slack may not be rounded up, so rules are lowered by 5 nm, as before. All 7 findings of `altium-third-party-pcbdoc-03`, the 2 of `-01` and the 16 of that class on `-08` remain errors: they are 8 to 20 nm short, 3.1 to 7.9 file units for the pair, which no reading of "one unit per item" covers. The derivation also shows where the rule is tighter than the worst case of the conversion (a rectangular pad against another pad, 6.36 nm); both gaps are stated as open decisions and nothing is widened here.

## What Changes

- **The constant is derived, not chosen.** `FILE_UNIT_NM` (127/50 nm), `SLACK_UNITS_PER_ITEM` (1), `PAIR_SLACK_NM` (5.08 nm) and `UNIT_SLACK_NM` = its whole nanometres, rounded down (5). The docstring and the facts page hold the derivation: by how much each kind of item can move in the conversion.
- **Tests at the bound**: on authored records, copper two file units inside its clearance is no finding and three units inside is one; on the model, one nanometre inside the bound is one. The test that KiCad judging is strict at the nanometre exists and is cited.
- **Measured again over the eight public PCB documents**: the findings the slack takes away (6 075, all 1 to 4 nm short) and those that stay (25 of the class, 8 to 20 nm short), per document.

Size: 0.5 design-day (a size, not time).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-verification`: MODIFIED "Clearance rules of a PCB document" (the slack is the stated rule).

## Non-goals

- No change of `checks/copper.py` or `checks/clearance.py`: KiCad boards are judged exactly as in 0.2.0, strictly at the nanometre.
- No wider slack than the rule states, for any pair kind, and no slack per pair kind: design, "Open decision".
- No allow-list: a finding that stays is an error.
- No change of any written file, of the import or of the board frame.
- No code or constant from any private project or organisation; the test records are authored for Fenolite.
- No new format fact: the unit is that of `docs/formats/units.md`.

## Evidence level required

Unchanged: the stage's level is that of c0088. The derivation is arithmetic on Fenolite's own conversion; the counts are `CORPUS-VERIFIED`.

## Impact

- Changed: `backends/altium/backend.py` (the constants and their documentation).
- Pages: `docs/formats/altium/import.md` ("Clearance of the copper check"), `docs/cli-contract.md`, `docs/evidence/altium-roundtrip.md`.
- Behaviour: none. The same boards give the same findings.
- Depends on: c0088, c0125, c0130 (this branch). Archive after them.
