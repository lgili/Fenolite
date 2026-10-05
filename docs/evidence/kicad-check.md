# `fenolite check` on the KiCad demo boards and projects

Counts only (change c0013, task 7.3). Measured on 2026-10-02 with kicad-cli 10.0.6 (macOS) by
`tests/kicad/check/test_check_demos.py` and `tests/kicad/check/test_canary.py` (`FENOLITE_CHECK_EVIDENCE`),
over the 21 readable non-heavy `rt0` demo boards, each in a folder with a `{}` project and a `(version 1)`
rules file, and over the 20 cached demo `project` rows whose board is one of those 21 (paired by tag and
file stem; none of them ships a rules file). Every copy was made in a temporary folder; nothing derived
from the corpus is kept.

| | demo boards | demo projects |
|---|---|---|
| runs | 21 | 20 |
| project folder unchanged (paths, SHA-256, `st_mtime_ns`) | 21 | 20 |
| `model.validate` `ok` / `errors` | 19 / 2 | 18 / 2 |
| `erc.lite` skipped (`native-input`); the stage of that date, replaced by `erc.kicad` in c0062 | 21 | 20 |
| `drc.kicad` `ok` | 21 | 20 |
| `roundtrip` `ok` | 21 | 20 |
| canary `fired` | 21 | 0 |
| canary `not-applicable` (no rules file) | 0 | 20 |
| `tool_writes` = `<stem>.kicad_prl` only | 21 | 20 |
| seconds per run: min / median / max | 1.8 / 4.5 / 26.5 | 1.2 / 3.3 / 21.5 |
| seconds in total | 160.1 | 120.4 |

The `model.validate` errors are the boards' own model findings (duplicate references, as the reader
already reports for them); every round trip passed with `opaque_count` equal to the reader's.

**Timings.** Measured again on 2026-10-02 after the two-run fallback, with other jobs sharing the
machine: a demo board now runs DRC twice (plain and canary), a demo project once (no rules file, so no
canary). Earlier the same day, with one DRC run per board, the board column read 0.8 / 1.9 / 12.6 s and
72.4 s in total on an idle machine, and 1.3 / 3.5 / 24.3 s and 132.8 s under the same load as above.

**Canary neutrality on the demo boards.** It does not hold, so both majors take the two-run fallback
(c0013 Decision 6; `H-K-CHECK-CANARY` refuted, `H-K-CHECK-CANARY-2`). On macOS 10.0.6 the stripped canary
report equals a plain run on 15 boards; on the other 6, kicad-cli does not repeat its own report between
identical runs (another partner item for some clearance violations, or another count: 864 to 869
violations over five plain runs of one board, 864 to 891 over five canary runs), so nothing could be
judged there. In the pinned Linux images with 4 CPUs, as on the CI runner, four plain and four canary
runs per board give:

| board | 10.0.6 plain / canary | 9.0.9 plain / canary |
|---|---|---|
| `kicad-demo-10-0-6-pcb-01` | 1597 each run / 1596 each run | not readable by 9.0 |
| `kicad-demo-10-0-6-pcb-07` | 475, one report / 475, another report | 500, one report / 501 in three runs |
| `kicad-demo-10-0-6-pcb-09` | 280, four reports / 280, four others | 281, three reports / 281, three others |
| `kicad-demo-10-0-6-pcb-11` | 867, one report / 867, another report | 819 to 821 / 821 to 822 |
| `kicad-demo-10-0-6-pcb-13` | 1302 each run / 1301 each run | 1101 to 1103 / 1099 to 1104 |
| `kicad-demo-10-0-6-pcb-16` | 887, mostly one report / 887, another report | 730, mostly one report / 730, another report |

"Another report" means the same count by type but other partner items for some clearance or unconnected
items. The three canary items (its clearance violation and two dangling-track warnings) are removed in
each canary run, so the differences are the canary tracks' effect on the rest of the run. The five
9.0.9.1 demo boards (at most 75 violations) give identical plain and canary reports on 9.0.9. With
`CANARY_TWO_RUN` = {9, 10}, the counted report comes from the plain run, and
`test_canary.py::test_two_run_demo_boards` checks on all 21 boards that the canary fires and that the
counted report holds no canary item. Two `check` runs on a board where KiCad does not repeat itself can
still give different DRC counts; the determinism of `check` is proved on authored projects
(`test_check_oracle.py -k deterministic`).

## Findings and assignment compare (change c0020)

Codes and counts only, measured on 2026-10-03 with kicad-cli 10.0.6 (macOS) by `fenolite check <project>
--json` on projects written into temporary folders (`tests/kicad/check/_fixtures.py`); the same tests pass
on 9.0.9 in the pinned image (`test_negatives.py`, `test_check_built.py`, `test_drc_facts.py`). Every
project is unrouted or seeded with a fault, so every run exits 5; the canary fired in each.

| project | findings (code: count) | (`model`, `board`): common / differences | (`board`, `export`): common / differences |
|---|---|---|---|
| authored built project (clean control) | `kicad.drc.unconnected-items`: 2 | 6 / 0 | 36 / 0 |
| reassigned pad (`R1` pad 2 on `GND`, board only) | `netlist.assignment-differs`: 1 at `R1-2`; `kicad.drc.shorting-items`: 1; `kicad.drc.solder-mask-bridge`: 1; `kicad.drc.unconnected-items`: 3 | 6 / 1 | 36 / 0 |
| bridging track (`VIN` across `R1`) | `kicad.drc.shorting-items`: 1 naming `R1-2`; `kicad.drc.solder-mask-bridge`: 1; `kicad.drc.tracks-crossing`: 1; `kicad.drc.unconnected-items`: 2 | 6 / 0 | 36 / 0 |
| overlap bench, forward (positive control) | `kicad.drc.clearance`: 2 (the `ord` pair and c0018's canary pair); `kicad.drc.track-dangling`: 4 warnings | native input | 0 / 0 |
| overlap bench, reverse | `kicad.drc.clearance`: 1 (the canary pair only); `kicad.drc.track-dangling`: 4 warnings | native input | 0 / 0 |
| blink built for target 9 | `kicad.drc.unconnected-items`: 3, each naming `REF-PIN` pads | 36 / 0 | 36 / 0 |
| blink built for target 10 | `kicad.drc.unconnected-items`: 3, each naming `REF-PIN` pads | 36 / 0 | 36 / 0 |

Both seeded faults are located at `R1-2`. The positive control gives the `ord` clearance with the later rule
governing (forward) and not with the rules reversed, c0018's canary firing in both. The clean control gives
neither `netlist.assignment-differs` nor `kicad.drc.shorting-items`. The authored model lists no pins for
its components, so its (`model`, `board`) pair covers the 6 pads that its nets name, and the 30 other pads
are one `netlist.uncovered` info (`not-in-model`); the blink's model lists every pin. The bench has no
footprints, so its (`board`, `export`) pair is empty.

## DRC repeatability on the demo boards (change c0051)

Ids and counts only. What two `pcb drc --format json --severity-all` runs of one unchanged project share
(`H-K-DRC-REPEAT`), measured over the 21 readable non-heavy demo boards, each in a temporary folder with
a `{}` project and a `(version 1)` rules file. Per board: N times a plain run and a canary run, with the
calls of `KicadOracle.drc`. Per run: whether the canary fired, the totals, the count per type,
`DrcReport.entries()` of the stripped report, the report in report order, and the report sorted with item
uuids. Nothing derived from the corpus is kept.

Columns. A "distinct report" is the report sorted, with item uuids and positions; a "distinct order" is
the report as written. A key is an entry of `DrcReport.entries()` (type, severity, excluded, the
description and position of each item); it is unstable when its count differs between runs. The canary
column counts the canary run after `strip_canary`.

### kicad-cli 10.0.6, macOS, 15 pairs per board (2026-10-04)

Conditions: 10 cores, load average 23 to 32 (other test suites ran on the machine), one DRC at a time;
0.5 / 1.8 / 8.3 s per DRC run (minimum / median / maximum).

| board | pairs | canary `fired` | violations / unconnected (plain) | violations (canary run, stripped) | distinct reports, plain / canary | distinct orders, plain / canary | types whose count varies | unstable keys by type (plain and canary runs together) |
|---|---|---|---|---|---|---|---|---|
| `kicad-demo-10-0-6-pcb-01` | 15 | 15 of 15 | 1597 / 0 | 1596 | 15 / 15 | 15 / 15 | `clearance` | `clearance`: 812, `hole_clearance`: 267 |
| `kicad-demo-10-0-6-pcb-02` | 15 | 15 of 15 | 69 / 0 | 69 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-03` | 15 | 15 of 15 | 17 / 0 | 17 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-04` | 15 | 15 of 15 | 19 / 0 | 19 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-05` | 15 | 15 of 15 | 28 / 0 | 28 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-07` | 15 | 15 of 15 | 469 to 483 / 0 | 472 to 486 | 15 / 15 | 15 / 15 | `clearance` | `clearance`: 70 |
| `kicad-demo-10-0-6-pcb-08` | 15 | 15 of 15 | 24 / 0 | 24 | 1 / 1 | 8 / 8 | none | none |
| `kicad-demo-10-0-6-pcb-09` | 15 | 15 of 15 | 132 / 148 | 132 | 7 / 5 | 7 / 5 | none | `unconnected_items`: 17 |
| `kicad-demo-10-0-6-pcb-10` | 15 | 15 of 15 | 120 / 0 | 120 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-11` | 15 | 15 of 15 | 864 to 894 / 0 | 862 to 893 | 13 / 14 | 15 / 15 | `clearance` | `clearance`: 183 |
| `kicad-demo-10-0-6-pcb-12` | 15 | 15 of 15 | 75 / 0 | 75 | 1 / 1 | 7 / 9 | none | none |
| `kicad-demo-10-0-6-pcb-13` | 15 | 15 of 15 | 1299 to 1300 / 0 | 1299 | 15 / 15 | 15 / 15 | `clearance`, `hole_clearance` | `clearance`: 813, `hole_clearance`: 1 |
| `kicad-demo-10-0-6-pcb-14` | 15 | 15 of 15 | 8 / 0 | 8 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-15` | 15 | 15 of 15 | 63 / 0 | 63 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-16` | 15 | 15 of 15 | 887 / 1 | 887 | 7 / 3 | 15 / 13 | none | `clearance`: 5, `unconnected_items`: 4 |
| `kicad-demo-10-0-6-pcb-17` | 15 | 15 of 15 | 248 / 0 | 248 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-9-0-9-1-pcb-01` | 15 | 15 of 15 | 9 / 0 | 9 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-9-0-9-1-pcb-02` | 15 | 15 of 15 | 73 / 0 | 73 | 1 / 1 | 6 / 4 | none | none |
| `kicad-demo-9-0-9-1-pcb-03` | 15 | 15 of 15 | 75 / 0 | 75 | 1 / 1 | 4 / 5 | none | none |
| `kicad-demo-9-0-9-1-pcb-05` | 15 | 15 of 15 | 4 / 0 | 4 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-9-0-9-1-pcb-06` | 15 | 15 of 15 | 48 / 0 | 48 | 1 / 1 | 1 / 1 | none | none |

What differs between runs:

- **Order only**, on 4 boards (`kicad-demo-10-0-6-pcb-08`, `-12`, `kicad-demo-9-0-9-1-pcb-02`, `-03`): up to 9
  orders in 15 runs, one sorted report.
- **Nothing**, on 11 boards.
- **Content**, on 6 boards (`kicad-demo-10-0-6-pcb-01`, `-07`, `-09`, `-11`, `-13`, `-16`), and only in
  entries of the types `clearance`, `hole_clearance` and `unconnected_items`: other partner items, mostly
  at another position too (on `-01`, 1061 of the 1079 unstable keys also differ as type-and-position
  keys; on `-09`, 5 of the 17 unstable keys keep their positions and name another item), and another
  count of a type (`clearance` 128 to 145 on `-07`, 231 to 263 on `-11`; `hole_clearance` 61 or 62 on
  `-13`). On `-09` and `-16` the counts per type repeat and only the entries differ.
- **Never**: an entry of any other type (the boards hold up to 18 types), the return code, or the files
  the tool wrote.

`tests/kicad/check/test_canary.py::test_two_run_demo_boards` checks this on every run of the `kicad-10`
job: two `KicadOracle.drc` outcomes per board, compared by `tests/_drcrepeat.py`. A board or a type joins
a named set only with a measurement of at least 15 runs per board recorded here.

### kicad-cli 10.0.6, pinned Linux image, 15 pairs per board

The image the `kicad-10` job runs (`kicad/kicad:10.0.6`, pinned by digest), on the same machine through
Docker (`linux/amd64`, 10 CPUs), while other test suites ran; 1.5 / 6.1 / 19.6 s per DRC run
(2026-10-04). The canary fired in 315 of 315 canary runs. The same six boards differ in content and in
the same three types, and no other board or type does. On `-07` and `-11` the 15 plain runs give one
report and the 15 canary runs another, so their unstable keys are differences between a plain and a
canary run. `-01` and `-13` report 499 `clearance` violations in every plain run and 498 in every canary
run, as on macOS. The totals differ from macOS on `-13` (1302 against 1299 or 1300) and `-16` (886 against
887).

| board | pairs | canary `fired` | violations / unconnected (plain) | violations (canary run, stripped) | distinct reports, plain / canary | distinct orders, plain / canary | types whose count varies | unstable keys by type (plain and canary runs together) |
|---|---|---|---|---|---|---|---|---|
| `kicad-demo-10-0-6-pcb-01` | 15 | 15 of 15 | 1597 / 0 | 1596 | 15 / 15 | 15 / 15 | `clearance` | `clearance`: 283, `hole_clearance`: 82 |
| `kicad-demo-10-0-6-pcb-02` | 15 | 15 of 15 | 69 / 0 | 69 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-03` | 15 | 15 of 15 | 17 / 0 | 17 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-04` | 15 | 15 of 15 | 19 / 0 | 19 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-05` | 15 | 15 of 15 | 28 / 0 | 28 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-07` | 15 | 15 of 15 | 475 / 0 | 475 | 1 / 1 | 15 / 15 | none | `clearance`: 28 |
| `kicad-demo-10-0-6-pcb-08` | 15 | 15 of 15 | 24 / 0 | 24 | 1 / 1 | 9 / 7 | none | none |
| `kicad-demo-10-0-6-pcb-09` | 15 | 15 of 15 | 132 / 148 | 132 | 10 / 11 | 10 / 11 | none | `unconnected_items`: 10 |
| `kicad-demo-10-0-6-pcb-10` | 15 | 15 of 15 | 120 / 0 | 120 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-11` | 15 | 15 of 15 | 867 / 0 | 867 | 1 / 1 | 15 / 15 | none | `clearance`: 54 |
| `kicad-demo-10-0-6-pcb-12` | 15 | 15 of 15 | 75 / 0 | 75 | 1 / 1 | 11 / 7 | none | none |
| `kicad-demo-10-0-6-pcb-13` | 15 | 15 of 15 | 1302 / 0 | 1301 | 15 / 15 | 15 / 15 | `clearance` | `clearance`: 175 |
| `kicad-demo-10-0-6-pcb-14` | 15 | 15 of 15 | 8 / 0 | 8 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-15` | 15 | 15 of 15 | 63 / 0 | 63 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-16` | 15 | 15 of 15 | 886 / 1 | 886 | 2 / 2 | 15 / 15 | none | `clearance`: 2, `unconnected_items`: 2 |
| `kicad-demo-10-0-6-pcb-17` | 15 | 15 of 15 | 248 / 0 | 248 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-9-0-9-1-pcb-01` | 15 | 15 of 15 | 9 / 0 | 9 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-9-0-9-1-pcb-02` | 15 | 15 of 15 | 73 / 0 | 73 | 1 / 1 | 6 / 4 | none | none |
| `kicad-demo-9-0-9-1-pcb-03` | 15 | 15 of 15 | 75 / 0 | 75 | 1 / 1 | 12 / 7 | none | none |
| `kicad-demo-9-0-9-1-pcb-05` | 15 | 15 of 15 | 4 / 0 | 4 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-9-0-9-1-pcb-06` | 15 | 15 of 15 | 48 / 0 | 48 | 1 / 1 | 1 / 1 | none | none |

### kicad-cli 9.0.9, pinned Linux image, 15 pairs per board

The image the `kicad-9` job runs (`kicad/kicad:9.0.9`, pinned by digest), through Docker (`linux/amd64`,
10 CPUs), while other test suites ran; 1.5 / 3.4 / 19.8 s per DRC run (2026-10-04). 9.0.9 loads 19 of the
21 boards ("Failed to load board" for `-01` and `-12`, one pair each). The boards that differ in content
are five of the six named ones (`-01` does not load), in the same three types; no other board or type
differs. `-13` holds 502 to 507 `clearance` violations in every run, above the limit, and its canary pair
is missing from 15 of 15 canary runs: before change c0051 `check` called that `absent`, now
`inconclusive` (`clearance-limit`). On the 18 other boards the canary fired in 270 of 270 runs. This
table is supporting data: `test_two_run_demo_boards` runs on 10.0.6 only, so the label of
`H-K-DRC-REPEAT` stays `(10.0.x)`.

| board | pairs | canary `fired` | violations / unconnected (plain) | violations (canary run, stripped) | distinct reports, plain / canary | distinct orders, plain / canary | types whose count varies | unstable keys by type (plain and canary runs together) |
|---|---|---|---|---|---|---|---|---|
| `kicad-demo-10-0-6-pcb-01` | 1 | no report: plain 1, canary 1 | | | | | | |
| `kicad-demo-10-0-6-pcb-02` | 15 | 15 of 15 | 68 / 0 | 68 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-03` | 15 | 15 of 15 | 17 / 0 | 17 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-04` | 15 | 15 of 15 | 19 / 0 | 19 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-05` | 15 | 15 of 15 | 27 / 0 | 27 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-07` | 15 | 15 of 15 | 499 to 500 / 0 | 500 to 501 | 2 / 3 | 15 / 15 | `clearance` | `clearance`: 25 |
| `kicad-demo-10-0-6-pcb-08` | 15 | 15 of 15 | 24 / 0 | 24 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-09` | 15 | 15 of 15 | 133 / 148 | 133 | 5 / 8 | 5 / 8 | none | `unconnected_items`: 10 |
| `kicad-demo-10-0-6-pcb-10` | 15 | 15 of 15 | 120 / 0 | 120 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-11` | 15 | 15 of 15 | 819 to 822 / 0 | 821 to 822 | 10 / 2 | 15 / 15 | `clearance` | `clearance`: 34 |
| `kicad-demo-10-0-6-pcb-12` | 1 | no report: plain 1, canary 1 | | | | | | |
| `kicad-demo-10-0-6-pcb-13` | 15 | 0 of 15 | 1101 to 1105 / 0 | 1100 to 1105 | 15 / 15 | 15 / 15 | `clearance`, `hole_clearance` | `clearance`: 159, `hole_clearance`: 1 |
| `kicad-demo-10-0-6-pcb-14` | 15 | 15 of 15 | 8 / 0 | 8 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-15` | 15 | 15 of 15 | 62 / 0 | 62 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-10-0-6-pcb-16` | 15 | 15 of 15 | 729 / 1 | 729 | 3 / 3 | 6 / 6 | none | `clearance`: 6, `unconnected_items`: 3 |
| `kicad-demo-10-0-6-pcb-17` | 15 | 15 of 15 | 243 / 0 | 243 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-9-0-9-1-pcb-01` | 15 | 15 of 15 | 8 / 0 | 8 | 1 / 1 | 5 / 6 | none | none |
| `kicad-demo-9-0-9-1-pcb-02` | 15 | 15 of 15 | 73 / 0 | 73 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-9-0-9-1-pcb-03` | 15 | 15 of 15 | 75 / 0 | 75 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-9-0-9-1-pcb-05` | 15 | 15 of 15 | 4 / 0 | 4 | 1 / 1 | 1 / 1 | none | none |
| `kicad-demo-9-0-9-1-pcb-06` | 15 | 15 of 15 | 48 / 0 | 48 | 1 / 1 | 1 / 1 | none | none |

### `--all-track-errors` (supporting data; the flag is not used)

`pcb drc` has the flag `--all-track-errors` ("Report all errors for each track", S-0022). Six plain runs
per board with the flag, 10.0.6 (macOS):

| board | violations / unconnected with the flag (six runs) | distinct sorted reports |
|---|---|---|
| `kicad-demo-10-0-6-pcb-01` | 1597 / 0 | 6 |
| `kicad-demo-10-0-6-pcb-07` | 536 / 0 | 1 |
| `kicad-demo-10-0-6-pcb-09` | 132 / 148 | 4 |
| `kicad-demo-10-0-6-pcb-11` | 1003 / 0 | 1 |
| `kicad-demo-10-0-6-pcb-13` | 1300 / 0 | 6 |
| `kicad-demo-10-0-6-pcb-16` | 896 / 1 | 3 |

The totals repeat on all six boards and two boards repeat whole; the others still name other items. A
likely cause of the spread without the flag is that KiCad stops at one violation per track and finds
another one first in another run (`INFERRED`; no public statement found).

## Clearance report limit (change c0051)

Ids and counts only (`H-K-DRC-LIMIT`, `H-K-CHECK-CANARY-3`).

### Stress run on the largest demo boards: kicad-cli 10.0.6, macOS, 40 pairs per board (2026-10-04)

| board | `clearance` violations, plain run | canary runs | canary pair missing | stripped canary report when the pair is present / missing |
|---|---|---|---|---|
| `kicad-demo-10-0-6-pcb-01` | 499 | 40 | 3 | 1596 (498 `clearance`) / 1597 (499 `clearance`) |
| `kicad-demo-10-0-6-pcb-13` | 499 | 40 | 1 | 1298 or 1299 (498 `clearance`) / 1300 (499 `clearance`) |
| `kicad-demo-10-0-6-pcb-16` | 12 | 40 | 0 | 887 or 888 / none |
| `kicad-demo-10-0-6-pcb-17` | 0 | 40 | 0 | 248 / none |

In each of the four runs without the pair, the two `track_dangling` warnings of the canary tracks were
present, so the tracks were loaded, and the report held 499 `clearance` violations of the board instead
of 498 and the canary's. Both boards report exactly 499 `clearance` violations in every plain run. With
the 15 pairs of the table above: the pair is missing from 4 of 110 canary runs of the two saturated
boards, and from none of the 365 canary runs of the 19 other boards.

### Authored bench (2026-10-04)

`tests/data/kicad/board/two_layer.kicad_pcb` (one `clearance` violation of its own) with N more pairs of
`F.Cu` tracks, each pair on two nets of its own with a 0.05 mm gap, a `{}` project and a `(version 1)`
rules file (`tests/kicad/check/_limitbench.py`). Each row: a plain run and a canary run, repeated.

| build | pairs | `clearance` in the plain run | `clearance` in the canary run, canary included | canary fired |
|---|---|---|---|---|
| 10.0.6 macOS | 300 | 301 | 302 | 6 of 6 |
| 10.0.6 macOS | 497 | 498 | 499 | 6 of 6 |
| 10.0.6 macOS | 498, 499, 500 | 499 | 499 | 6 of 6 each |
| 10.0.6 macOS | 700 | 499 | 499 | 5 of 6 |
| 10.0.6 pinned Linux image | 497 | 498 | 499 | 4 of 4 |
| 10.0.6 pinned Linux image | 498 | 499 | 499 | 4 of 4 |
| 10.0.6 pinned Linux image | 700 | 499 | 499 | 4 of 4 |
| 9.0.9 pinned Linux image | 497 | 498 | 499 | 4 of 4 |
| 9.0.9 pinned Linux image | 498 | 499 | 499 | 4 of 4 |
| 9.0.9 pinned Linux image | 700 | 507 | 502 to 508 | 1 of 4 |

`kicad-cli` reports at most 499 `clearance` violations on 10.0.6 and stops a little above 499 on 9.0.9.
Below 499 the canary always fired. No public statement of the limit was found in the manuals (S-0010,
S-0022, S-0038); it is measured (S-0020). `KicadOracle.drc` therefore gives `inconclusive` with reason
`clearance-limit`, not `absent`, when the canary run's report holds no canary pair and at least
`CLEARANCE_REPORT_LIMIT` = 499 `clearance` violations; it does not repeat the run.

## ERC and schematic parity (change c0062)

Measured on 2026-10-05 with `kicad-cli` 10.0.6 (macOS) and 9.0.9 (pinned image) by
`tests/kicad/check/test_erc_facts.py`, `test_erc_oracle.py`, `test_parity.py` and `test_copy_set.py`.
Every case starts from the blink that `build` writes for the running major and changes one thing by
token edit. The outcomes are the probes of `docs/evidence/kicad/probes/<version>.json`.

| probe | 9.0.9 | 10.0.6 |
|---|---|---|
| `erc-report-keys` (the keys of `erc.REQUIRED_KEYS`, exit 0 with and without violations) | equal | equal |
| `erc-ignored-checks` | absent | present |
| `erc-unloadable` (an unknown root child: exit 3, `Failed to load schematic`, no report) | absent | absent |
| `erc-writes-prl` (`<stem>.kicad_prl` beside the input) | absent | present |
| `erc-position-scale` (five open pins reported at their connection points, positions times 100) | equal | equal |
| `erc-type-pin-not-connected`, `-pin-not-driven`, `-power-pin-not-driven`, `-lib-symbol-issues` | present | present |
| `erc-type-isolated-pin-label` / `erc-type-global-label-dangling` (a label alone on one pin) | absent / present | present / absent |
| `erc-type-<type>-ignored`, five controls (`ignore` in `erc.rule_severities`) | absent | absent |
| `erc-sev-<type>-warning`, five controls (`warning` in `erc.rule_severities`) | equal | equal |
| `erc-copyset` (the built blink and the authored hierarchy, each with decoys) | equal | equal |
| `check-copyset-schematic` (DRC with parity on the copy set against the whole folder) | equal | equal |
| `drc-parity-flag` / `drc-parity-noflag` (a pad on another net) | present / absent | present / absent |
| `drc-parity-canary` (the staged canary run against the plain run) | equal | equal |
| `drc-parity-unloadable` (the flag with a schematic that does not load: exit 255, no report) | absent | absent |

- **Default severities of the controls.** `pin_not_connected`, `pin_not_driven` and
  `power_pin_not_driven` are errors; `lib_symbol_issues` and the single-pin label are warnings. With
  `ignore`, 10.0.6 lists the key in `ignored_checks`; 9.0.9 has no such list.
- **Copy set on corpus projects.** The first three root rows of the acceptance list that each major
  loads give equal entries for the copy set and the whole demo folder
  (`test_copy_set_corpus_projects`), on both majors.
- **Sheets used twice.** A check that looks at a sheet file is listed under the root sheet `/` with the
  reference of one use; the item is then located by its position, never by a guessed reference.
- **A schematic that does not load.** `erc.kicad` reports `check.oracle-failed`; the DRC run with the
  parity flag writes no report, so the oracle runs it again without the flag and the stage reports
  `kicad.drc.parity-unchecked` with the canary state and the findings of that second run.
- **The examples.** `examples/blink_2layer` and `examples/board_40parts`, built for targets 9 and 10 and
  checked with 10.0.6: `erc.kicad` `ok` with 0 violations, and `drc.kicad` with `parity_judged` true and
  `parity` 0. `examples/blink_routed` had 29 `pin_not_connected` and 2 `pin_not_driven` errors until its
  unused pins were marked. `examples/blink_official` takes its symbols from KiCad's own libraries and
  leaves pins open: 27 `pin_not_connected`, 2 `power_pin_not_driven` and one `ground_pin_not_ground`
  warning on 10.0.6, findings of that design.
- **Time of the stage** (10.0.6, macOS, median of three `fenolite check --stages …` runs, other jobs
  sharing the machine): `erc.kicad` 1.7 s on the blink and 1.8 s on the 40-part board; `drc.kicad`, two
  runs with the canary, 2.9 s and 3.5 s; the two tool-free stages `model.validate,roundtrip` 1.0 s and
  1.4 s. Most of each figure is the start of the interpreter and of `kicad-cli`.
