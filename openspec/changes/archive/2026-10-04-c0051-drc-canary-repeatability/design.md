## Context

`KicadOracle.drc` runs `pcb drc` twice on a project with a rules file: a plain run gives the counted
report and a canary run gives the verdict on the custom rules (`CANARY_TWO_RUN`, c0013 Decision 6,
`H-K-CHECK-CANARY-2`). `tests/kicad/check/test_canary.py::test_two_run_demo_boards` runs it on the
21 readable non-heavy demo boards and asserts three things: the canary state is `fired`,
`canary_removed` is 0, and the counted report names no canary uuid. It compares nothing between
runs.

Its occasional failure is `canary` = `absent` on one of the two largest boards. This change measures
why (below) and finds a fault of the product, not of the test.

Earlier records say that KiCad does not repeat its DRC report on large boards (`H-K-CHECK-CANARY`,
`H-K-RT2-STABLE-2`, `docs/evidence/kicad-check.md`, `docs/evidence/kicad-rt2.md`). The two failed
`kicad-10` runs on record (37004360203 and 37017544405) failed `test_canary_neutral_demo_boards`,
the predecessor that compared a stripped canary run with a plain run; c0013 replaced it. No CI run
since then failed `test_two_run_demo_boards` (checked with `gh run list --status failure` on
2026-10-04: the only later failure is `tests/kicad/altium/test_pcbdoc_oracle.py`, noted under
"Found outside this change").

## Measurement (2026-10-04)

Method: for each board, a folder with the cached board, a `{}` project and a `(version 1)` rules
file (`tests/_projects.py::demo_project`); then N times a plain run and a canary run, with the same
calls as `KicadOracle.drc` (`_plan`, `_run`). Per run: the outcome, whether the canary fired, the
canary items, the totals, the count per type, `DrcReport.entries()` of the stripped report, a hash
of the report in report order and a hash of it sorted with item uuids. Nothing derived from the
corpus is kept: ids and counts only.

### kicad-cli 10.0.6, macOS, 15 pairs per board

Conditions: 10 cores, load average 23 to 32 (other test suites ran on the machine), one DRC at a
time, 0.5 / 1.8 / 8.3 s per run (minimum / median / maximum).

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

Columns: a "distinct report" is the report sorted, with item uuids and positions; a "distinct
order" is the report as written. A key is an entry of `DrcReport.entries()` (type, severity,
excluded, the description and position of each item); it is unstable when its count differs between
runs. The canary column counts the canary run after `strip_canary`; the three canary items (its
`clearance` violation and two `track_dangling` warnings) were present in every canary run.

What differs between runs:

1. **Order only**, on 4 boards (`-08`, `-12`, `kicad-demo-9-0-9-1-pcb-02`, `-03`): up to 9 orders in
   15 runs, one sorted report.
2. **Nothing**, on 11 boards: one order, one report.
3. **Content**, on 6 boards (`-01`, `-07`, `-09`, `-11`, `-13`, `-16`), and only in entries of the
   types `clearance`, `hole_clearance` and `unconnected_items`:
   - other partner items for a violation, mostly at another position too (on `-01`, 1061 of the
     1079 unstable keys also differ as type-and-position keys); on `-09`, 5 of the 17 unstable
     `unconnected_items` keys keep their positions and name another item;
   - another count of a type: `clearance` on `-07` (128 to 145), `-11` (231 to 263) and `-13`
     (498 or 499), `hole_clearance` on `-13` (61 or 62); on `-01` the plain runs give 499
     `clearance` entries and the canary runs 498, each in all 15 runs.
   - On `-09` and `-16` the totals and the counts per type repeat; only the entries differ.
4. **Never**: an entry of any other type (the boards hold up to 18 types), the return code, the
   files the tool wrote, or the canary verdict.

The test as written would have passed in 315 of 315 pairs.

### Stress run: the canary goes missing (10.0.6, macOS, 40 pairs per board)

The four largest boards, 40 more pairs each, same conditions.

| board | `clearance` violations, plain run | canary runs | canary pair missing | stripped canary report when the pair is present / missing |
|---|---|---|---|---|
| `kicad-demo-10-0-6-pcb-01` | 499 | 40 | 3 | 1596 (498 `clearance`) / 1597 (499 `clearance`) |
| `kicad-demo-10-0-6-pcb-13` | 499 | 40 | 1 | 1298 or 1299 (498 `clearance`) / 1300 (499 `clearance`) |
| `kicad-demo-10-0-6-pcb-16` | 12 | 40 | 0 | 887 or 888 / none |
| `kicad-demo-10-0-6-pcb-17` | 0 | 40 | 0 | 248 / none |

In each of the four runs the two `track_dangling` warnings of the canary tracks were present, so
the tracks were loaded, and the report held 499 `clearance` violations of the board instead of 498
and the canary's. Both boards report exactly 499 `clearance` violations in every plain run. The
canary pair takes one of 499 places when it is found in time, and none when it is not. This is the
failure of `test_two_run_demo_boards` (`canary` = `absent`), and it also explains the "one
violation fewer in every canary run" of `H-K-CHECK-CANARY`.

### The limit, on an authored bench

`tests/data/kicad/board/two_layer.kicad_pcb` (one `clearance` violation of its own) with N more
pairs of `F.Cu` tracks, each pair on two nets of its own with a 0.05 mm gap; a `{}` project and a
`(version 1)` rules file. Each row: a plain run and a canary run, repeated.

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

So `kicad-cli` reports at most 499 `clearance` violations on 10.0.6, and stops a little above 499
on 9.0.9 (502 to 508 of 701). Below 499 the canary always fired. No public statement of this limit
was found in the manuals (S-0010, S-0022, S-0038); it is measured (S-0020).

### Other builds

The pinned Linux images of 10.0.6 and 9.0.9 are present locally. Their runs are tasks 1.2 and 1.3;
the tables go to `docs/evidence/kicad-check.md`, and a board or type that they add joins the named
sets before task 3.1 (Decision 3).

### `--all-track-errors` (supporting data, not used)

`pcb drc` has the flag `--all-track-errors` ("Report all errors for each track", S-0022). A likely
cause of the spread is that, without it, KiCad stops at one violation per track, and which one it
finds first depends on the run (`INFERRED`; no public statement found). Six plain runs per board
with the flag, on 10.0.6 (macOS):

| board | totals with the flag (six runs) | distinct sorted reports |
|---|---|---|
| `kicad-demo-10-0-6-pcb-01` | 1597 / 0 | 6 |
| `kicad-demo-10-0-6-pcb-07` | 536 / 0 | 1 |
| `kicad-demo-10-0-6-pcb-09` | 132 / 148 | 4 |
| `kicad-demo-10-0-6-pcb-11` | 1003 / 0 | 1 |
| `kicad-demo-10-0-6-pcb-13` | 1300 / 0 | 6 |
| `kicad-demo-10-0-6-pcb-16` | 896 / 1 | 3 |

The totals repeat on all six boards and two boards repeat whole; the others still name other
items. The flag would not make the report repeatable, and it changes the counts, so it is left to
the maintainer (Open questions).

## Goals / Non-Goals

Goals:

- Say, with numbers, what two DRC runs share and what they do not.
- Make the gate test assert all of the stable part, and name the unstable part.
- Make the spec and the contract promise only what holds.

- Stop telling users that loaded rules were not loaded.

Non-goals: those of the proposal.

## Decisions

1. **Compare in canonical form.** Order alone differs on 4 boards and on every unstable board, so
   every comparison uses `DrcReport.entries()`: sorted, uuids left out, the run's temporary folder
   masked as `KicadOracle.rt2` does. This is option (a) of the task, and it is already what
   `entries()` exists for. It is not enough alone: 6 boards differ in content.
2. **Compare two outcomes of `KicadOracle.drc`, not the plain and the canary run of one call.**
   - The user-facing promise is about two `check` runs, and `DrcOutcome` holds only the plain
     report. The canary run's report is not exposed, and exposing it would change `src/` and the
     backend protocol for a test.
   - Cost: four DRC runs per board instead of two. Measured locally, the 21 boards take about 90 s
     for two runs each, so about 90 s more in `kicad-10` (the job takes about 20 minutes).
   - Rejected: comparing through `fenolite check --json`. It adds the other stages' time and proves
     nothing more: the stage sorts its issues, and `test_check_oracle.py -k deterministic` already
     covers the envelope on a board that repeats.
3. **Two named sets, both measured.**
   - `UNREPEATABLE_TYPES = {"clearance", "hole_clearance", "unconnected_items"}`: on every board,
     entries of other types must be equal.
   - The canary state must be `fired`. `inconclusive` / `clearance-limit` is accepted only when the
     outcome's report is saturated (`clearance_saturated`), which names `-01` and `-13` by rule and
     not by list.
   - `UNREPEATABLE_BOARDS`: the six ids. On every other board the whole report must be equal.
   - The same six boards are the ones `docs/evidence/kicad-check.md` listed on 2026-10-02 in the
     Linux images, and five of them are the boards with unstable keys in `docs/evidence/kicad-rt2.md`
     (`-16` showed none in two runs there). Three independent measurements agree on the set.
   - A set grows only with a recorded measurement of at least 15 runs per board. This is the rule
     that keeps the list from becoming a place to hide failures.
   - Rejected: a bound on the counts of the named types (for example ±20 on `-07`). The spread is
     not bounded by anything known, so a bound would be a guess that fails later.
   - Rejected: dropping the six boards from the test. Their stable part (up to 18 types, the
     canary verdict) is worth checking, and it is where a regression of the two-run path would show.
   - Rejected: retrying, `pytest.mark.flaky`, `xfail(strict=False)` or a skip (task rule).
4. **The comparison is a function with unit tests.** `tests/_drcrepeat.py` holds the two sets and
   `repeat_problems`. `tests/unit/test_drc_repeat.py` feeds it authored `DrcOutcome`s: equal,
   order-only, a named type on a named board (no problem), a named type on a stable board
   (problem), another type on a named board (problem), a canary state that differs (problem),
   `clearance-limit` on a report below the limit (problem) and on a saturated one (no problem), a
   missing report (problem). So the weaker form is shown to fail, in `make check-fast`, without
   `kicad-cli`.
5. **A saturated report gives no verdict; the run is not repeated.**
   - Rule: after the canary run, when no `clearance` violation names exactly the two canary uuids,
     the state is `inconclusive` / `clearance-limit` if that report holds at least
     `CLEARANCE_REPORT_LIMIT = 499` `clearance` violations, and `absent` otherwise. The count
     includes anything of type `clearance`, on both majors (`>=`, because 9.0.9 overshoots).
   - Why it is honest: at the limit a missing pair proves nothing (measured), and below it the pair
     was never missing (315 demo runs, the bench rows up to 497 pairs). `absent` therefore keeps
     its meaning, "the rules were not loaded", exactly where it can be proved.
   - Effect for the user: `kicad.drc.rules-unchecked` (warning) with the reason in the message, and
     the stage evidence `UNVERIFIED`, as for every other `inconclusive` reason. No stage code
     changes: `checks/drc.py` already maps `inconclusive`.
   - Cost: a rules file that really is dropped on a saturated board is now reported as unknown
     instead of not loaded. On such a board the old answer was not trustworthy either.
   - Rejected: repeating the canary run until it fires. It hides the tool's behaviour behind a
     probability (the bench on 9.0.9 fired in 1 of 4 runs), costs a DRC run each time, and never
     turns a real `absent` into a proof.
   - Rejected: a canary of another violation type. Any type can be saturated by a board, and the
     canary's present form is the one proved on both majors (`H-K-DRU-ORDER`, `check-canary-*`).
   - Rejected: a separate small canary board (c0013 Decision 5 rejected it: it loses rules errors
     that depend on the board).
   - Rejected: accepting `absent` in the test on the two named boards. The product would still tell
     users that loaded rules were not loaded.
   - `H-K-CHECK-CANARY-2` said the canary fires on each of the 21 demo boards. That criterion is
     refuted (4 of 110 canary runs on two boards), so the row is closed and `H-K-CHECK-CANARY-3`
     succeeds it; `oracle.EVIDENCE` and the texts cite the successor.
6. **`fenolite check` and the determinism promise.**
   - What relies on repeatability: "Check output is deterministic" (`verification-loop`), and the
     canary verdict (Decision 5). The evidence level of `drc.kicad` holds per run: it says the
     report was read from `kicad-cli` and, when the canary fired, that the rules were loaded. `roundtrip.rt2` already handles unstable keys,
     `zone.fill` has `oracle-unstable`, and the exports are covered by `H-K-EXPORT-REPEAT`.
   - The requirement is narrowed (MODIFIED delta): Fenolite adds no difference; where the tool does
     not repeat, the three `kicad.drc.*` codes, the summary counts made from them, the stage status
     and the exit code may differ; on a saturated board the canary state may differ too, between
     `fired` and `clearance-limit`. An exit code can change only when one of those issues is the
     only error of a run. That was not observed: every unstable board here has hundreds of stable
     errors. It follows from the rule and is stated so.
   - `docs/cli-contract.md` gets one paragraph under `check`; `--seed` and `--timestamp`
     ("Determinism") do not apply to `check` and stay as they are.
   - No new issue code. Telling the user at run time would need a second plain run or a list of
     types in `src/`; left to the maintainer.

## Files and public API

| File | Change |
|---|---|
| `src/fenolite/backends/kicad/canary.py` | `CLEARANCE_REPORT_LIMIT = 499`, `clearance_saturated(report) -> bool`, `"clearance-limit"` in `CanaryReason` |
| `src/fenolite/backends/kicad/oracle.py` | `drc` gives `inconclusive` / `clearance-limit` for a saturated canary report without the pair; `EVIDENCE` cites `H-K-CHECK-CANARY-3` |
| `tests/unit/backends/kicad/test_canary.py`, `test_oracle.py` | `clearance_saturated`; the saturated and the 498 fake reports |
| `tests/kicad/check/_limitbench.py`, `test_drc_limit.py` | new: the authored bench and its two tests, on both majors |
| `tests/_drcrepeat.py` | new: `UNREPEATABLE_TYPES`, `UNREPEATABLE_BOARDS`, `canonical(report) -> tuple`, `repeat_problems(board_id, first, second) -> list[str]` |
| `tests/unit/test_drc_repeat.py` | new: the helper's cases, the record guard, the contract guard |
| `tests/kicad/check/test_canary.py` | `test_two_run_demo_boards` runs the oracle twice and asserts `repeat_problems(...) == []` |
| `docs/hypotheses.md` | rows `H-K-DRC-LIMIT`, `H-K-DRC-REPEAT`, `H-K-CHECK-CANARY-3`; `H-K-CHECK-CANARY-2` refuted; a paragraph for this change |
| `docs/evidence/kicad-check.md` | sections "DRC repeatability on the demo boards" and "Clearance report limit" (change c0051) |
| `docs/formats/kicad/drc.md` | the reason, the limit and two fact rows under "Check canary" |
| `docs/cli-contract.md` | the reason under "Rules canary"; paragraph "Repeatability" under `check` |
| `CHANGELOG.md` | one line under "Fixed" |

Public API: one constant, one function and one more value of `DrcOutcome.canary_reason`. No stage,
exit code or issue code is added.

## Sources registered by this change

None. The change cites S-0020 (`kicad-cli` 10.0.6 as an oracle), S-0022 (10.0 CLI manual, the
`pcb drc` flags) and S-0037 (9.0 CLI manual).

## Hypotheses registered by this change

| id | backend | statement | level wanted | test | criterion |
|---|---|---|---|---|---|
| `H-K-DRC-REPEAT` | kicad | Two `pcb drc --format json --severity-all` runs on one unchanged project differ at most in the report order and in entries of the types `clearance`, `hole_clearance` and `unconnected_items`; every entry of another type, the return code, the written files and the canary verdict repeat; on the demo boards outside `kicad-demo-10-0-6-pcb-01`, `-07`, `-09`, `-11`, `-13` and `-16` the whole sorted report repeats (S-0020, S-0022) | `KICAD-VERIFIED (10.0.x)` | `tests/kicad/check/test_canary.py::test_two_run_demo_boards` | on 10.0.6, for each of the 21 readable non-heavy demo boards, two `KicadOracle.drc` outcomes give no problem in `repeat_problems`; if refuted, the board or type joins the named set with its 15-run measurement, in a `-2` successor |

| `H-K-DRC-LIMIT` | kicad | `pcb drc` stops reporting `clearance` violations near 499 per run: 10.0.6 reports exactly 499 on a board with more, 9.0.9 between 499 and 508; the check canary's pair competes for a place and can be missing from a run that loaded the rules; in a report with fewer than 499 `clearance` violations it is always present when the rules were loaded (measured, S-0020; no statement found in S-0010, S-0022, S-0038) | `KICAD-VERIFIED (9.0.x, 10.0.x)` | `tests/kicad/check/test_drc_limit.py` | on 9.0.9 and 10.0.6: 300 pairs give 300 more `clearance` violations than none and the canary fires; 700 pairs give at least 499 and fewer than 700 (exactly 499 on 10.0.6); five oracle runs on 700 pairs give `fired` or `clearance-limit`, never `absent`; if refuted, `CLEARANCE_REPORT_LIMIT` takes the measured value per major |
| `H-K-CHECK-CANARY-3` | kicad | `H-K-CHECK-CANARY-2` with the limit: the canary fires exactly once when the rules were loaded and the canary run's report holds fewer than 499 `clearance` violations; at or above that count its pair can be missing, and the state is then `inconclusive` (`clearance-limit`), never `absent` (S-0010, S-0038, S-0020) | `KICAD-VERIFIED (9.0.x, 10.0.x)` | `test_canary.py::test_canary_fires`, `::test_canary_broken_rules`, `::test_canary_ignored`, `::test_two_run_demo_boards`; `test_drc_limit.py` | the probes of `H-K-CHECK-CANARY-2`; on 10.0.6 each of the 21 demo boards gives `fired`, or `clearance-limit` with a saturated report; the bench criterion of `H-K-DRC-LIMIT` on both majors |

No collision: `docs/hypotheses.md` and the active changes on `main` hold none of the three ids.

## Evidence level per behaviour (before merge)

| Behaviour | Level |
|---|---|
| Two runs differ only in order and in the three named types | `KICAD-VERIFIED (10.0.x)`: 30 runs per board on macOS, and the 10.0.6 image run of task 1.2 |
| The same on 9.0.9 | open until task 1.3; recorded as measured, the label stays `(10.0.x)` unless it agrees |
| The clearance limit and the saturated verdict | `KICAD-VERIFIED (9.0.x, 10.0.x)`: the bench on 10.0.6 (local) and 9.0.9 (pinned image), task 2.2 |
| The canary below the limit | unchanged claim, now `H-K-CHECK-CANARY-3`; supported by 315 of 315 demo runs and the bench |
| Product labels (`oracle.EVIDENCE`, `drc.EVIDENCE`) | levels unchanged; `oracle.EVIDENCE` cites `H-K-CHECK-CANARY-3` |

## Risks

- **A stable board stops repeating.** Fifteen pairs cannot exclude a rare event. If it happens, the
  test fails with the board and type named, and the rule of Decision 3 says what to do: measure 15
  runs, then extend the set and the record. That is slower than a retry and it is the point.
- **The limit differs on a build not measured.** The rule uses `>=`, so a higher soft stop (as on
  9.0.9) is covered. A build that stops below 499 would give `absent` again on a saturated board;
  the bench's verdict test would fail there and name it.
- **Time.** About 100 s more in `kicad-10`, a few seconds in `kicad-9`.
- **Sibling changes.** If one of c0050 or c0052 to c0056 also modifies "Check output is
  deterministic", the later one in the merge order must copy the earlier text.

## Open questions (for the maintainer)

1. Should `drc.kicad` pass `--all-track-errors`? It steadies the totals on the six boards and makes
   two of them repeat whole, and it raises the counts (475 to 536 on `-07`, 867 to 1003 on `-11`).
2. Should `check` tell the user at run time that the three codes may not repeat on a large board
   (an info issue)? Today only the contract says it.

## Found outside this change

- `tests/kicad/altium/test_pcbdoc_oracle.py::test_import_succeeds_without_errors` failed in the
  `kicad-10` job of run 37186647371 on `main` (a2ec22b): `kicad-cli` warned "Invalid lock file
  '/tmp/org.kicad.kicad/instances/kicad-cli-10.0'", which the test's list of allowed warnings does
  not hold. It looks like parallel `kicad-cli` processes sharing one lock folder. Not touched here.

## Size (design-days)

1.5: measurement 0.5, oracle rule and bench 0.4, helper and tests 0.3, documents and deltas 0.3.
