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
| 1 | waiting | four copper layers with inner zones, classes, minimums, the high-voltage clearance and creepage rules, the `USB2` interface, the built schematic, BOM, placement table and manifest | the first scheduled run of the job (task 5.2 of c0119); the example and the runner are on the branch since 2026-10-08 |
| 2 | waiting | six copper layers and a declared stack-up | c0100, c0101 archived |
| 3 | waiting | outline shape, slot and holes, rule areas, pair and impedance rules, thermal via arrays, `near` rules, a net tie | c0102, c0103, c0104, c0105, c0111, c0112, c0113, c0114 archived; part heights under a lid wait for the change split out of c0113 (c0140) and hold no stage |
| 4 | waiting | routed and analysed | c0106, c0107, c0108, c0109, c0110, c0115 archived |
| 5 | waiting | the document kinds, drawings and test features | c0116, c0117, c0118 archived |

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

- **The two heavy demo boards** (`kicad-demo-10-0-6-pcb-06`, 84.8 MB, and `kicad-demo-10-0-6-pcb-18`,
  69.6 MB): not fetched on the machine of the local run (task 1.3 of c0119 needs the maintainer's consent
  for 155 MB), so `heavy-read` and `heavy-rt1` have no budget yet; the first scheduled runs give them
  (`H-K-YARD-HEAVY`).
- **Target 9**: nowhere in v0.4. The 9.0 library tag lacks a library the board uses, and KiCad 9.0 cannot
  refill (`H-K-01`).
- **The releases up to 0.3.0** were made without a run of the yardstick; the release record of every
  release after the job's first scheduled run names the newest run, its stage and its verdict.
- **An Altium build** of the board, **agent runs** on it (c0081), **a BGA**, and reading fabrication files
  back: no step of the runner.
- **The sum of resident memory over a step's processes**: one sample on the stand-in (366 MiB in `check`
  at 369 parts); the runner records the largest process.
