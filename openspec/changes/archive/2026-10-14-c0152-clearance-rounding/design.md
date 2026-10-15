## Context

- c0131 made the slack of the copper check on Altium input a stated rule: one file unit (2.54 nm) per item of the pair, 5 whole nanometres. It left 25 findings 8 to 20 nm short as errors and asked Altium's own check about the seven of `altium-third-party-pcbdoc-03` (steps D4 to D6 of `openspec/changes/c0088-altium-light-drc/design.md`).
- The maintainer's answer (2026-10-08, Altium Designer 26.5.0, S-0616): with the Clearance rules alone, 0 violations of `Clearance_2` between pad `J2-1` and the track of `Net*_4`; the pad shows 63.78 × 63.78 mil. By c0088's design (N = 0) the seven pairs are no findings of the board for Altium, and the follow-up was to find why: the size of the pad, the rounding of the gap, or Altium's own tolerance.
- The mechanism stays the one of c0088 and c0131: the Altium rules view lowers each clearance rule (`backend._with_unit_slack`); `checks.copper` compares strictly and has no tolerance of its own.

## Measurement (2026-10-08, local corpus cache, no tool)

The seven findings, as the check reports them with the slack of the unit alone, and the records behind them (`read.pcb.read_pcbdoc`):

| item | record (file units) | model (nm) |
|---|---|---|
| pad `J2-1` | centre (59 200 000, 38 500 000), shape 2 (rectangle) on all three layers, size 637 795 × 637 795, stack mode simple | edges at 149 558 000 and 151 178 000 (1 620 000 wide: 637 795 × 2.54 = 1 619 999.3, each edge rounded once) |
| track 1118 (bottom) | x1 = x2 = 58 806 106, y 38 150 037 to 38 849 963, width 50 000 | x 149 367 509, width 127 000 |
| the six others | the 45° and the straight segments of the same loop around the pad | |

- **Straight side.** Pad edge 59 200 000 − 318 897.5 = 58 881 102.5; track edge 58 806 106 + 25 000 = 58 831 106; gap **49 996.5 units = 126 991.11 nm**, 3.5 units (8.89 nm) inside 50 000. The model gives 126 991 nm.
- **Corners.** The 45° segments stand 49 997.6 units (126 993.9 nm) from the pad's corner; the model gives 126 992. The check reports them 8 nm short.
- **What it is not.** Not the conversion of coordinates (the model is within 0.11 nm of the exact gap on the straight side, inside c0131's bound of 4.14 nm for a track against a rectangular pad). Not the end caps of the track nor a polygonisation: `geometry.thick` judges a segment with round ends exactly, the pad is a rectangle judged exactly (`exact=True`), and no arc is involved. Not the pad's size: 63.78 mil (637 800 units) would make the gap smaller, 49 994 units. Not the rule: `Clearance_2` (priority 2, `ExistsOnLayer('Top Layer') Or ExistsOnLayer('Bottom Layer')`, 5 mil) is the rule in force on the bottom layer, and `Clearance_1` scopes the inner layers only.
- **So** the document's own integers place the copper 3.5 units inside its rule, and Altium's check does not report it. The difference is in the comparison: Altium allows at least 3.5 units. No public source states Altium's tolerance (searched 2026-10-08: Altium's documentation describes the check as "less than the specified minimum" and gives no resolution; a 2011 release note fixed only the displayed distance). The display of 1/1000 mil (10 units) would round 4.99965 mil to 5.000 mil, which would explain it; that is a guess and is not used.

## Decision

1. **The slack of the Altium rules view is the larger of the unit's slack and Altium's observed tolerance.** `ALTIUM_PASSED_UNITS = Fraction(7, 2)`, `ALTIUM_PASSED_NM = ALTIUM_PASSED_UNITS * FILE_UNIT_NM` (8.89 nm), `CLEARANCE_SLACK_NM = max(UNIT_SLACK_NM, ceil(ALTIUM_PASSED_NM))` = **9 nm**.
2. **Rounded up, not down (unlike c0131).** The check compares the model's gap, itself whole nanometres: the observed straight-side gap is read as 126 991 nm, so a rule lowered by 8 nm (126 992) still reports it. 9 is the least whole value that passes every pair Altium was seen to pass; it passes at most 0.11 nm more than Altium was seen to, below the model's resolution of 1 nm.
3. **Not the sum of the two.** Adding the unit's slack (5.08 nm) to the tolerance would give 13 nm and pass all 16 findings of `-08`, which are 3.1 to 5.1 units short and were not checked in Altium. The minimum justified by the measurement is the tolerance alone. Because 9 nm is above every bound of the conversion in c0131's table (the largest, a rectangular pad against a pad, 6.36 nm), it also settles c0131's open decision 2.
4. **The same for every pair kind and every rule**, as c0131 decided: the tolerance is one of Altium's comparison, not of a kind of item.
5. **KiCad is not touched.** The slack is in `AltiumBackend.design_rules` only; `checks/copper.py` is unchanged and judges KiCad boards strictly at the nanometre (KiCad's resolution is the model's, 1 nm).
6. **Evidence.** The fact row on `docs/formats/altium/import.md` is `ALTIUM-VERIFIED(author-report)` (S-0616) for what Altium shows, with S-0172 for the document; the shortfall in units is asserted by a corpus test from the records.

## Effect (measured 2026-10-08; `FENOLITE_HEAVY=1` for `-08`)

| document | the class before (shortfall in nm) | after |
|---|---|---|
| `-01` | 2 pad to track: 9, 20 | 1: 20 |
| `-03` | 7 pad to track: 8, 8, 9, 9, 9, 9, 9 | 0 |
| `-08` | 16: pad–track 8; track–track 9, 9, 10 ×4; track–via 8, 8, 9 ×3, 10, 11, 11; via–via 13 | 8: track–track 10 ×4; track–via 10, 11, 11; via–via 13 |

25 → 9 findings; every other count of `test_copper` is unchanged. The 9 that stay are 10 to 20 nm short (3.9 to 7.9 units), beyond the observed tolerance, and stay errors.

## Tests

- `tests/unit/backends/altium/adapter/test_rules.py`: `test_the_slack_is_derived`; `test_the_slack_on_records` (two tracks 0, 2, 3 and 4 units inside 10 mil: gaps 254 000, 253 995, 253 992, 253 990; only the last is a finding); `test_a_pad_and_a_track_at_the_observed_tolerance` (a rectangular pad of 637 795 units and a track 3.5 and 4.5 units inside 5 mil: none, then one at 126 988 nm); `test_one_nanometre_inside_the_bound` (9 nm inside: none; 10 nm: one).
- `tests/unit/backends/altium/test_frame.py::test_rules_source_of_a_built_sample`: rules lowered by `CLEARANCE_SLACK_NM`.
- `tests/corpus/test_altium_copper.py::test_the_pairs_that_altium_passes` (`needs_corpus`): no clearance finding on `-03`; the seven pairs with the unit's slack alone; the 3.5 units from the records. `test_copper` asserts that every finding the slack removes is at most `CLEARANCE_SLACK_NM` short; `test_vias_without_inner_pads` (heavy) pins 9 and 8 clearance findings.
- KiCad: `tests/unit/checks/test_copper.py::test_strict_comparison`, cited, unchanged.

## Size (design-days)

| group | dd |
|---|---|
| measurement and design | 0.25 |
| constants, tests, pages | 0.25 |

Total: 0.5. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-verification`, "Clearance rules of a PCB document": MODIFIED from the text of c0132's delta, which follows c0131's. Archive order: c0088, c0125, c0130, c0131, c0132, then this change.
