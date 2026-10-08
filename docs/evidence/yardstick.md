# The yardstick board

The series of `examples/yardstick`: one authored board of about 370 parts that `tools/yardstick.py run`
takes through the loop of its stage every night (job `yardstick` of `nightly.yml`; capability
release-gate, "Yardstick record"; change c0119). Counts, seconds and MiB only; nothing built from the
official KiCad libraries is kept here.

## How to read

- **Provenance of the circuit.** Recorded on 2026-10-07, by the maintainer's decision 1 of that day: the
  maintainer, Luiz Carlos Gili, declares that the yardstick circuit (an eight-channel 48 V buck
  controller with an isolated high-voltage sense section) was invented for Fenolite and mirrors no board,
  product or reference design of any organisation. Nothing in a repository can show this, so the statement
  is kept here. What keeps it checkable: every value at the top of the script is a round one with the
  comment `chosen for the example` or a public source id; the parts are ids of the official KiCad
  libraries, fetched and never committed; the file is CC0 and names no company, product or private path
  beyond those library ids; `tests/residue` scans the example.
- **A stage** is one step of the board's growth (`STAGE` in the script). It is `reached` when the changes
  it needs are archived, its additions are in the example and one scheduled run of it has the verdict
  `passed`; `waiting` names what it waits for; `not reached (cut: c<id>)` names a change that was cut,
  whose part the example leaves out.
- **A run** is one scheduled or dispatched run of the job. Its record (`fenolite.yardstick-record.v0`)
  is an artefact of the run, kept 90 days; a row is added to `Runs` when a stage is reached and before
  each release, printed by `uv run python tools/yardstick.py row <record> --url <run>`.
- **Open connections** are KiCad's count of unconnected items. Before stage 4 nothing is routed, and
  KiCad stops its report at 499 entries: such a count reads `≥ 499`.
- **Peak MiB** is the peak resident memory of a step's largest process (`ru_maxrss`), not the sum over
  the processes of the step.
- **Seconds and MiB are measures of one runner.** A run that crosses a budget fails the job; no evidence
  label rises on a budget that held, and none falls on one that failed. The labels of `H-K-YARD-*` and
  `H-G-DSN-YARD` (`docs/hypotheses.md`) move on KiCad's verdicts in scheduled runs only.

## Stages

| stage | state | the board gains | waits for |
|---|---|---|---|
| 1 | waiting | four copper layers with inner zones, classes, minimums, the high-voltage clearance and creepage rules, the `USB2` interface, the built schematic, BOM, placement table and manifest | the first scheduled run of the job with the verdict `passed` (task 5.2 of c0119) |
| 2 | waiting | six copper layers (`GND` on In1.Cu, `+3V3` and `VIN48` on In4.Cu, `HV_RTN` on both under the strip) and the stack-up preset `six-layer-1.6mm` (S-0722), impedance-controlled, ENIG | the same run (complete for 0.4: c0100, c0101) |
| 3 | waiting | slots under the two isolators and the creepage minimum raised to 7.5 mm, four plated `design.hole` mounting holes with keep-outs of tracks and vias, the strip as the rule area `HV` with a clearance of 0.6 mm between its `HV` nets, the class `USB` with pair values, the pair's gap, clearance, uncoupled, skew and length rules, the impedance target `USB90`, filled and capped thermal via arrays in the controller's exposed pad and the eight high-side tabs, `near` rules for the decoupling, the crystal and the gates, the net tie `NT1` between `GND` and `SGND`; the step `impedance` | the same run (complete for 0.4: c0102, c0103, c0104, c0105, c0111, c0112, c0113, c0114); the rounded outline of c0102 is left out (below); part heights (c0140) take no part: the example has no lid |
| 4 | waiting | `In1.Cu` and `In4.Cu` typed as planes; the steps `route-pairs` (KiCadRoutingTools, the pair and the controller's escape), `route` (Freerouting, plane fan-out, `--timeout 3600` and two tiers), `fill-routed`, `check-routed` against the ratchets, `net` and `analyze` (clearance, creepage with the 1 mm groove, insulation) | the same run (complete for 0.4: c0106, c0107, c0108, c0109, c0110, c0115); c0110's `pairs` and `escape` features stay undeclared in 0.4 (its gate is deferred), so `route-pairs` routes nothing and the pair stays open, counted by the ratchets |
| 5 | waiting | three global fiducials, two tooling holes and five test points; the steps `export-package` (IPC-2581, ODB++, STEP, board PDF and DXF, schematic PDF, fabrication and assembly drawings, with the manifest) and `testpoints` | the same run (complete for 0.4: c0116, c0117, c0118) |

The example went from stage 1 to stage 5 in one step on 2026-10-08: the coordinator decided that day that
the changes each stage needs, implemented on the release branch of 0.4 and archived at the release, count
as archived for the example (`complete for 0.4` above, which `tools/yardstick.py` reads as it reads a cut).
Because the stages are cumulative, the first scheduled run with the verdict `passed` reaches the five
stages together; a failed one names the step and the rule, and so the stage, that stopped it.

**Left out of stage 3: the rounded outline.** On this base `Design.stackup()`, `Design.rule_area()` and
the board drawings refuse a board declared with `board(outline=…)` ("call board() first"): they test the
size that only `board(width, height)` sets. Found by the example on 2026-10-08 with
`design.board(outline=shape.rect(…, radius=…), copper=6)` followed by `design.stackup(…)`; the repair
belongs to c0101, c0102 and c0103, and the example keeps the rectangle until it lands.

## Runs

| date | commit | stage | run | total seconds | largest peak MiB | open connections | DRC errors | verdict | note |
|---|---|---|---|---|---|---|---|---|---|

No scheduled run yet.

## Budgets

The current values of `tools/yardstick_budgets.toml`:

- **Stage 1: provisional**, from one local run of the runner on the example itself: 2026-10-07T16:22Z,
  commit `7392159d` (the integration branch of v0.4 before this change), macOS on arm64 with 10 cores
  and 16 GiB, `kicad-cli` 10.0.6, Fenolite 0.2.1 run from source, the libraries from the verified cache
  of tag 10.0.6. The machine was shared with other jobs (load 24 to 28), so the seconds are upper bounds.
  The budget is the measured seconds times 4, rounded up to 10 s, and the measured MiB times 2, rounded
  up to 50 MiB. The run passed: every `check` stage `ok` but `drc.kicad`, whose only error type is
  `unconnected_items` (499, KiCad's cap), 2 `isolated_copper`, 184 `silk_over_copper` and 114
  `silk_overlap` warnings; `erc.kicad` reports 2 `ground_pin_not_ground` warnings; the rebuild left the
  board's bytes unchanged. 377 parts, 176 nets, 931 pads on nets, a board of 1 375 504 bytes.

  | step | seconds | peak MiB | budget s | budget MiB |
  |---|---|---|---|---|
  | `capabilities` | 2.1 | 55 | 10 | 150 |
  | `build-dry` | 21.3 | 122 | 90 | 250 |
  | `build` | 21.7 | 116 | 90 | 250 |
  | `fill` | 23.1 | 245 | 100 | 500 |
  | `check` | 47.1 | 272 | 190 | 550 |
  | `export` | 7.2 | 209 | 30 | 450 |
  | `render` | 4.8 | 204 | 20 | 450 |
  | `bom` | 3.6 | 92 | 20 | 200 |
  | `pnp` | 5.0 | 87 | 20 | 200 |
  | `manifest` | 4.8 | 77 | 20 | 200 |
  | `rebuild-dry` | 26.0 | 130 | 110 | 300 |
  | `rebuild` | 27.3 | 130 | 110 | 300 |
  | `inspect` | 4.2 | 81 | 20 | 200 |
  | `build-install` | 210.2 | 219 | 850 | 450 |

  `build-install` read the libraries of the local KiCad 10.0.6 install and planned the same board bytes
  as `build-dry`, in 9.9 times its seconds (`H-K-YARD-LIBREAD` stays `INFERRED`: its criterion is three
  scheduled runs). A second local run on the same machine a quarter of an hour later, against these
  budgets, passed with no budget crossed: `build` 8.7 s, `check` 19.3 s and 333 MiB, `build-install`
  135.2 s (16 times the 8.3 s of `build-dry`). The spread between the two runs is the load of the
  machine; neither is a scheduled run, and neither is a row of `Runs`.
- **The heavy demo boards: provisional**, by the same rule, from one local run on 2026-10-08 (task 1.3 of
  c0119): Linux x86_64 with 4 cores and 16 GiB, Fenolite run from source at `a105cc0`, each command one
  child process measured with `os.wait4` as the runner measures a step; the machine also routed the
  example during the last two. Every read is `supported` and both round trips pass RT0 and RT1.

  | step | seconds | peak MiB | budget s | budget MiB |
  |---|---|---|---|---|
  | `heavy-read:kicad-demo-10-0-6-pcb-06` | 78.5 | 1 702 | 320 | 3 450 |
  | `heavy-read:kicad-demo-10-0-6-pcb-18` | 75.9 | 1 355 | 310 | 2 750 |
  | `heavy-rt1:kicad-demo-10-0-6-pcb-06` | 329.9 | 4 334 | 1 320 | 8 700 |
  | `heavy-rt1:kicad-demo-10-0-6-pcb-18` | 311.1 | 3 943 | 1 250 | 7 900 |

- **Stages 2 to 5: provisional, copied from stage 1** (task 6.1 of c0119 allows it for stage 2; for the
  later stages the machine of 2026-10-08 had no `kicad-cli`, so no local run of the full loop was
  possible). The stage-5 board is larger than the stage-1 board of the local run (388 parts on six layers
  with 225 thermal vias, against 377 on four), which the margin of four on seconds is left to absorb; the
  first three scheduled runs of stage 5 replace every value. `route` has 3 900 s and `route-pairs` 900 s:
  their `--timeout` plus 300 s for the merge and the write (design, Decision 10); neither has a MiB budget
  yet. The steps added by stages 3 to 5 (`impedance`, `fill-routed`, `check-routed`, `net`, `analyze`,
  `export-package`, `testpoints`) have no budget: they are recorded and fail nothing until the runs give one.
- **The ratchets of stages 4 and 5 are bounds, not counts**: 498 open connections (a route that leaves
  KiCad's count at its cap of 499 fails) and 499 other DRC errors. No KiCad count of the routed board
  exists yet; `rebase` prints the largest counts of the first three scheduled runs, which replace them.
- **The local run of 2026-10-08 at stage 5**, on the same machine, of every step that needs no
  `kicad-cli` (`--only build-dry,build,rebuild-dry,rebuild,inspect,build-install,impedance,net,analyze,
  testpoints --skip-heavy`): `build-dry` 14.4 s and 141 MiB, `build` 14.3 s, `rebuild-dry` 16.8 s,
  `rebuild` 15.3 s and 154 MiB, `inspect` 2.2 s, `impedance` 1.0 s, `net` 2.6 s, `analyze` 15.4 s,
  `testpoints` 2.3 s; every exit 0 but `build-install` (exit 3: no KiCad install on the machine). The
  dry rebuild planned no change and the rebuild left the board's bytes unchanged; `testpoints`'s file is in
  the manifest. `net` counts 757 open connections on the unrouted board, which KiCad caps at 499. It is no
  scheduled run and no row of `Runs`.
- **The `route` step, measured once on the same machine** (2026-10-08, Freerouting 2.4.1 on Temurin 25,
  the unfilled stage-5 board, `--timeout 3600 --order 'OSC_*' --order 'CH*'`): exit 0 after 3 606 s,
  peak 1 755 MiB as the runner counts it (`ru_maxrss` of the step; the JVM's resident set was about
  1.7 GB). Plane fan-out of `GND`, `+3V3`, `VIN48` and `HV_RTN`: 309 pads, 271 vias and tracks, 29
  `kicad.fanout.failed`. Three runs: tier 0 (2 nets) done in 659 s, tier 1 (128 nets) done in 1 459 s,
  tier 2 (37 nets) cut by the budget (`route.budget-exhausted`); 167 nets selected and 130 closed, the
  open connections of the selected nets from 425 to 109; 1 419 tracks and 210 vias. `net` then counts
  441 open connections on 47 nets, the zone nets included, since nothing was refilled. Three pairs were
  skipped (`route.pair-skipped`): `USB_DP`/`USB_DN`, and `HV_OUT_P`/`HV_OUT_N` and
  `HV_SENSE_P`/`HV_SENSE_N`, which KiCad's name rule pairs too; the last two are named `…_HI`/`…_LO`
  since, so that the board holds its one pair. No `kicad-cli` judged this board: it sizes the budget
  of the step and is no row of `Runs`.
- **Accepted findings: none.** No entry of `[stage1.accepted]` was needed.
- **The creepage minimum** of stage 1 is 7 mm: with 7.5 mm, `kicad-cli` 10.0.6 reports 4 `creepage`
  violations on the same board, and none with 7 mm (2026-10-08, task 2.2 of c0119).
- **Budgets from runs** replace these after the first three scheduled runs of a stage (median seconds
  times 1.5, largest MiB times 1.25); a later commit that raises a budget or accepts a finding adds a line
  here with the step or the type and the reason.

**What sized the change, and is no source of a committed budget.** Measured on 2026-10-05 on a generated
stand-in of 369 parts on four layers, at `27ef3ad7` (the review branch), before `check` ran `erc.kicad`
and `parity` and before `build` wrote a schematic, on a shared machine:

| step | seconds | peak MiB |
|---|---|---|
| `capabilities` | 1.2 | 52 |
| `build --dry-run` | 7.8 | 114 |
| `build --confirm` | 6.0 | 115 |
| `fill --confirm` | 7.5 | 223 |
| `check --format concise` | 8.5 | 257 |
| `export --all --manifest` | 3.7 | 211 |
| `render --svg` | 2.3 | 203 |
| rebuild `--dry-run` | 7.9 | 130 |
| rebuild `--confirm` | 9.9 | 126 |
| `inspect <board>` | 2.2 | 81 |
| `roundtrip --level rt1` | 5.0 | 135 |

On the same stand-in: a build from the whole-file libraries of a KiCad install took 101 s to 161 s against
6 s from the verified cache; Freerouting 2.4.1 with the inner zones given as planes left 32 of 344
connections open after its 20 passes (1 003 s, heap 1.9 GB), flat from pass 13 on.

## Not measured

- **The two heavy demo boards on the CI runner** (`kicad-demo-10-0-6-pcb-06`, 84.8 MB, and
  `kicad-demo-10-0-6-pcb-18`, 69.6 MB): measured once on a local machine (`Budgets`); the first
  scheduled runs settle `H-K-YARD-HEAVY`.
- **The full loop of stages 2 to 5 with `kicad-cli`**: written on 2026-10-08 and not run on any machine
  yet; the first dispatched run of the job is the first.
- **Target 9**: nowhere in v0.4. The 9.0 library tag lacks a library the board uses, and KiCad 9.0 cannot
  refill (`H-K-01`).
- **The releases up to 0.3.0** were made without a run of the yardstick; the release record of every
  release after the job's first scheduled run names the newest run, its stage and its verdict.
- **An Altium build** of the board, **agent runs** on it (c0081), **a BGA**, and reading fabrication files
  back: no step of the runner.
- **The sum of resident memory over a step's processes**: one sample on the stand-in (366 MiB in `check`
  at 369 parts); the runner records the largest process.
