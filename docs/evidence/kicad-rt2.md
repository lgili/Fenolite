# RT0, RT1 and RT2 over the corpus

Ids and counts only (change c0020, task 5.3; capability kicad-oracle, "Corpus round trips RT0 to RT2").
Measured on 2026-10-03 by `tests/kicad/check/test_corpus_rt.py` (`FENOLITE_CENSUS_OUT`). Each board is
checked in a temporary folder with a `{}` project and a `(version 1)` rules file; the corpus cache is only
read, and nothing derived from it is kept.

- **RT0**: `parse` → `dumps` → `parse` gives an equal tree.
- **RT1**: the board rebuilds to itself, and the re-read model and the opaque counts agree (`roundtrip`).
- **RT2**: KiCad's DRC gives the same violations for the board and for Fenolite's re-dump (`roundtrip.rt2`).
  Violations are keyed without item uuids. A key that differs between runs of one file is unstable and is
  left out. A difference fails RT2 only when no key is unstable; otherwise RT2 is not judged on that board.

## kicad-cli 10.0.6 (macOS, local): 24 boards

The 21 readable non-heavy demo boards as cached, and the three third-party boards re-saved once with
`pcb upgrade --force` (their origin stays `third-party`). Both sides are re-saved with `pcb upgrade` before
DRC, except `third-party-pcb-02`, whose two upgrades differ (`H-K-FMT-RESAVE`).

| board | opaque count | RT0, RT1 | RT2 | normalised | runs (original + re-dump) | original: violations / unconnected | re-dump: violations / unconnected | unstable keys | other differences | seconds |
|---|---|---|---|---|---|---|---|---|---|---|
| `kicad-demo-10-0-6-pcb-01` | 7456 | ok | holds | yes | 5 + 4 | 1598 / 0 | 1598 / 0 | 1011 | 0 | 39.2 |
| `kicad-demo-10-0-6-pcb-02` | 2961 | ok | holds | yes | 2 + 1 | 69 / 0 | 69 / 0 | 0 | 0 | 6.1 |
| `kicad-demo-10-0-6-pcb-03` | 648 | ok | holds | yes | 2 + 1 | 17 / 0 | 17 / 0 | 0 | 0 | 3.5 |
| `kicad-demo-10-0-6-pcb-04` | 695 | ok | holds | yes | 2 + 1 | 19 / 0 | 19 / 0 | 0 | 0 | 3.5 |
| `kicad-demo-10-0-6-pcb-05` | 2089 | ok | holds | yes | 2 + 1 | 28 / 0 | 28 / 0 | 0 | 0 | 5.9 |
| `kicad-demo-10-0-6-pcb-07` | 6702 | ok | holds | yes | 5 + 4 | 475 / 0 | 475 / 0 | 29 | 0 | 24.3 |
| `kicad-demo-10-0-6-pcb-08` | 36 | ok | holds | yes | 2 + 1 | 24 / 0 | 24 / 0 | 0 | 0 | 2.4 |
| `kicad-demo-10-0-6-pcb-09` | 6999 | ok | holds | yes | 5 + 4 | 132 / 148 | 132 / 148 | 11 | 0 | 15.6 |
| `kicad-demo-10-0-6-pcb-10` | 6886 | ok | holds | yes | 2 + 1 | 120 / 0 | 120 / 0 | 0 | 0 | 9.6 |
| `kicad-demo-10-0-6-pcb-11` | 5963 | ok | holds | yes | 5 + 4 | 862 / 0 | 863 / 0 | 41 | 0 | 33.8 |
| `kicad-demo-10-0-6-pcb-12` | 2536 | ok | holds | yes | 2 + 1 | 75 / 0 | 75 / 0 | 0 | 0 | 5.8 |
| `kicad-demo-10-0-6-pcb-13` | 3681 | ok | not judged | yes | 5 + 4 | 1300 / 0 | 1300 / 0 | 841 | 18 | 28.8 |
| `kicad-demo-10-0-6-pcb-14` | 96 | ok | holds | yes | 2 + 1 | 8 / 0 | 8 / 0 | 0 | 0 | 3.2 |
| `kicad-demo-10-0-6-pcb-15` | 1245 | ok | holds | yes | 2 + 1 | 63 / 0 | 63 / 0 | 0 | 0 | 4.2 |
| `kicad-demo-10-0-6-pcb-16` | 8568 | ok | holds | yes | 2 + 1 | 888 / 1 | 888 / 1 | 0 | 0 | 29.9 |
| `kicad-demo-10-0-6-pcb-17` | 11197 | ok | holds | yes | 2 + 1 | 248 / 0 | 248 / 0 | 0 | 0 | 35.3 |
| `kicad-demo-9-0-9-1-pcb-01` | 143 | ok | holds | yes | 2 + 1 | 9 / 0 | 9 / 0 | 0 | 0 | 3.3 |
| `kicad-demo-9-0-9-1-pcb-02` | 3139 | ok | holds | yes | 2 + 1 | 73 / 0 | 73 / 0 | 0 | 0 | 7.2 |
| `kicad-demo-9-0-9-1-pcb-03` | 2692 | ok | holds | yes | 2 + 1 | 75 / 0 | 75 / 0 | 0 | 0 | 5.8 |
| `kicad-demo-9-0-9-1-pcb-05` | 102 | ok | holds | yes | 2 + 1 | 4 / 0 | 4 / 0 | 0 | 0 | 2.8 |
| `kicad-demo-9-0-9-1-pcb-06` | 2403 | ok | holds | yes | 2 + 1 | 48 / 0 | 48 / 0 | 0 | 0 | 5.7 |
| `third-party-pcb-01` | 7303 | ok | holds | yes | 5 + 4 | 1231 / 1 | 1231 / 1 | 732 | 0 | 23.5 |
| `third-party-pcb-02` | 5139 | ok | holds | no | 5 + 4 | 630 / 0 | 630 / 0 | 96 | 0 | 16.3 |
| `third-party-pcb-03` | 9876 | ok | holds | yes | 5 + 4 | 1241 / 0 | 1241 / 0 | 161 | 0 | 27.4 |

RT0 and RT1 hold on all 24 boards. RT2 fails on none: it holds on 23 and is not judged on
1 (`kicad-demo-10-0-6-pcb-13`). 16 boards gave equal reports in the first three runs. On
the other 8, the first re-dump report differed from the original's, so each side ran three more times:
KiCad does not repeat its own report on those boards, with up to 1011 unstable keys on one board. There,
"holds" covers only the keys that every run of both sides gave; it says nothing about the rest. The run
took 343.1 s in total.

## kicad-cli 9.0.9 (pinned image): the five `rt2-9` rows

9.0 has no `pcb upgrade`, so the files are checked as they are (`normalised` no).

| board | opaque count | RT0, RT1 | RT2 | normalised | runs (original + re-dump) | original: violations / unconnected | re-dump: violations / unconnected | unstable keys | other differences | seconds |
|---|---|---|---|---|---|---|---|---|---|---|
| `kicad-demo-9-0-9-1-pcb-01` | 143 | ok | holds | no | 2 + 1 | 8 / 0 | 8 / 0 | 0 | 0 | 5.5 |
| `kicad-demo-9-0-9-1-pcb-02` | 3139 | ok | holds | no | 2 + 1 | 73 / 0 | 73 / 0 | 0 | 0 | 12.4 |
| `kicad-demo-9-0-9-1-pcb-03` | 2692 | ok | holds | no | 2 + 1 | 75 / 0 | 75 / 0 | 0 | 0 | 9.7 |
| `kicad-demo-9-0-9-1-pcb-05` | 102 | ok | holds | no | 2 + 1 | 4 / 0 | 4 / 0 | 0 | 0 | 4.0 |
| `kicad-demo-9-0-9-1-pcb-06` | 2403 | ok | holds | no | 2 + 1 | 48 / 0 | 48 / 0 | 0 | 0 | 10.5 |

RT0, RT1 and RT2 hold on the five boards, with no unstable key. In the same image, with only these five
rows cached, the rest of `tests/kicad` passes or skips (262 passed, 270 skipped). A cache that lacks one of
the five rows fails the test naming the row, and an empty cache skips it with the fetch hint.

## What KiCad does not repeat

Measured on 10.0.6 (macOS) with plain runs of one unchanged file, three runs per board, as the largest
difference from the first run:

| board | violations | pairs of items that differ | items named that differ | counts by type that differ |
|---|---|---|---|---|
| `kicad-demo-10-0-6-pcb-01` | 1597 | 362 | 122 of 998 | 0 |
| `kicad-demo-10-0-6-pcb-07` | 474 | 8 | 6 of 549 | 4 |
| `kicad-demo-10-0-6-pcb-11` | 864 | 41 | 35 of 950 | 27 |
| `kicad-demo-10-0-6-pcb-13` | 1300 | 646 | 192 of 759 | 1 |

Between two runs KiCad names other partner items, lists other items, reports one conflict as `clearance`
in one run and as `hole_clearance` in the next, and on some boards gives another total. No finer view of
the report repeats on these boards, so `H-K-RT2-STABLE` is refuted and `H-K-RT2-STABLE-2` records the part
that holds: reports repeat on boards with few violations, and where they do not, RT2 is not judged.
