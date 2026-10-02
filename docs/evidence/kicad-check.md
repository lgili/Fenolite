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
| `erc.lite` skipped (`native-input`) | 21 | 20 |
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
