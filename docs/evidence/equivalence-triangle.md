# Equivalence triangle: Fenolite's Altium import against `kicad-cli pcb import`

The record of `fenolite equivalent A.PcbDoc --against kicad-import` (change c0045, capability
design-equivalence): one PCB document is read twice, by Fenolite's Altium backend and by
`kicad-cli pcb import --format altium` followed by Fenolite's KiCad reader, and the two models are
compared at levels 1 to 4, and at level 5 since change c0089 ("Level 5, kicad-cli 10.0", at the end). The
page holds counts only. Documents are named by corpus row id and licence;
no content of a document is written here.

What the label means: `ORACLE-VERIFIED(kicad-cli)` says that two independent readers of one file agree.
It says nothing about Altium Designer, and it settles no `H-A-*` row.

## Where the triangle runs

The triangle reads the seven PCB document rows of change c0041 (the use `altium-pcbdoc` of
`tests/corpus/manifest.toml`); this change adds no row and no use. None of them is embeddable, so each is
fetched into the cache and never committed.

| row id | licence | source |
|---|---|---|
| `altium-third-party-pcbdoc-01` | LGPL-3.0 | S-0188 |
| `altium-third-party-pcbdoc-02` | Apache-2.0 | S-0176 |
| `altium-third-party-pcbdoc-03` | Apache-2.0 | S-0172 |
| `altium-third-party-pcbdoc-04` | MIT | S-0199 |
| `altium-third-party-pcbdoc-05` | BSD-2-Clause | S-0174 |
| `altium-third-party-pcbdoc-06` | MIT | S-0175 |
| `altium-third-party-pcbdoc-07` | MIT | S-0200 |

- **The file in the repository.** `tests/kicad/equivalence/test_triangle_blink.py` runs the triangle on
  `tests/data/altium/blink/blink.PcbDoc`, a document Fenolite wrote from its authored CC0 library. It
  needs no corpus and runs in the `kicad-10` job of `.github/workflows/ci.yml` (`tests/kicad`).
- **Corpus.** The `kicad-10` job fetches the rows of the use `altium-pcbdoc` by name (its fetch step passes
  `--uses altium-pcbdoc`, which `tests/unit/test_ci_workflow.py` checks) and runs `tests/kicad` with
  `FENOLITE_REQUIRE=kicad,corpus`, so `tests/kicad/equivalence/test_triangle_corpus.py` runs there on every
  row, and locally on `kicad-cli` 10.0.6 (macOS). The design of this change expected a local run only; the
  fetch step has been widened since.
- **Rows that fail in `kicad-cli`.** `docs/evidence/altium-pcb-read.md` ("Document oracle") records one:
  on the Linux build of `kicad-cli` 10.0.6, `pcb import` exits 255 on `altium-third-party-pcbdoc-02` with an
  unhandled exception of KiCad's own importer, whose class changes between runs. The macOS build imports
  the row. The corpus test skips that row where the tool writes no board and compares it where it does;
  it matches only the exit code and the stable part of KiCad's message.
- **Below 10.0.** `pcb import` does not exist in 9.0 (`H-K-00`), so every test of
  `tests/kicad/equivalence/` is skipped there.

## Committed document, kicad-cli 10.0

`uv run pytest tests/kicad/equivalence/test_triangle_blink.py -s` with `kicad-cli` 10.0.6 (macOS, local,
2026-10-05): 3 passed. `tests/data/altium/blink/blink.PcbDoc` holds three components (`U1`, `R1` on the
top side, `D1` on the bottom side) and 36 pads.

| run | level 1 | level 2 | level 3 | level 4 |
|---|---|---|---|---|
| empty profile (relative frame, tolerance 0, no rule): compared / differences | 3 / 0 | 36 / 0 | 36 / 68 (`pad-size` 36, `pad-position` 30, `pad-drill` 2) | 3 / 1 (`position` 1) |
| profile `kicad-import` 10.0 (tolerance 10 nm): compared / differences / excluded | 3 / 0 / 0 | 36 / 0 / 0 | 36 / 0 / 0 | 3 / 0 / 0 |

- Translation removed from KiCad's board: (98 101 100, 145 403 600) nm.
- Largest difference after the translation: footprint position 1 nm, pad position 1 nm, pad size 1 nm,
  drill 1 nm; no rotation differs. Every difference of the empty-profile run is this rounding: the document
  holds lengths in units of 2.54 nm.
- No rule matches. All four levels are `ORACLE-VERIFIED(kicad-cli)` (10.0.6) for this document, which is
  what KiCad's importer reads of a file Fenolite wrote.
- The import report lists no warning and no error; the tool prints 16 warnings about internal plane
  layers that it does not map, which the command reports as `equiv.import-message` infos.

`tests/unit/cli/test_equivalent_cmd.py -k two_backends` compares the same document with the KiCad board
that Fenolite builds from the same design, with no tool: no difference at levels 1 to 4 with
`--frame relative --tolerance-nm 1`.

## Corpus, kicad-cli 10.0

`FENOLITE_REQUIRE=kicad,corpus uv run pytest tests/kicad/equivalence/test_triangle_corpus.py -s` with
`kicad-cli` 10.0.6 (macOS, local, 2026-10-05): 85 passed, on all seven rows. In each cell: compared /
differences / excluded, under the profile `kicad-import` 10.0 (relative frame, tolerance 10 nm, five
rules).

| row id | licence | level 1 | level 2 | level 3 | level 4 | translation (nm) | rules that matched |
|---|---|---|---|---|---|---|---|
| altium-third-party-pcbdoc-01 | LGPL-3.0 | 248 / 0 / 1 | 721 / 0 / 2 | 731 / 0 / 3 | 248 / 0 / 0 | −29 362 400, 254 482 600 | `kicad-10.0-value-empty` (1), `kicad-10.0-paste-pad-pin` (2), `kicad-10.0-paste-pad` (2), `kicad-10.0-component-copper-pad` (1) |
| altium-third-party-pcbdoc-02 | Apache-2.0 | 41 / 0 / 0 | 143 / 0 / 0 | 143 / 0 / 2 | 41 / 0 / 0 | 73 326 065, 195 872 005 | `kicad-10.0-octagon-shape` (2) |
| altium-third-party-pcbdoc-03 | Apache-2.0 | 52 / 0 / 0 | 210 / 0 / 0 | 217 / 0 / 1 | 52 / 0 / 0 | 47 663 100, 180 695 600 | `kicad-10.0-component-copper-pad` (1) |
| altium-third-party-pcbdoc-04 | MIT | 15 / 0 / 0 | 50 / 0 / 0 | 51 / 0 / 1 | 15 / 0 / 0 | −187 891 421, 333 439 028 | `kicad-10.0-component-copper-pad` (1) |
| altium-third-party-pcbdoc-05 | BSD-2-Clause | 23 / 0 / 0 | 96 / 0 / 0 | 96 / 0 / 0 | 23 / 0 / 0 | 118 656 100, 115 798 600 | none |
| altium-third-party-pcbdoc-06 | MIT | 27 / 0 / 0 | 106 / 0 / 0 | 106 / 0 / 0 | 27 / 0 / 0 | 75 801 098, 159 203 601 | none |
| altium-third-party-pcbdoc-07 | MIT | 12 / 0 / 0 | 112 / 0 / 0 | 114 / 0 / 0 | 12 / 0 / 0 | −156 786 903, 337 125 269 | none |

Totals: 418 components, 1 438 `REF-PIN` elements, 1 458 pad pairs and 418 placements compared; 10
differences excluded by five rules; none left.

Largest differences after the translation, whatever the tolerance (`tests/_triangle.py::measure`), and
the count of paired footprints on the bottom side:

| row id | footprint position (nm) | pad position (nm) | pad size (nm) | drill (nm) | rotation (µdeg) | pad rotation (µdeg) | bottom footprints |
|---|---|---|---|---|---|---|---|
| altium-third-party-pcbdoc-01 | 5 | 9 | 1 | 1 | 0 | 0 | 119 |
| altium-third-party-pcbdoc-02 | 3 | 5 | 5 | 4 | 0 | 0 | 14 |
| altium-third-party-pcbdoc-03 | 4 | 9 | 4 | 2 | 0 | 0 | 3 |
| altium-third-party-pcbdoc-04 | 8 | 9 | 1 | 0 | 0 | 0 | 0 |
| altium-third-party-pcbdoc-05 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| altium-third-party-pcbdoc-06 | 6 | 9 | 3 | 1 | 0 | 0 | 2 |
| altium-third-party-pcbdoc-07 | 6 | 9 | 1 | 1 | 0 | 0 | 8 |

The measured maximum is 9 nm, so the profile's `tolerance_nm` is 10, the smallest multiple of 10 that
covers it. KiCad holds a converted length in steps of 10 nm (`docs/formats/altium/pcb-read.md`, "What
KiCad does not import"), and a pad's local position is computed from two rounded board positions.

### Differences with the empty profile

The first measurement ran with no rule and tolerance 0 in the relative frame. Counts by kind:

| row id | level 1 | level 2 | level 3 | level 4 |
|---|---|---|---|---|
| altium-third-party-pcbdoc-01 | `ref-ambiguous` 1, `value` 1 | `pin-missing` 2 | `pad-size` 673, `pad-position` 643, `pad-drill` 25, `pad-missing` 3 | `position` 34 |
| altium-third-party-pcbdoc-02 | none | none | `pad-position` 118, `pad-size` 75, `pad-drill` 4, `pad-shape` 2 | `position` 2 |
| altium-third-party-pcbdoc-03 | `ref-ambiguous` 1 | none | `pad-size` 201, `pad-position` 146, `pad-drill` 21, `pad-missing` 1 | `position` 32 |
| altium-third-party-pcbdoc-04 | `ref-ambiguous` 1 | none | `pad-position` 40, `pad-size` 33, `pad-missing` 1 | `position` 13 |
| altium-third-party-pcbdoc-05 | `ref-ambiguous` 1 | none | `pad-size` 96, `pad-position` 36 | `position` 1 |
| altium-third-party-pcbdoc-06 | none | none | `pad-size` 100, `pad-position` 65, `pad-drill` 8 | `position` 22 |
| altium-third-party-pcbdoc-07 | `ref-ambiguous` 1 | none | `pad-position` 100, `pad-size` 114, `pad-drill` 19 | `position` 10 |

Every `pad-size`, `pad-position`, `pad-drill` and `position` difference is below 10 nm and disappears at
the tolerance. What remains at 10 nm is attributed below.

### What Fenolite caused, and was fixed

Before the fix, the first row gave 88 `component-missing` and 5 more `ref-ambiguous` differences at
level 1, and only 161 of its 248 components were compared. Fenolite's adapter took a component's
reference from its source designator. The components of a repeated sheet share that designator (84
components of this row), and a designator changed on the board alone leaves it behind (2 components);
KiCad's importer names a footprint by the designator text the board shows. The adapter now takes the
designator text first and the source designator only without one
(`fenolite.backends.altium.adapter.board`; regression test
`tests/unit/backends/altium/adapter/test_board.py::test_the_reference_is_the_designator_the_board_shows`).
The model of that row no longer holds the seven duplicate references of the repeated sheet.

### Rules of the profile `kicad-import` 10.0

| rule | level, kind | attribution | what was observed | rows |
|---|---|---|---|---|
| `kicad-10.0-value-empty` | 1, `value` | undecided | one component whose comment text the document holds has an empty value in the converted board | altium-third-party-pcbdoc-01 (1) |
| `kicad-10.0-paste-pad-pin` | 2, `pin-missing` | importer | two pads of one component lie on a paste layer; KiCad imports no such pad | altium-third-party-pcbdoc-01 (2) |
| `kicad-10.0-paste-pad` | 3, `pad-missing` | importer | the same two pads at level 3 | altium-third-party-pcbdoc-01 (2) |
| `kicad-10.0-component-copper-pad` | 3, `pad-missing` | importer | KiCad turns component copper regions and net-less component fills into pads without a number: 2, 8 and 6 such pads | altium-third-party-pcbdoc-01 (1), -03 (1), -04 (1) |
| `kicad-10.0-octagon-shape` | 3, `pad-shape` | undecided | two octagonal pads are `roundrect` in KiCad's board and `custom` in Fenolite's import | altium-third-party-pcbdoc-02 (2) |

The three `importer` rules restate rows of `docs/formats/altium/pcb-read.md` ("What KiCad does not
import"), which the reader oracle of change c0041 verified record by record. A rule selects by a glob
over `where` and cannot see a pad's layer or shape, so the paste and octagon rules name the pads they were
observed on; the same behaviour on another board shows as a difference.

### References that a document holds several times

These cannot be paired. They are a property of the document, get no rule, and are left out of the corpus
test by name (`IGNORED_REFS` in `tests/kicad/equivalence/test_triangle_corpus.py`; `--ignore-ref` on the
command line). Without that option each gives one `ref-ambiguous` difference.

| row id | reference | count in Fenolite's read | count in KiCad's read | what it is |
|---|---|---|---|---|
| altium-third-party-pcbdoc-01 | empty | 12 | 4 | pads that belong to no component; 8 of them lie on a paste layer, which KiCad does not import |
| altium-third-party-pcbdoc-03 | `*` | 3 | 3 | three components with the designator `*` |
| altium-third-party-pcbdoc-04 | empty | 2 | 2 | pads that belong to no component |
| altium-third-party-pcbdoc-05 | empty | 4 | 4 | pads that belong to no component |
| altium-third-party-pcbdoc-07 | empty | 2 | 2 | pads that belong to no component |

### Labels per level

A level is `ORACLE-VERIFIED(kicad-cli)` (10.0.6) for a document when no `undecided` rule matched at that
level or below.

| row id | level 1 | level 2 | level 3 | level 4 |
|---|---|---|---|---|
| altium-third-party-pcbdoc-01 | INFERRED (`kicad-10.0-value-empty`) | INFERRED | INFERRED | INFERRED |
| altium-third-party-pcbdoc-02 | ORACLE-VERIFIED(kicad-cli) | ORACLE-VERIFIED(kicad-cli) | INFERRED (`kicad-10.0-octagon-shape`) | INFERRED |
| altium-third-party-pcbdoc-03 to -07 | ORACLE-VERIFIED(kicad-cli) | ORACLE-VERIFIED(kicad-cli) | ORACLE-VERIFIED(kicad-cli) | ORACLE-VERIFIED(kicad-cli) |

Over all rows, each of `H-G-EQ-L1` to `H-G-EQ-L4` therefore stays `INFERRED`: one `undecided` rule matched
at level 1 on one row and one at level 3 on another. The Linux run of the `kicad-10` job compares six
rows; `altium-third-party-pcbdoc-02` is skipped there as recorded under "Where the triangle runs".

## Level 5, kicad-cli 10.0 (change c0089)

Level 5 compares the routing of each net: which pads the copper joins, the vias per pair of copper spans
and the routed length per copper span (`docs/equivalence.md`, "Level 5: routing"). The triangle runs it on
two sets of boards, with `tests/kicad/equivalence/test_triangle_level5.py`:

- **The routed sample** (`tests/_altium_copper.py`, authored for Fenolite; four copper layers, five
  tracks, one arc, three vias, one zone): its KiCad board, the PCB document that
  `fenolite build --target altium --copper-from` writes from it, and the board that `kicad-cli pcb import`
  converts that document to. Three corners, compared pairwise. The probe `equiv-l5-triangle`
  (`docs/evidence/kicad/probes/10.0.6.json`) records `equal`.
- **The seven public documents** of the table above. Fenolite writes nothing here, so each row has two
  corners: Fenolite's read of the document and the read of KiCad's conversion.

`uv run pytest tests/kicad/equivalence/test_triangle_level5.py -s` with `kicad-cli` 10.0.6 (macOS, local,
2026-10-06): 20 passed; 21 passed after change c0122, which adds one test ("The pour with holes"
below). `pcb import` does not exist in 9.0, so nothing of this section runs there; the probe
is registered for major 10 only and `docs/evidence/kicad/probes/9.0.9.json` does not hold it.

### Tolerances

The profile `kicad-import` 10.0 keeps its `tolerance_nm` of 10 and gains `tolerance_ppm` 20 for routed
lengths. The sample needs neither more than 10 nm nor the relative tolerance. On the public documents
the largest difference of a routed length on one copper span, with no tolerance at all, is 20 nm, and
among the differences above 10 nm the largest share of the longer length is 18 parts per million; 20 is
the smallest multiple of 10 that covers it. The cause is the rounding of `H-G-EQ-ROUND-2`: KiCad holds
each end of each segment in steps of 10 nm, so the length of a route differs by more the more segments it
has. With `tolerance_ppm` 0 the only level-5 differences on the public documents are `route-length`:
connectivity and via counts agree exactly on every row.

| row id | spans compared | largest length difference (nm) | largest share above 10 nm (ppm) |
|---|---|---|---|
| altium-third-party-pcbdoc-01 | 222 | 14 | 2 |
| altium-third-party-pcbdoc-02 | 40 | 10 | none above 10 nm |
| altium-third-party-pcbdoc-03 | 83 | 12 | 2 |
| altium-third-party-pcbdoc-04 | 15 | 13 | 7 |
| altium-third-party-pcbdoc-05 | 50 | 4 | none above 10 nm |
| altium-third-party-pcbdoc-06 | 21 | 10 | none above 10 nm |
| altium-third-party-pcbdoc-07 | 41 | 20 | 18 |

### The routed sample

Levels 1 to 5 in the relative frame at 10 nm, with no relative tolerance and no rule. In each cell of
level 5: nets compared / differences / notices.

| pair | levels 1 to 4 | level 5 | pieces a, b | vias a, b | total length a, b (nm) | zones without a fill a, b |
|---|---|---|---|---|---|---|
| KiCad board, written document | no difference | 4 / 0 / 1 | 5, 5 | 3, 3 | 51 020 987, 51 020 985 | 1, 2 |
| written document, KiCad's import | no difference | 4 / 0 / 1 | 5, 5 | 3, 3 | 51 020 985, 51 020 987 | 2, 2 |
| KiCad board, KiCad's import | no difference | 4 / 0 / 1 | 5, 5 | 3, 3 | 51 020 987, 51 020 987 | 1, 2 |

- The three reads hold the same pieces: `LED_DRV` joins two pads on the top layer, `LED_A` joins two
  pads through one via and the second inner layer, `VIN` and `GND` hold one pad with a via each. Each
  length per copper span agrees within 10 nm.
- The one notice is `route-unjudged` on `GND`: the sample's zone is written unpoured (the document's
  polygons are repoured in Altium), so no read holds its fill and the net is not judged. The zone of two
  layers of the KiCad board is one polygon per layer in the document, hence 1 and 2.
- With one via taken out of KiCad's import, level 5 reports `route-connectivity` on that net: the
  comparison is not blind on this board.

### The public documents

Profile `kicad-import` 10.0 (relative frame, 10 nm, 20 ppm), with the references of "References that a
document holds several times" left out. No rule of the profile is of level 5, and none was needed. In the
level-5 cell: nets compared / differences / excluded.

| row id | level 5 | notices | pieces a, b | vias a, b | zones without a fill a, b | copper on no net a, b |
|---|---|---|---|---|---|---|
| altium-third-party-pcbdoc-01 | 153 / 0 / 0 | `route-unjudged` 8 | 419, 419 | 646, 646 | 0, 8 | 0, 0 |
| altium-third-party-pcbdoc-02 | 34 / 0 / 0 | `route-unjudged` 4 | 44, 44 | 242, 242 | 1, 6 | 0, 1 |
| altium-third-party-pcbdoc-03 | 54 / 0 / 0 | none | 59, 59 | 47, 47 | 0, 0 | 6, 0 |
| altium-third-party-pcbdoc-04 | 10 / 0 / 0 | none | 10, 10 | 67, 67 | 0, 0 | 0, 0 |
| altium-third-party-pcbdoc-05 | 30 / 0 / 0 | none | 30, 30 | 59, 59 | 0, 0 | 0, 0 |
| altium-third-party-pcbdoc-06 | 18 / 0 / 0 | none | 19, 19 | 42, 42 | 0, 0 | 0, 0 |
| altium-third-party-pcbdoc-07 | 21 / 0 / 0 | none | 22, 22 | 60, 60 | 0, 0 | 0, 0 |

Totals: 320 nets compared, 1 163 vias on each side, no difference, no exclusion. Every net with copper is
in a pair on every row (`nets_unpaired` is 0 on both sides).

What level 5 did not judge, and why:

- **Nets that depend on a pour** (`route-unjudged`, 8 nets on the first row and 4 on the second). The
  document holds the poured copper of its polygons and Fenolite reads it as zone fills; KiCad's conversion
  holds the same zones without a fill. Such a net has several pieces in KiCad's read and cannot be
  compared. This is the non-goal "no judgement of unfilled zones".
- **Copper on no net** (6 items in Fenolite's read of the third row, 1 in KiCad's of the second). Level 5
  compares nets; these items are counted and not compared. Until change c0124 Fenolite's read of the
  first two rows held 74 and 43 more; "Lines on internal planes" below says what they were.
- **No stub notice.** The table above holds the third row as measured after change c0122. Before it
  the row gave `route-stub` 1 with 54 and 59 pieces; "The pour with holes" below says why.

### The pour with holes (change c0122)

The pour of `altium-third-party-pcbdoc-03` is one region with 268 holes and five more regions of the same
polygon, each of which lies inside one of those holes. Until change c0122 Fenolite's Altium adapter made a
zone fill from a region's outline and dropped its holes, so the five regions touched the main one in
Fenolite's read; KiCad's import keeps the holes. The adapter now builds each fill as one ring that holds
the outline and the holes (`geometry.keyhole_ring`; capability altium-import, "Zones from polygons").
Measured with `kicad-cli` 10.0.6 (macOS, local, 2026-10-06), Fenolite's read against KiCad's import:

| | before c0122 | after c0122 |
|---|---|---|
| pieces of copper, Fenolite's read, KiCad's import | 54, 59 | 59, 59 |
| pieces of copper that reach no pad, Fenolite's read, KiCad's import | 0, 5 | 5, 5 |
| level-5 differences | 0 | 0 |
| `route-stub` notices | 1 | 0 |
| fills of the zone, Fenolite's read, KiCad's import | 6, 6 | 6, 6 |
| points of those fills, Fenolite's read, KiCad's import | 180, 7 582 | 7 515, 7 582 |
| holes of poured regions in the fills, holes dropped (outside their outline or without area) | 0, all | 271 (268 of the main region, 3 of one other), 0 |

- The five islands are pieces of their own in both reads, so the notice is gone; nothing was loosened and
  no rule was added. `test_corpus_islands_in_the_holes_of_a_pour` asserts the pieces on both sides, and
  `NOTICES` of `tests/kicad/equivalence/test_triangle_level5.py` no longer holds the row.
- The two reads do not hold the same points: KiCad cuts its bridges elsewhere. Level 5 compares what the
  copper joins, not the ring.
- The other six rows are unchanged at every level (the numbers of the tables above are those of the run
  after the change).
- Over the seven rows the poured regions hold 607 holes (136, 58, 271, 27, 45, 30 and 40); every one is
  in a fill now and none was dropped, so `altium.import.zone-hole-outside` is given on no row.
- **The copper check on Fenolite's read of that row** (`checks.copper.check_copper`, without pads: the
  Altium backend has no board frame): `copper.short` 267 before and 0 after; `copper.clearance` 6 before
  and 266 after, of which 221 are a fill against a track and 45 a fill against a via. The 267 shorts were
  the tracks and vias of other nets inside holes of the pour. The clearance findings that take their
  place are measured against 0.5 mm, the clearance the model gives a zone that names none: the import
  reads no clearance for a polygon, and the gaps the document's pour keeps start at 0.127 mm. That the
  import gives a zone the model's default clearance is an open point outside change c0122: until the
  import reads a polygon's clearance (a task of change c0088), these 266 findings are an artefact of
  that default and say nothing about the document. Closed on 2026-10-07: since change c0088 the copper
  check on Altium input judges no pour against a default, and since change c0125 that row has a
  clearance in force from its own rule records; it reports 0 shorts and 7 clearance findings of another
  class (`docs/evidence/altium-roundtrip.md`, "Light DRC over the corpus"). None of the 266 remains.

### Lines on internal planes (change c0124)

The first two rows hold two internal planes each. A plane layer is stored in negative: what is drawn on it
is a place without copper. Each document holds free tracks without a net on those layers, the lines that
cut its planes: 74 and 43. Until change c0124 Fenolite's Altium adapter read them as tracks, which level 5
counted as copper on no net. The adapter now makes no entity of a free primitive on a plane layer
(capability altium-import, "Objects on an internal plane"). Measured with `kicad-cli` 10.0.6 (macOS,
local, 2026-10-06), Fenolite's read against KiCad's import:

| | row 01 before | row 01 after | row 02 before | row 02 after |
|---|---|---|---|---|
| tracks, Fenolite's read, KiCad's import | 1 420, 1 346 | 1 346, 1 346 | 234, 191 | 191, 191 |
| tracks and arcs on a plane layer, Fenolite's read, KiCad's import | 74, 0 | 0, 0 | 43, 0 | 0, 0 |
| copper on no net at level 5, Fenolite's read, KiCad's import | 74, 0 | 0, 0 | 43, 1 | 0, 1 |
| pieces of copper, both reads | 419, 419 | 419, 419 | 44, 44 | 44, 44 |
| level-5 differences, `route-unjudged` notices | 0, 8 | 0, 8 | 0, 4 | 0, 4 |

- KiCad's import makes no track of those lines: its boards held exactly 74 and 43 tracks fewer than
  Fenolite's read, and the two reads now hold the same number. `H-A-IMP-PLANE-CUT` is settled by this
  (`test_corpus_plane_cuts_are_no_tracks`), and `COPPER_NO_NET` of the test pins the last column of the
  table of the public documents.
- The two reads do not hold the planes in the same form, and neither holds their copper. KiCad's boards
  hold rule areas on the plane layers (136 and 93 on the two rows) and one zone without a fill per split
  plane (8 and 5); Fenolite's read holds the layer with the plane's net and the count of what cuts it
  (`plane_cuts`), and no zone. Level 5 compares neither rule areas nor unfilled zones, so nothing differs
  and nothing was loosened: no rule of the profile was added, and no probe outcome moved.
- Levels 1 to 4 and every other row are unchanged.

### Labels at level 5

By the rule of "Labels per level" (no `undecided` rule at that level or below):

| board | level 5 |
|---|---|
| routed sample, three pairs | ORACLE-VERIFIED(kicad-cli) (10.0.6), for the three nets that are judged; `GND` is not judged |
| altium-third-party-pcbdoc-01, -02 | INFERRED (an `undecided` rule matched at a lower level; 8 and 4 nets are not judged) |
| altium-third-party-pcbdoc-03 to -07 | ORACLE-VERIFIED(kicad-cli) (10.0.6); the third row since change c0122, which took its stub notice away |

`H-G-EQ-L5-TRIANGLE` is about the first row of this table. The Linux run of the `kicad-10` job is open: it
is the maintainer's, and it will compare six of the seven public rows, as at levels 1 to 4.
