# Copper check on the readable demo boards

Counts and timings only (change c0029, task 10.1). Measured on 2026-10-04 by
`tests/corpus/test_copper_perf.py` on the 21 readable, non-heavy demo boards of the `rt0` corpus rows,
read by Fenolite's board reader, with the pads of the board frame. Each design got one authored test
rule, a clearance of 0.2 mm on every pair, so that every board has a clearance in force; the demo
projects' own rules and classes were not read. The findings are therefore not verdicts on the boards:
many of them are designed with smaller clearances, and their stored fills are judged as they are. The
times are wall seconds of `board_pads` plus `check_copper` on one machine (macOS, CPython 3.13),
rounded to 0.1 s. They are recorded, never asserted.

| board | layers | tracks | arcs | vias | pads | fills | candidate pairs | exact tests | shorts | clearance | zone overlaps | unsupported | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `kicad-demo-10-0-6-pcb-01` | 6 | 1884 | 200 | 444 | 617 | 31 | 8102 | 15649 | 0 | 2393 | 0 | none | 6.1 |
| `kicad-demo-10-0-6-pcb-02` | 2 | 364 | 0 | 0 | 165 | 2 | 586 | 1154 | 0 | 33 | 0 | none | 0.3 |
| `kicad-demo-10-0-6-pcb-03` | 2 | 59 | 0 | 0 | 33 | 1 | 91 | 182 | 0 | 0 | 0 | none | 0.0 |
| `kicad-demo-10-0-6-pcb-04` | 2 | 53 | 0 | 0 | 34 | 1 | 91 | 182 | 0 | 0 | 0 | none | 0.0 |
| `kicad-demo-10-0-6-pcb-05` | 2 | 731 | 0 | 84 | 379 | 23 | 920 | 1840 | 0 | 0 | 0 | none | 0.2 |
| `kicad-demo-10-0-6-pcb-07` | 4 | 2935 | 0 | 253 | 825 | 21 | 6368 | 12727 | 0 | 186 | 0 | none | 1.5 |
| `kicad-demo-10-0-6-pcb-08` | 1 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | none | 0.0 |
| `kicad-demo-10-0-6-pcb-09` | 2 | 140 | 0 | 19 | 327 | 8 | 602 | 1204 | 0 | 0 | 0 | none | 0.3 |
| `kicad-demo-10-0-6-pcb-10` | 2 | 576 | 0 | 29 | 327 | 9 | 1304 | 2608 | 0 | 0 | 0 | none | 0.4 |
| `kicad-demo-10-0-6-pcb-11` | 4 | 1638 | 16 | 410 | 651 | 86 | 6716 | 13423 | 9 | 345 | 0 | pad 4 | 1.2 |
| `kicad-demo-10-0-6-pcb-12` | 2 | 370 | 0 | 6 | 240 | 3 | 613 | 1226 | 0 | 0 | 0 | none | 0.2 |
| `kicad-demo-10-0-6-pcb-13` | 8 | 943 | 0 | 183 | 389 | 35 | 5494 | 9658 | 7 | 1391 | 0 | zone-outline 2 | 3.3 |
| `kicad-demo-10-0-6-pcb-14` | 2 | 112 | 48 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | none | 0.1 |
| `kicad-demo-10-0-6-pcb-15` | 2 | 208 | 0 | 3 | 108 | 7 | 316 | 632 | 0 | 0 | 0 | none | 0.1 |
| `kicad-demo-10-0-6-pcb-16` | 4 | 2143 | 0 | 405 | 753 | 104 | 7041 | 14073 | 3 | 100 | 0 | none | 1.8 |
| `kicad-demo-10-0-6-pcb-17` | 4 | 7932 | 0 | 808 | 2118 | 8 | 10392 | 20784 | 0 | 32 | 0 | none | 3.5 |
| `kicad-demo-9-0-9-1-pcb-01` | 2 | 19 | 0 | 0 | 11 | 1 | 47 | 93 | 1 | 0 | 0 | none | 0.1 |
| `kicad-demo-9-0-9-1-pcb-02` | 2 | 371 | 0 | 7 | 241 | 3 | 667 | 1334 | 0 | 0 | 0 | none | 0.2 |
| `kicad-demo-9-0-9-1-pcb-03` | 2 | 370 | 0 | 6 | 240 | 3 | 614 | 1228 | 0 | 0 | 0 | none | 0.2 |
| `kicad-demo-9-0-9-1-pcb-05` | 2 | 4 | 0 | 0 | 14 | 0 | 0 | 0 | 0 | 0 | 0 | none | 0.0 |
| `kicad-demo-9-0-9-1-pcb-06` | 2 | 647 | 0 | 12 | 281 | 17 | 1073 | 2146 | 0 | 0 | 0 | none | 0.3 |

21 boards, 19.8 s in total; the slowest took 6.1 s, below the 60 s at which the
design would cut the measurement (Decision 14), so no cut was applied.

What makes it fast enough: one spatial index per layer for the candidate pairs, an index of the edges
of every large fill for the exact tests and for the point-in-fill test, and a closest-pair search
that widens from the shapes' boxes instead of visiting every pair of edges.

## The zone's own clearance (c0068, 2026-10-05)

`H-K-COPPER-ZONECLR`. `tests/corpus/test_zone_clearance_census.py` checks each readable non-heavy demo
board twice with the classes and the board minimum of its own project file (the corpus holds no rules
file for a demo): once as `check` now does, and once with the zone's value switched off, which is the
rule of c0029. A stored fill of a demo may be stale, so nothing is gated. Boards without a filled zone
are left out of the table (3 of 21).

| board | zones with fills | of them with a clearance | pads with a clearance override | clearance findings without the zone value | clearance findings | of them with source `zone` | added by the zone value | kinds of the other item of the added ones | added ones naming a pad with an override |
|---|---|---|---|---|---|---|---|---|---|
| `kicad-demo-10-0-6-pcb-01` | 13 | 13 | 115 | 919 | 919 | 40 | 0 | none | 0 |
| `kicad-demo-10-0-6-pcb-02` | 1 | 1 | 0 | 0 | 0 | 0 | 0 | none | 0 |
| `kicad-demo-10-0-6-pcb-03` | 1 | 1 | 0 | 0 | 0 | 0 | 0 | none | 0 |
| `kicad-demo-10-0-6-pcb-04` | 1 | 1 | 0 | 0 | 0 | 0 | 0 | none | 0 |
| `kicad-demo-10-0-6-pcb-05` | 1 | 1 | 0 | 0 | 0 | 0 | 0 | none | 0 |
| `kicad-demo-10-0-6-pcb-07` | 3 | 3 | 0 | 0 | 0 | 0 | 0 | none | 0 |
| `kicad-demo-10-0-6-pcb-09` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | none | 0 |
| `kicad-demo-10-0-6-pcb-10` | 2 | 0 | 0 | 24 | 24 | 0 | 0 | none | 0 |
| `kicad-demo-10-0-6-pcb-11` | 34 | 34 | 0 | 3 | 3 | 0 | 0 | none | 0 |
| `kicad-demo-10-0-6-pcb-12` | 1 | 1 | 2 | 1 | 1 | 0 | 0 | none | 0 |
| `kicad-demo-10-0-6-pcb-13` | 4 | 4 | 0 | 15 | 15 | 0 | 0 | none | 0 |
| `kicad-demo-10-0-6-pcb-15` | 1 | 1 | 0 | 0 | 0 | 0 | 0 | none | 0 |
| `kicad-demo-10-0-6-pcb-16` | 2 | 2 | 64 | 157 | 157 | 27 | 0 | none | 0 |
| `kicad-demo-10-0-6-pcb-17` | 2 | 2 | 0 | 32 | 32 | 0 | 0 | none | 0 |
| `kicad-demo-9-0-9-1-pcb-01` | 1 | 1 | 0 | 0 | 1 | 1 | 1 | 1 pad | 0 |
| `kicad-demo-9-0-9-1-pcb-02` | 1 | 1 | 0 | 0 | 0 | 0 | 0 | none | 0 |
| `kicad-demo-9-0-9-1-pcb-03` | 1 | 1 | 2 | 4 | 4 | 2 | 0 | none | 0 |
| `kicad-demo-9-0-9-1-pcb-06` | 1 | 1 | 0 | 0 | 0 | 0 | 0 | none | 0 |

- The zone's value **adds 1 finding** over the 21 boards, and none on the boards of tag
  10.0.6: the one added finding names a pad of a 9.0.9.1 demo. 69 findings that the check
  reported already now carry the zone's value and the source `zone`, because that value is the larger.
- No added finding names a track, an arc or a via. At proposal time, before the repair of the pad offset
  and before a zone's value was judged against the narrowed arc, the same rule added 3 findings against
  pads with an offset drill on one board and 6 against arc tracks on another (design, measurement 3);
  both groups are gone.
- **Clearance overrides of pads and footprints** (design, Open Questions). A pad or a footprint may carry
  a `(clearance …)` of its own, which the copper check does not model. The last column counts the added
  findings that name such a pad or a pad of such a footprint: 0. The boards that hold overrides do have
  findings of source `zone` on those pads, but each of those pairs was a finding without the zone's
  value too.
- The census costs more than the measurement above: with zones the largest clearance of a board is
  often the 0.5 mm of a zone, so the candidate search reaches further. `summary.max_clearance` says how
  far.
