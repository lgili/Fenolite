# Altium polygon pour evidence (c0215)

What is known of Fenolite's computed pours (`backends/altium/pour.py`) against pours that Altium saved.
The documents are the eight public PCB documents of the corpus manifest (S-0835), read with Fenolite's own
readers from the corpus cache; the engine and the comparison (`backends/altium/pourcompare.py`, M1 to M4 of the design of
change c0215) run on them as `tests/corpus/test_altium_pour_census.py` runs them. A saved pour may be stale,
poured by another version or with AdvancedPour, so a disagreement here is a finding, not a verdict on
either side; nothing here raises a row above `CORPUS-VERIFIED`, and only the kit's group K6 says what
Altium does (`docs/altium-kit.md`).

## Census

Census of 2026-10-26 (`test_pour_census`, `FENOLITE_HEAVY=1` for row `-08`). `d` is the polygon's
`ARCRESOLUTION`, 0.5 mil in every document. "M1" is the XOR area over `d` times the boundary of the saved
pour (it passes at 1 or less).

| row | polygons | refused, by reason | compared | pass | worst M1 | M2 differences |
|---|---|---|---|---|---|---|
| `-01` | 5 | `polygon-cutout` 2, `depends-on-refused` 3 | 0 | 0 | — | — |
| `-02` | 12 | `polygon-cutout` 6, `depends-on-refused` 3, `outline-arc` 2, `outline` 1 | 0 | 0 | — | — |
| `-03` | 1 | none | 1 | 0 | 0.256 | 58, the largest 3.03 mm² |
| `-04` | 9 | `depends-on-refused` 5, `rule-scope` 4 | 0 | 0 | — | — |
| `-05` | 2 | none | 2 | 0 | 0.198 | 65, the largest 0.049 mm² |
| `-06` | 10 | `depends-on-refused` 6, `polygon-cutout` 3, `connect-scope` 1 | 0 | 0 | — | — |
| `-07` | 9 | `outline-arc` 4, `rule-scope` 3, `depends-on-refused` 1, `outline` 1 | 0 | 0 | — | — |
| `-08` | 33 | `depends-on-refused` 13, `rule-scope` 10, `outline-arc` 6, `connect-scope` 2, `polygon-cutout` 2 | 0 | 0 | — | — |

78 of 81 polygons are refused: the engine keeps their outline and says why. Three are compared; each passes
M1 and fails M2, so no polygon supports `H-A-POUR-CORPUS` yet.

## Disagreements

Places are in the frame of the import, in nanometres (the import negates Altium's Y). "Candidate" is Fenolite's pour, "reference" the
saved one; "held by" names the side whose copper the difference is. The nearest object is the one whose
box is nearest the centre of the difference.

| row | polygon | failed | finding |
|---|---|---|---|
| `-03` | `B.Cu` `GND_L02_P000` | M2, M3, M4 | 58 differences: 36 next to a track of another net, 13 to a via of another net, 7 to `GND` pads, 2 to pads of other nets. The largest, 3.03 mm² held by the candidate at (24962320, -67945000), lies inside the box of a `NetJ5_2` track. At the `GND` pads of `J1` at (175768000, -108541248), (175768000, -119781246), (171768000, -119781246) and (171768000, -108541248) the reference holds 0.97, 0.97, 0.89 and 0.89 mm² that the candidate leaves void, where a free `GND` region overlaps each pad; at `S1` (136662945, -124556764) it holds 0.78 mm². M3: one piece holds 251 holes against 268. M4: the candidate touches 15 objects where the reference touches 27, and `GND` forms 5 connected groups against 1. |
| `-05` | `B.Cu` `GND_BOTTOM` | M2 | 27 differences, all held by the candidate, 0.004 to 0.049 mm², 0.1 to 0.2 mm from a track (11), a via (10) or a pad (6) of another net: copper left between two voids that the saved pour does not hold. |
| `-05` | `F.Cu` `GND_TOP` | M2, M3, M4 | 38 differences of the same kind (17 by vias, 16 by tracks, 5 by pads of other nets). M3: one piece against two (a neck of about 130 µm against the 127 µm threshold), whose holes do not match (24 against 0). M4 follows from M3: the one piece touches 47 objects. |

The differences by same-net pads of `-03` (the reference holds copper where Fenolite leaves a relief) and
the copper that Fenolite keeps between the voids of `-05` are the two open findings: rows `H-A-POUR-RELIEF`,
`H-A-POUR-CONNECT` and `H-A-POUR-NECK` of the register name the probes of K6 that settle them (P2 and P3).

## Time

The time of reading a document and pouring every polygon (`test_pour_time`, on an Apple M4, 2026-10-26),
the comparison of the census not included:

| row | seconds |
|---|---|
| `-01` | 0.7 |
| `-02` | 0.2 |
| `-03` | 7.5 |
| `-04` | 0.2 |
| `-05` | 1.1 |
| `-06` | 0.2 |
| `-07` | 0.1 |
| `-08` | 5.2 |

The limit of task 3.6 is 60 s for one document. Before the neck removal took one difference per polygon,
row `-03` took 36.6 s.

## Kit rounds

No round of group K6 has been run. The verdict of each probe of the samples `pour` and `pour4` is written
here when one is (task 7.4).
