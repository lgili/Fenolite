## Outcome in one paragraph

**"One file unit per item of the pair" is 5.08 nm for a pair, which in whole nanometres is the 5 nm the check already used. No finding changes on any of the eight public documents, and the findings that prompted the question all stay.** They are 3.1 to 7.9 file units short for the pair; the rule gives 2. The maintainer's rule as stated therefore does not do what the numbers of those findings would need ("Open decision", 1), and it is slightly tighter than the worst case of the conversion for one pair kind ("Open decision", 2). It is implemented as stated.

## Context

- **Today.** `backends/altium/backend.py`: `UNIT_SLACK_NM = 5`; `_with_unit_slack` lowers the `min` of every `clearance` rule of the copper view by it (a value at or below it is kept). `checks.copper` compares strictly: a pair is a finding when its gap is below the value in force (`thick_closer_than`).
- **What a rules source can do.** `DesignRules` gives the check a design, a board minimum and two switches; the check has no tolerance of its own, per backend or otherwise, and it must not get one here (`checks/copper.py` judges KiCad boards as in 0.2.0, and another session edits that file). The view can change rule values, and nothing else.
- **Whole nanometres.** `Rule.min` is an integer.

## The unit

A PCB document stores a coordinate, a width, a size and a radius as an integer of 1/10 000 mil (`docs/formats/units.md`; `adapter.units.NM_PER_UNIT` = 127/50). One file unit is 25 400 nm / 10 000 = **2.54 nm**. The import converts each stored integer by itself, exactly as a fraction and half to even to the nanometre (`core.units.u_to_nm`).

## How far the conversion can move each item

A stored value `u` becomes `round(2.54·u)`, off by at most 0.5 nm (reached when `u` is an odd multiple of 25). "Item" below is one copper item of the check; the bound is how far a point of its outline can lie from where the document has it.

| item | what is rounded | bound (nm) | in file units |
|---|---|---|---|
| track | each coordinate of its two ends (0.5 nm each, so a point by √0.5 = 0.71 nm); its width (0.5 nm, so 0.25 nm per side) | 0.71 + 0.25 = 0.96 | 0.38 |
| via | its centre (0.71); its diameter (0.25 per side) | 0.96 | 0.38 |
| vertex of a pour (a zone fill) | each coordinate (0.71); a vertex that is the foot of the bridge to a hole is rounded once more on x (c0122: 0.5) | 0.71, or 1.21 at a bridge | 0.28, 0.48 |
| round or oval pad | the footprint's position (0.71); the pad's position in the footprint's frame, which the import rounds (0.71, turned by the footprint's rotation); the board position that the frame computes from the two, rounded once (0.71): c0088's "up to 1.41 nm more". Then half the rounded size (0.25) | 3 × 0.71 + 0.25 = 2.37 | 0.93 |
| rectangular pad (also rounded rectangle, octagon) | as above for the centre (2.12); each corner is computed from the half sizes (0.25 per axis, 0.35 on the diagonal) and rounded once (0.71) | 2.12 + 0.35 + 0.71 = 3.18 | 1.25 |
| pad of an odd unit width | nothing more: the half of an odd width is a half unit, 1.27 nm, in the document as well; the frame computes it as a fraction, so it is in the bounds above | | |
| arc | the record holds a centre, a radius and two angles; the model holds three points, each computed from them and rounded (0.71), and the check polygonises the arc within 1 000 nm and widens it by a band of 1 001 nm on each side for clearance (`checks.copper.ARC_TOL_NM`) | the band, 1 001 | 394 |

- **Arcs.** The check already reports an arc with a lower bound of its gap and judges it widened by 2 002 nm: for a pair with an arc the slack of the unit decides nothing. This holds before and after change c0127 (branch `c0127-c0128-rewrite-followups`, commit `5b07b481`, not on this branch): c0127 keeps the record's centre, radius and angles in the arc's bag for the write and leaves the three points of the model, which the check reads, as they are.
- **Pair bounds** are the sums: track–track, track–via, via–via 1.92 nm; track or via against a pour 1.67 to 2.17; track or via against a round pad 3.33, against a rectangular pad 4.14; pour against a rectangular pad 4.39; round pad–round pad 4.74; **round pad–rectangular pad 5.55; rectangular pad–rectangular pad 6.36**.

## The rule as stated, and what it gives

"One file unit per item of the pair": every pair has two items, so the slack of a pair is 2 × 2.54 = **5.08 nm**, the same for every pair kind. A pair is no clearance finding while its gap is not below the rule's value less 5.08 nm.

- The check compares exactly and strictly against an integer value. Lowering the rule by 5 reports the gaps below `value − 5`; lowering by 6 would pass gaps between `value − 6` and `value − 5.08`, which the stated rule reports. So the slack is rounded **down**: `UNIT_SLACK_NM = floor(5.08) = 5`. The check is then at most 0.08 nm stricter than the rule and never looser.
- Because every pair has two items, lowering each rule once is the rule applied pair by pair; the view needs nothing per pair.
- **5 is the constant of c0088.** The rule as stated changes no number.
- Against the table: one unit covers every item but a rectangular pad (1.25 units); the pair slack covers every pair but a pad against a rectangular pad (5.55 and 6.36 nm against 5.08).

## Open decision for the maintainer

1. **The findings that prompted the rule stay, and the rule cannot reach them.** Measured below: 25 findings on three documents are 8 to 20 nm short of their rule, 3.1 to 7.9 file units for the pair. They are not conversion error: none of the 6 075 findings that the slack takes away is more than 4 nm short, nothing lies between 5 and 7 nm, and on `-03` the document's own integers put a track edge 49 996.5 units from a pad edge under a rule of 50 000. To pass them the slack would have to be 4 units per item (20.3 nm) on these documents, which is a tolerance of the check, not a property of the unit. Whether Altium's own check passes such copper is not known from a public source; the author report of c0088 (Part D) can say. **Default implemented: they stay errors.**
2. **Rectangular pads.** The worst case of the conversion for a pad against a rectangular pad is 5.55 or 6.36 nm, above the 5.08 of the rule. No such finding exists on the eight documents: no pad-to-pad pair is among the 6 075 findings that the slack removes, and the 13 pad-to-via pairs among them are 1 to 4 nm short. The honest bound would be a slack by item kind (0.96, 1.21, 2.37, 3.18 nm) or 7 nm for every pair; either is wider than the rule as stated for some pair. **Default implemented: the rule as stated, 5 nm; nothing is widened.** A real pair of pads in that last 1.3 nm would be reported as a clearance finding 6 nm short.

## Decisions (2026-10-07)

Settled by the coordinator for the maintainer after the first commit of this change:

1. **The 25 clearance findings that are 8 to 20 nm short stay errors**: 2 on `altium-third-party-pcbdoc-01`, 7 on `-03` and 16 on `-08`. No tolerance is added to the check, for these or for any pair, and nothing is allow-listed.
2. **The rule stays as stated** although it is slightly tighter than the worst case of the conversion for a pad against a rectangular pad (5.55 to 6.36 nm against 5.08 nm): it is not widened, for lack of a public pair that shows the case.
3. **Altium's own rule check on one of them is a step of the maintainer's Altium session 2.** It is written where c0088's Part D lives: no evidence page holds that Part D (`docs/evidence/altium-pcb.md`, "Part D", is the PCB writer's, of c0038), so the step is in `openspec/changes/c0088-altium-light-drc/design.md`, "Session 2: the same copper in Altium's own check", as the required steps D4 to D6 on the public document `-03`. If Altium passes the pairs, the follow-up is to find the pad-size fact that Fenolite reads wrong; if it reports them, they are findings of the board.
4. **This change altered no finding**: 6 075 findings are removed by the slack before and after it, and 25 of the class stay, on the eight public documents.

On `-03` the 7 findings are one pad and seven segments of one track net around it, not seven pads: the pages that said "pads" are corrected in this commit.

## Decisions

1. **Derived constants** in `backend.py`: `FILE_UNIT_NM = Fraction(127, 50)`, `SLACK_UNITS_PER_ITEM = 1`, `PAIR_SLACK_NM = 2 · SLACK_UNITS_PER_ITEM · FILE_UNIT_NM`, `UNIT_SLACK_NM = floor(PAIR_SLACK_NM)`. `_with_unit_slack` is unchanged.
2. **No mechanism in the check.** A per-backend tolerance does not exist in `checks.copper`; the smallest sound mechanism is the one in place, the lowered rule value.
3. **A rule at or below the slack is kept as it is** (as before): a clearance of 5 nm or less is not lowered to nothing.
4. **Cut order.** First the test on the model one nanometre inside, never the tests on records.

## Tests

- `tests/unit/backends/altium/adapter/test_rules.py::test_one_file_unit_per_item_on_records`: a document of authored records with a Clearance of 10 mil and two tracks of two nets; at the clearance, two units inside (gap 253 995 nm, the bound) and three units inside (253 992 nm). No finding, no finding, one finding. The file's grid is the unit, so no record can hold a gap between the last two.
- `::test_one_nanometre_inside_the_bound`: the same import with one track moved by 1 nm in the model (gap 253 994 nm): one finding.
- KiCad judging: `tests/unit/checks/test_copper.py::test_strict_comparison` (c0029) holds a board at exactly its clearance (no finding) and 1 nm inside (one finding, gap 199 999 against 200 000). It is cited, not copied; no file it exercises is changed by this change.
- `tests/unit/backends/altium/test_frame.py::test_rules_source_of_a_built_sample` (c0088) keeps asserting that the view's rules are the document's less `UNIT_SLACK_NM`.

## Measured (2026-10-07, macOS, local corpus cache, no tool; `FENOLITE_HEAVY=1` for `-08`)

Clearance findings with the rule values as the documents write them, by how short they are, before and after this change (the two are equal: the constant did not move).

| document | findings the slack removes (all 1 to 4 nm short) | findings of the class that stay, and by how much | other clearance findings |
|---|---|---|---|
| `-01` | 626 | 2 pad to track: 9 and 20 nm (3.5 and 7.9 units) | 0 |
| `-02` | 0 (no clearance in force) | 0 | 0 |
| `-03` | 359 | 7 pad to track: 8, 8, 9, 9, 9, 9, 9 nm (3.1 to 3.5 units) | 0 |
| `-04` | 118 | 0 | 8, each more than 7 µm short (c0088) |
| `-05` | 232 | 0 | 0 |
| `-06` | 0 (no clearance in force) | 0 | 0 |
| `-07` | 112 | 0 | 0 |
| `-08` (heavy) | 4 628 | 16: 6 track to track, 8 track to via, 1 pad to track, 1 via to via; 8 to 13 nm (3.1 to 5.1 units) | 1, 33.9 µm short (the padless via of c0130) |

- Removed: 6 075 findings, 4 262 of them 1 nm short, 1 538 2 nm, 234 3 nm and 41 4 nm; none 5 nm. By pair kind they include 2 830 pour against via, 1 402 pour against pad, 1 194 pour against track and 436 track against track.
- Stay: 25 findings, the nearest 8 nm short. The two groups do not meet: the conversion explains at most 4 nm, as the table of bounds says it should for these pair kinds (the largest bound among them is 4.39 nm).

## Size (design-days)

| group | dd |
|---|---|
| derivation and proposal | 0.25 |
| constants, tests, measurement, pages | 0.25 |

Total: 0.5. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-verification`, "Clearance rules of a PCB document": MODIFIED from the text of c0130's delta (this branch), which follows c0125's and c0088's. Archive order: c0088, c0125, c0130, then this change.
