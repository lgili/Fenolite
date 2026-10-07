## Context

- **Scope.** Milestone v0.4, c0119, from the complex-board review of 2026-10-05: "an authored example of 300 parts or more, on 4 and then 6 layers, with inner planes, one pair, repeated power channels and a high-voltage gap, run on a schedule; time and memory budgets read from it". The review's findings that it answers: no board, example or milestone above 40 parts on two layers; no end-to-end test of a four-layer build; the two heavy demo boards never run; performance measured but never a gate; no line that measures routing at size, since c0016 and c0023.

- **What exists** (`origin/dev` at `9aba2dff`, read on 2026-10-07; the measurements further down are older and say so):
  - `examples/board_40parts/design.py`: 40 parts of the authored mini library on two layers, its modules written as a Python function called twice. `tests/_acceptloop.py` (`STEPS`, `run_cli`, the determinism flags), `tests/routing/test_acceptance_loop.py`, `tests/kicad/acceptance/test_finished.py`, and the living `release-gate` requirements of v0.1.
  - The DSL: `Design.board(width, height, copper=2|4, planes=…)` refuses other counts (`dsl/design.py:354`); `zone(net, layers=…, outline=…)` takes inner layers; `planes=` gives `build.plane-not-lowered` on KiCad (`lens/build.py:150`); `Design.via(kind=…)` and `arc_to` (c0068); `design.rules.rule()` with `fenolite.dsl.select`, `creepage` written for KiCad 10 only (c0071); `USB2` (c0073), reported as `build.interface-not-lowered`; `Part(pad_map=…)` (c0056).
  - `check` runs the stages `model.validate`, `erc.kicad`, `copper.clearance`, `zone.fill`, `drc.kicad`, `parity`, `netlist.assignment_compare` and `roundtrip` (`checks/stages.py:33`; `erc.lite` is gone since c0062), and `check --format concise` (c0066) keeps every stage summary and an `issues_summary`. `build` writes a schematic with one sheet per module (c0061, c0070). `bom`, `pnp` (c0064), `manifest` (c0065) and `net` (c0066) are commands. `fenolite inspect` on a project folder exited 1 with `FEN-1001` (`IsADirectoryError`) at `27ef3ad7`; on `dev` `cmd_inspect.py:130` handles a folder of symbol files, and whether a project folder still fails is re-tested by task 0.1.
  - The second backend: `build --target altium` writes Altium documents on `dev` (c0084 to c0088). This change builds for KiCad only and adds no rule kind, selector or model field, so the Altium rule table and lowering are not concerned.
  - The offline catalog held 14 footprints at `27ef3ad7`. c0075 and c0076 are archived on `dev`, and `catalog/__init__.py` now holds QFN, TO-252, micro-USB and mounting-hole footprints among others, each with its source ids; the exact count, and which parts of Decision 1 it still lacks, are counted by task 0.1. Its footprints carry no `Reference` text (only its symbols have the property), which c0077 repairs.
  - `.github/workflows/nightly.yml` holds one job, `macos-app` (c0068), on `schedule` and `workflow_dispatch`, in one concurrency group. The `routing` job of `ci.yml` installs Freerouting 2.4.1 and KiCadRoutingTools v0.22.1, both checked by SHA-256, inside the pinned images. The routers are registered as `direct`, `freerouting` and `kicadroutingtools`.
  - Markers `needs_kicad`, `needs_libs`, `needs_freerouting`, `slow`. The corpus manifest tags two demo boards `heavy`: `kicad-demo-10-0-6-pcb-06` (84 806 775 bytes) and `kicad-demo-10-0-6-pcb-18` (69 638 531 bytes). `kicad-10` fetches with `--exclude-uses heavy`, tests take them only with `FENOLITE_HEAVY=1` (`tests/_corpus.py:51`), and no evidence page records a run of them.
  - `tools/kicad_libs_fetch.py` fills a verified cache per tag; the 10.0.6 tag takes 450 MB (symbols 271 MB, footprints 179 MB). Without a cache, `LibraryResolver` falls back to the per-OS install (`MACOS_INSTALL`, `LINUX_INSTALL`, `backends/kicad/libs.py:67`).
  - `tests/corpus/test_copper_perf.py` and `tests/unit/backends/kicad/test_throughput.py` record times, "never a gate".

- **Measured on 2026-10-05, at `27ef3ad7`, not repeated on `dev`.** Since then `check` lost `erc.lite` and gained `erc.kicad` and `parity`, and `build` writes a schematic, so the times, peaks and reply sizes of measurements 2 and 3 are too low for `dev` by an unknown amount, and measurement 3's list of stages is the old one. They stay here as the record of what sized the change; no committed budget is read from them (Decision 10), and tasks 2.2 and 4.2 take the numbers again on the example itself. A stand-in was generated for this change: a script of `fenolite.dsl` calls only, an invented circuit of the composition of Decision 1, parts of the official KiCad 10.0.6 libraries, built and judged by this branch's code run from source and `kicad-cli` 10.0.6 on macOS (arm64, 10 cores). The machine was shared with other jobs (load 5 to 36), so times are upper bounds. Every writing step ran with `--seed 250025 --timestamp 2026-10-04T00:00:00Z --no-backup`. Peak memory is `ru_maxrss` of `os.wait4` on the step's process: the largest single process of the step, Python, `kicad-cli` or Java.
  1. *The stand-in.* Eight channels: 369 parts, 163 nets, 895 pads on nets, 12 modules, 203 mm × 156 mm, four copper layers, `GND` on In1.Cu and `+3V3` on In2.Cu under the low-voltage area, `HV_RTN` on both inner layers under a high-voltage strip 8 mm away, classes `PWR`, `HV` and `SIG`, a clearance rule of 7 mm between `HV` and the rest. Sixteen channels: 665 parts, 283 nets, 1 586 pads, 253 mm × 194 mm.
  2. *The loop on the unrouted board* (seconds and peak MiB; bytes of the `--json` reply where they matter):

     | step | 369 parts | 665 parts |
     |---|---|---|
     | `capabilities` | 1.2 s, 52 MiB | — |
     | `build --dry-run` | 7.8 s, 114 MiB | 8.7 s, 175 MiB |
     | `build --confirm` | 6.0 s, 115 MiB | 14.0 s, 170 MiB |
     | `fill --confirm` | 7.5 s, 223 MiB | 24.2 s, 288 MiB |
     | `check` | 9.2 s, 262 MiB, 124 518 bytes | 17.1 s, 301 MiB, 142 620 bytes |
     | `check --format concise` | 8.5 s, 257 MiB, 5 807 bytes | 14.2 s, 313 MiB, 5 820 bytes |
     | `export --all --manifest` | 3.7 s, 211 MiB | 3.0 s, 228 MiB |
     | `render --svg` | 2.3 s, 203 MiB | 1.6 s, 221 MiB |
     | rebuild `--dry-run` | 7.9 s, 130 MiB | 10.3 s, 201 MiB |
     | rebuild `--confirm` | 9.9 s, 126 MiB | 9.9 s, 202 MiB |
     | `inspect <board>` | 2.2 s, 81 MiB | 2.2 s, 109 MiB |
     | `roundtrip --level rt1` | 5.0 s, 135 MiB | 7.0 s, 197 MiB |

     Sampled every 0.2 s, the largest sum of the resident sets of Python and `kicad-cli` running together was 366 MiB and 429 MiB, both in `check`. The board after `fill` is 1.36 MB and 2.41 MB, `.fenolite/` 6.8 MB and 12 MB. A rebuild over the filled 665-part project left the board byte-identical.
  3. *`check` at 369 parts.* `model.validate`, `erc.lite`, `copper.clearance` (16 328 item pairs judged, no finding), `zone.fill` (3 zones current), `netlist.assignment_compare` (no difference) and `roundtrip` (RT1 equal) are `ok`. `drc.kicad` reports 499 `unconnected_items` (KiCad's cap; the canary fired), 29 `silk_over_copper` and 119 `silk_overlap` warnings.
  4. *Creepage.* With a `creepage` rule of 8 mm between `HV` and the rest, 10.0.6 reports 59 `creepage` violations, at the isolator's own pin rows and the low-voltage pins inside the strip, and `check` takes 8.4 s.
  5. *Fine pitch.* A `PWR` clearance of 0.3 mm gives 32 `copper.clearance` errors at `build`: the QFN-48's pads lie 0.2 mm from its exposed pad, and the pads of the 1.27 mm header 0.27 mm apart. The stand-in uses 0.2 mm; a board keeps the larger value away from such parts with an area rule (c0103).
  6. *Where the libraries come from*, `build --confirm` at 369 parts for target 10, the same board bytes in each case:

     | symbols and footprints from | resolved as | seconds | peak MiB |
     |---|---|---|---|
     | the verified cache of tag 10.0.6 (one file per symbol) | `scan` | 6.0 | 115 |
     | the install's folders, named by `KICAD10_SYMBOL_DIR` and `KICAD10_FOOTPRINT_DIR` | `scan` | 100.7 | 213 |
     | the install's template library tables | `template` | 161.2 | 217 |

     The macOS install and the pinned `kicad/kicad:10.0.6` image hold whole-library symbol files (`Device.kicad_sym` has 2 414 673 bytes in both; the controller's library 3.6 MB). The image holds 155 footprint libraries and 224 symbol entries under `/usr/share/kicad`. For target 9: from the 9.0.9 tag the build stopped after 131 s at `Converter_DCDC_Isolated`, a library that the 9.0 tag lacks; from the 10.0 install every library id is unknown.
  7. *A catalog-only board.* Three catalog parts on four layers, built and checked: `netlist.assignment-differs` (2) and `netlist.uncovered` (2), because the footprints carry no `Reference`: the defect that c0077, on the agent track, repairs. (The review of 2026-10-07 read `catalog/__init__.py:952` as a repair; that line sets the property on a symbol, not on a footprint. Task 0.1 runs the three-part board again on `dev`.)
  8. *Routing the stand-in.* One stub and via per SMD pad of `GND`, `+3V3` and `HV_RTN` (229, the controller excepted), the design file as `write_dsn` gives it and edited as c0107's probe does (inner layers `(type power)`, one `plane` per inner zone), Freerouting 2.4.1 with `-mp 20` and `--router.optimizer.enabled=false`, at most 2 700 s. Fanout: 518 of 863 SMD pins in 26 s. Autorouter: 344 unrouted items at the start, 107 after pass 1 (245 s), 32 after pass 20, and between 32 and 33 from pass 13 on. Done in 1 003 s (849 CPU s), heap peak 1 886 MB, resident 1.2 GB to 1.6 GB. Merged and refilled, KiCad counts 32 unconnected items and 3 `via_dangling`; 2 302 tracks and 293 vias were added.
  9. *Reused, measured the same day on the review branch:* the review's scale probe (100 to 600 parts on four layers, 20 s to 66 s for build, fill, check and export; 549 hand-computed vias at 600 parts; a decoupling capacitor 54 mm from its part on average after the grid placer); c0107 run r21 (100 parts, planes, optimizer off: no unconnected item after 370 s); c0109 P1 (the plugin as built: no copper after 912 s); c0110 (no Freerouting session in 900 s on a 0.8 mm BGA).

  None of this is committed. Task 1.2 records it in the evidence page.

- **No fact of this change rests on 9.0.9.** The board is built for KiCad 10 only (Decision 9). The one 9.0.9 fact used, the missing library in the 9.0 tag, was measured.

## Goals / Non-Goals

**Goals:**
- One authored board of 300 parts or more, readable as a user's script, that grows by stages as the changes of v0.4 land.
- A scheduled run that takes the board through the loop of its stage and leaves a record that compares across runs.
- Time and memory budgets per step, read from the board on the CI runner, that fail the run when crossed.
- Numbers for the open questions of other changes: c0109's default budget, c0113's acceptance board.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- A benchmark between routers or between machines: the record compares runs of one job.

## Decisions

1. **An invented eight-channel controller.** The board is a controller for eight identical 48 V synchronous buck channels with an isolated sense of a high-voltage bus. It is invented for Fenolite: no product, reference design or company board. The maintainer declared so on 2026-10-07 (proposal, "Provenance of the circuit"), and the statement is kept in `docs/evidence/yardstick.md`.

   | section | contents | parts |
   |---|---|---|
   | power input | 48 V terminal block, fuse, TVS, bulk and ceramic capacitors; a 12 V auxiliary input; a 3.3 V regulator; a power LED | about 18 |
   | controller | a 48-pin QFN controller with its decoupling, crystal, reset and boot parts, an SWD header, three status LEDs | about 25 |
   | CAN port | a transceiver in SOIC-8, termination, a terminal block | about 6 |
   | USB port | a micro-B receptacle, an ESD array, a VBUS divider, a shield RC; the pair `USB_DP`/`USB_DN` | about 6 |
   | channel, 8 times | a half-bridge driver in SOIC-8 with bootstrap diode and capacitor, two N-MOSFETs in TO-252, gate resistors, an RC snubber, a 12 mm inductor, input and output capacitors, a shunt and a current-sense amplifier in SOT-23-5, a feedback divider, a TVS, an output terminal block, an LED, an NTC divider | 37 each, 296 |
   | high-voltage sense | a terminal block, a divider of eight 1206 resistors, a TVS, an isolated amplifier in wide SOIC-8, an isolated DC/DC converter in wide SOIC-16, decoupling on both sides, filters | about 20 |
   | mechanical | four mounting holes with a pad | 4 |

   - About 370 parts and 160 nets; the stand-in of the Context has this composition (369 parts).
   - Each section is a function; `channel(n, x, y)` creates one channel's parts, nets and positions at a cell origin and is called eight times, as `bank()` is in `board_40parts`. A channel's references are numbered `n·100 + k` (`R301` is a resistor of channel 3), the shared sections below 100, so every finding names its channel.
   - Every value (48 V, gaps, clearances, the impedance of stage 3) is the example's own input, stated once at the top of the script with the comment `chosen for the example` or a public source id. The values are round: 48 V, 12 V and 3.3 V supplies; a gap of 8 mm between the high-voltage strip and the rest; clearances in steps of 0.05 mm; a board size in whole millimetres that the floor plan gives. Fenolite ships none (plan D6, as c0047).
   - The composition answers the review's yardstick, which is generic (four to eight layers, 300 to 600 parts, repeated channels, pairs, a high-voltage section); any invented circuit of that shape would serve, and nothing in the change depends on this one's values.
   - Rejected: the review's generated designs. Their data lists build, but a reader learns nothing from them, and the script must read as one a user writes. Rejected: a BGA controller (Non-goals).

2. **Parts of the official KiCad libraries, read from the verified cache.** The example names official library ids; its builds carry `needs_libs`, and the job fetches the 10.0.6 tag (Decision 8).
   - Rejected: the offline catalog. Since c0076 it holds many of the packages (Context), but a catalog-only board fails the net comparison until c0077 lands (measurement 7), and the yardstick is there to measure the path a user's board takes through the official libraries, whole-file symbol libraries included (measurement 6). The switch is an open question.
   - Rejected: footprints authored in the script. Same field defect, about twenty footprints to author with land patterns that stay `INFERRED`, and nothing learned about scale.

3. **Stages.** The board grows in five cumulative stages. `examples/yardstick/design.py` holds `STAGE = <n>` at module level; the runner reads it with `ast`, without running the script.

   | stage | the board gains | needs on `dev`, archived | steps added |
   |---|---|---|---|
   | 1 | four copper layers; zones `GND` on In1.Cu, `+3V3` and `VIN48` on In2.Cu (two outlines), `HV_RTN` on both under the strip; classes and minimums; a clearance rule between `HV` and the rest; a `creepage` rule at a value the board meets without a slot; the `USB2` interface; the schematic that `build` writes, one sheet per module; the BOM, the placement table and the manifest with its states | nothing beyond release 0.3.0 | `capabilities`, `build-dry`, `build`, `fill`, `check`, `export`, `render`, `bom`, `pnp`, `manifest`, `rebuild-dry`, `rebuild`, `inspect`, `build-install`, `heavy-read`, `heavy-rt1` |
   | 2 | six copper layers: F.Cu signal, In1.Cu `GND`, In2.Cu and In3.Cu signal, In4.Cu `+3V3` and `VIN48`, B.Cu signal; a declared stack-up | c0100, c0101 | — |
   | 3 | a rounded outline, a slot under the isolator and `design.hole` mounting holes (c0102); a high-voltage rule area with an area clearance, keep-outs round the holes with `rule_area` (c0103); pair class values and gap, skew and length rules on `USB_DP`/`USB_DN` (c0104); a differential impedance target (c0105); thermal via arrays in the controller's exposed pad and the transistor tabs (c0111), filled and capped (c0112); `near` rules for decoupling, crystal and drivers (c0113); a net tie between power and signal ground (c0114); the creepage minimum raised to a value only the slot meets | c0102, c0103, c0104, c0105, c0111, c0112, c0113, c0114 | `impedance` |
   | 4 | routed: plane fan-out, open-net selection and locks, a budget and tiers, the pair and the controller's escape by KiCadRoutingTools, the rest by Freerouting; length and skew judged; copper analyses | c0106, c0107, c0108, c0109, c0110, c0115 | `route-pairs` (KiCadRoutingTools), `route` (Freerouting), `fill-routed`, `check-routed`, `net`, `analyze` |
   | 5 | the rest of the package: schematic PDF, IPC-2581, ODB++, STEP, board PDF and DXF (c0116), fabrication and assembly drawings (c0117), fiducials, tooling holes and test points with their report (c0118) | c0116, c0117, c0118 | `export-package` (the new kinds), `testpoints` |

   - What moved since the table was first drawn (2026-10-07): c0061, c0064 and c0065 are archived on `dev`, so the schematic, `bom`, `pnp` and the manifest states are measured from stage 1 and no longer wait for stage 5. Stage 5's `testpoints` step is c0118's command.
   - c0096, c0097 and c0099 (board authoring, implemented on their branches) are needed by no stage. By the maintainer's decision 2 of 2026-10-07, stage 3's holes are c0102's `design.hole` and its keep-outs c0103's `rule_area`, to which c0096's `hole()` and `keepout()` adapt; its nearness rules are c0113's `near`, with c0113's `place.keepout` as the one keep-out predicate. By decision 3, part heights left c0113 for a change of their own after c0099, so "part heights under a lid" is no part of stage 3: the example takes it when that change exists, and the page names it `waiting` without holding a stage. c0097's explanation lines make `check` replies larger; reply bytes are recorded, not budgeted (Open Questions).
   - A stage is reached when the changes it needs are archived, its additions are in the example, and one scheduled run of it passes. A change that is cut leaves its addition out: the stage is reached without it, and the evidence page names it `not reached (cut: c<id>)`.
   - Each stage's additions use the names their owners give them; this change adds no script call, model field, CLI option or issue code.
   - Stage 1 merges alone; each later stage is one task group of this change. The change is archived when stage 5 is reached, or when the maintainer records the remaining parts as cut.
   - Rejected: one script per stage (five scripts to keep in step). Rejected: a flag per change inside the script (combinations no reader follows and no budget covers).

4. **The script places every part.** A floor plan: the power input along one edge, the controller, CAN and USB beside it, the eight channel cells in two rows of four, the high-voltage strip along the opposite edge with its copper at least the gap from low-voltage copper. The channel's offsets are authored once and repeated by translation. Connectors and holes are locked. `place` is not a step: a yardstick must give the same board on every run, and its floor plan is part of what a reader learns from the script. c0096's `place --strategy constrained` has its own acceptance boards; whether the yardstick later gains a dry-run placement step is an open question.
   - Rejected: `place --strategy grid`, blind to nets (54 mm from a capacitor to its part on average at 600 parts). Rejected: unplaced parts, which no headless placer would place well. The roadmap line `dsl-module-frame` will express the repetition natively; the example then follows it.

5. **No hand-computed copper before stage 4.** SMD pads of plane nets stay unjoined until c0107's fan-out runs in stage 4; thermal arrays come with c0111 in stage 3. The record counts what stays open.
   - Rejected: the review's method, one via per pad from footprint geometry read through a library API outside the DSL (549 vias at 600 parts). It is the gap stages 3 and 4 close; doing it in the example would hide it.

6. **The high-voltage gap, stage by stage.** Stage 1: the strip, its own return zones, the clearance rule, and a `creepage` rule (c0071, KiCad 10) whose minimum task 2.2 sets from KiCad's report to a value the board meets without a slot (the stand-in at 8 mm gave 59 violations). Stage 3: a slot under the isolator (c0102), the strip as a rule area with its clearance (c0103), and the creepage minimum raised to a value that only the slot meets. Stage 4: `analyze --kinds creepage,clearance` (c0047) with c0115's groove width and insulation between layers. Every value is the example's input.

7. **The runner.** `tools/yardstick.py`, standard library only, with three sub-commands.
   - `run [--example DIR] [--out DIR] [--budgets FILE] [--record FILE] [--summary FILE] [--only STEP,…] [--skip-heavy]` reads `STAGE`, then runs the stage's steps (Decision 3) in order, each as `python -m fenolite <args> --json` in `--out`, writing steps with `--seed 250025 --timestamp 2026-10-04T00:00:00Z --no-backup --confirm` as `tests/_acceptloop.py` does. It waits with `os.wait4` and keeps per step: the arguments, the exit code, wall seconds (monotonic clock), `peak_mib` (`ru_maxrss`, KiB on Linux and bytes on macOS), the reply's bytes and the issue counts by code. It then reads the stage's measures, applies the acceptance rules and the budgets, writes the record and a Markdown summary, and exits 0 (passed), 1 (a step, a rule or a budget failed) or 2 (usage, or a missing tool, library, corpus row or budget table).
   - Measures: parts and nets (`model.validate`), pads (`netlist.assignment_compare`), copper layers, board and `.fenolite/` bytes, zone fills, DRC errors and warnings by type, KiCad's `unconnected` count and, once c0141 marks report limits (`summary.limits`), whether it is capped; the artefacts per state from `manifest`; from stage 4, `route`'s `routed`, `unrouted`, `open`, `budget` and `runs` (c0108, c0109) and the open connections of `fenolite net` (c0108); c0113's measures from `check` when present.
   - Acceptance rules: every step exits as its stage expects (`check` exits 5 before stage 4); before stage 4 the stages of `check` that ran, `erc.kicad` and `parity` among them, are `ok` except `drc.kicad`, whose only error type is `unconnected_items`; a finding that only a repair in Fenolite can remove is accepted for a stage by an entry in the budgets file that names its owner (requirement "Yardstick runner"), so that stage 1 does not wait for it and does not hide it; `copper.clearance` has no finding and `netlist.assignment_compare` no difference; the rebuild dry run plans no write and the confirmed rebuild leaves the board's bytes unchanged; from stage 4, open connections and DRC errors at most their ratchets.
   - `row RECORD [--url URL]` prints one row of the evidence page. `rebase RECORD …` prints the budgets that Decision 10 gives from the records, as TOML for a person to commit.
   - Rejected: pytest tests that time themselves (the write modes are serial-only, and a timed test fails at random under load). Rejected: sampling `ps` for the sum over a process tree (not in every image, and it depends on timing; measurement 2 gives the sum once). Rejected: `tracemalloc` inside Fenolite (it misses `kicad-cli` and Java and changes the code it measures).

8. **Libraries in the job: the verified cache, the install measured once.** The job fetches the 10.0.6 tag with `tools/kicad_libs_fetch.py` into a folder kept by `actions/cache` and sets `FENOLITE_LIBS_CACHE`. The runner adds one step, `build-install`: a dry-run build with `FENOLITE_LIBS_CACHE` unset, so the libraries come from `/usr/share/kicad` of the image. It has a budget like any step, so the cost that a user with KiCad installed pays (101 s to 161 s against 6 s, measurement 6) is tracked.
   - Rejected: the install for every build (four builds of two to three minutes would bury Fenolite's own 6 s). Rejected: no install step (the common path would go unmeasured).

9. **KiCad 10 only.** The 10.0 install serves no target-9 build, and the 9.0 tag lacks a library the board uses (measurement 6); 9.0 cannot refill (`H-K-01`), so a target-9 loop needs a 10.0 container (`H-K-CLI-DOCKER`, verified locally only). The 9.0 writer stays proved by each change's benches and by c0025's recorded boards. Rejected: a target-9 leg from the 9.0.9 tag (another part for the missing library, and a build that measures the 9.0 library format).

10. **Budgets.** `tools/yardstick_budgets.toml` holds one table per stage: `source` (the runs it was read from, or `provisional`), `seconds` and `mib` per step, and from stage 4 the ratchets `open_connections` and `drc_errors`.
    - From the first three scheduled runs of a stage: seconds are the median × 1.5, rounded up to 10 s; MiB the largest × 1.25, rounded up to 50 MiB; a ratchet is the largest count of the three. Until then the values are provisional: the local measurement × 4 for seconds and × 2 for MiB, rounded the same way.
    - Stage 1 as it was computed from measurement 2 at 369 parts (`27ef3ad7`). It is kept to show the size of the numbers and is not committed: the `[stage1]` table of the budgets file is written by tasks 4.1 and 4.2 from one local run of the runner on the example on `dev`, by the same rule, with `bom`, `pnp` and `manifest` added and `check` including `erc.kicad` and `parity`:

      | step | seconds | MiB |
      |---|---|---|
      | `capabilities` | 10 | 150 |
      | `build-dry`, `rebuild-dry` | 40 | 300 |
      | `build` | 30 | 250 |
      | `fill` | 30 | 450 |
      | `check` | 40 | 550 |
      | `export`, `render` | 20 | 450 |
      | `rebuild` | 40 | 300 |
      | `inspect` | 10 | 200 |
      | `build-install` | 650 | 450 |
      | `heavy-read`, `heavy-rt1` | from the first run | from the first run |

    - A step above its budget fails the run. A budget is raised only in a commit that adds a row to the evidence page with the reason (more work by a change, another runner); it is lowered when three runs stay below half of it. Without `rebase`, a person computes the values by hand.
    - The route step's seconds budget is the `--timeout` passed to `route` (c0109) plus 300 s for the merge and the write.
    - Rejected: budgets in pull-request jobs (`make check` takes 20 minutes, runners vary, and one full suite runs at a time). Rejected: budgets from one run (one sample).

11. **The heavy demo boards.** Steps `heavy-read` (`fenolite inspect <board>`) and `heavy-rt1` (`fenolite roundtrip <board> --level rt1`) for each of the two rows, from the corpus cache, which the job fills with `tools/corpus_fetch.py --uses heavy --only` and the two board ids (the tag also covers an Altium sheet) and keeps with `actions/cache` keyed on the manifest's hash.
    - Not measured here: the boards are not in this machine's cache, and their 155 MB are fetched by task 1.3. From measurement 2, RT1's peak grows about 60 MiB per MB of board; carried to 85 MB, that is near 5 GB, an extrapolation that `H-K-YARD-HEAVY` settles.
    - Not `check`: KiCad's report on boards with hundreds of violations does not repeat (`docs/evidence/kicad-rt2.md`), and those projects are not the yardstick.

12. **The job.** `yardstick` in `nightly.yml`, on the workflow's `schedule` and `workflow_dispatch`, in its concurrency group; not a merge gate.
    - `runs-on: ubuntu-latest`, container `kicad/kicad:10.0.6@sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec` with `--user 0`, as the `routing` job; `timeout-minutes` 60 up to stage 3 and 180 from stage 4.
    - Steps in order: `actions/checkout@v4`; `astral-sh/setup-uv` with Python 3.12; `uv sync --locked --extra dev`; `kicad-cli version` showing `10.0.6`; the library cache and its fetch; the heavy rows' cache and fetch; from stage 4, Java 25, the Freerouting jar and KiCadRoutingTools as the `routing` job installs them, each checked by SHA-256; `uv run python tools/yardstick.py run --out "$RUNNER_TEMP/yardstick" --record "$RUNNER_TEMP/yardstick/record.json" --summary "$GITHUB_STEP_SUMMARY"`; `actions/upload-artifact@v4` of the record and the replies, `if: always()`, kept 90 days.
    - Rejected: a job in `ci.yml` (every push would pay its minutes). Rejected: a weekly run (a regression would hide among a week of merges). Rejected: a workflow of its own (`nightly.yml` exists for runs too heavy for pushes).

13. **The record and the page.** The record is JSON with the schema name `fenolite.yardstick-record.v0`: date, commit, stage, runner (system, CPU count, memory), tool versions (`fenolite`, `kicad-cli` and routers from `capabilities`), the board's measures, the steps, the acceptance rules with their results, the budgets used and the verdict. `docs/evidence/yardstick.md` holds: how to read it; `Stages` (each stage reached with its date and run, or waiting for, or not reached with the cut change); `Runs` (date, commit, stage, run URL, total seconds, largest peak MiB, open connections, DRC errors, verdict, note); `Budgets` (the source of the current values); `Not measured`. Rows are added at each stage and before each release, from `tools/yardstick.py row`. The release record of every release made after the job's first scheduled run names the newest run and its stage; the releases up to 0.3.0 have none.
    - Rejected: committing every run (CI would write to the repository). Rejected: artefacts only (they expire after 90 days, and no one reads a series across them).

14. **What the numbers say to other changes.**
    - c0109's default budget (its Open Questions): not enough for this board. One Freerouting run took 1 003 s here and would be cut at 900 s, and a single-tier run cut by the budget keeps no copper (c0109, Limits). The stage-4 route step passes `--timeout 3600` and tiers, and records `result.budget` and `result.runs`. The default stays c0109's to set, with this measurement in its evidence row.
    - The flat count from pass 13 (32 open) says that more time alone does not close the board; plane layers (c0107), the controller's escape (c0110) and a second pass over open nets (c0108) are what stage 4 measures.
    - c0113 names "c0119's board" for its acceptance: from stage 3 the board carries `near` rules and the record keeps c0113's measures from `check`.
    - `inspect` on a project folder exited 1 at `27ef3ad7` (Context): the runner passes the board file either way; c0066 is archived, so if task 0.1 still finds the defect on `dev` it is filed as an issue of its own, not as part of this change.

15. **Borders.** c0081 measures agent runs and may take this board as a task; this change runs no agent. c0141 marks KiCad's report limits per type, and c0120 owns progress and resumable jobs: the runner reads the marks and ignores progress lines. c0080, if archived, gets one tested guide line. c0077 decides the catalog switch (Open Questions). The living manifest requirements (c0065) own the manifest that `export`, `bom`, `pnp` and `manifest` write from stage 1.

16. **Other changes that hold the same capabilities** (checked 2026-10-07 on `origin/dev` at `9aba2dff`). This change adds requirements only: five in `release-gate` and one in `ci-baseline`; no name of them exists in a living spec or in an open change.
    - `release-gate`: one open change on `dev` holds a delta, c0136 (MODIFIED "Version 0.2.0", the milestone renaming). It is another requirement; either order of landing works, and neither regenerates.
    - `ci-baseline`: no open change on `dev` holds a delta. "macOS application nightly job" (c0068) and "KiCad 9.0 oracle job" are living and untouched. The job shares `nightly.yml` with `macos-app`, the only job there on `dev`; the `macos_app` tests of `test_ci_workflow.py` read that job only.
    - Among the 26 proposals of v0.4, none adds to `release-gate` or `ci-baseline` besides this one (review of 2026-10-07); c0078 changes the `routing` job of `ci.yml`, which stage 4 copies its router install from, so task 8.1 reads that job as it is then.

17. **The second backend.** `dev` writes Altium documents (c0084 to c0088). The yardstick is built for KiCad and judged by `kicad-cli`; it adds no rule kind, selector or model field, so no row of the Altium rule table and no lowering changes, and no requirement of this change has an "in an Altium build" clause. An Altium build of the example is no step: its verdict would need Altium Designer, which no CI job has, and the Altium write side is proved by its own samples and the verification kit (c0091, c0092). Rejected: a `build --target altium --dry-run` step as a smoke test: it would pass or fail on the stage's newest constructs (rule areas, pairs, net ties), whose Altium rows belong to their own changes, and the yardstick would become their gate.

## Files and public API

| file | content |
|---|---|
| `examples/yardstick/design.py` (new, CC0) | the board; `STAGE` |
| `examples/README.md` | the row of the example |
| `tools/yardstick.py` (new) | `main(argv: list[str] \| None = None) -> int`; sub-commands `run`, `row`, `rebase`; `read_stage(path) -> int`; `steps_for(stage) -> tuple[Step, …]`; `peak_mib(usage, platform) -> float`; `judge(record, budgets) -> list[Finding]` |
| `tools/yardstick_budgets.toml` (new) | budgets per stage |
| `tools/README.md`, `Makefile` | the tool; `make yardstick` (the runner on a local cache) |
| `tests/unit/test_yardstick.py` (new) | hermetic: stage reading, steps per stage, measures, budgets, exit codes, record and row, with a fake `fenolite` |
| `tests/unit/test_examples.py` | the yardstick's structure, loaded without a build |
| `tests/libs/test_yardstick_build.py` (new, `needs_libs`) | the example builds for target 10 from the verified cache |
| `tests/unit/test_ci_workflow.py` | the job's shape |
| `.github/workflows/nightly.yml` | the job `yardstick` |
| `docs/evidence/yardstick.md` (new) | the page |
| `docs/hypotheses.md`, `docs/evidence/sources.md`, `docs/roadmap.md`, `CHANGELOG.md` | rows |

Nothing under `src/fenolite/` changes.

## Sources registered by this change

One, registered at task 5.1 under the next free id of the block S-0702 to S-0719 (the block S-0700 to S-0719 was given to this group on 2026-10-07; c0116 takes S-0700 and S-0701): the public README of `actions/upload-artifact`, read for `retention-days`. The schedule and the runner labels rest on S-0362 and S-0363 (c0068).

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-YARD-STAGE1 | Stage 1 of `examples/yardstick` (300 parts or more, four copper layers, inner zones, a schematic of one sheet per module, target 10) builds, fills, passes every `check` stage but the unconnected items of KiCad's DRC and the accepted findings the budgets file names, exports, renders and rebuilds to the same bytes on `kicad-cli` 10.0.6 | the `yardstick` job | three scheduled runs of stage 1 with the verdict `passed`; the row names them |
| H-K-YARD-STAGE2 | The same on six copper layers with a declared stack-up (c0100, c0101) | the `yardstick` job | as above, for stage 2 |
| H-K-YARD-STAGE3 | The same with the shape, rule areas, pair, impedance, placement and via rules of stage 3, every `check` stage of those changes `ok` | the `yardstick` job | as above, for stage 3 |
| H-K-YARD-STAGE4 | The routed board passes `check` with no more open connections and DRC errors than its ratchets | the `yardstick` job | as above, for stage 4; the ratchets of the first three runs are recorded |
| H-K-YARD-STAGE5 | Every artefact of the stage-5 package is written, listed in the manifest and accepted by the `kicad-cli` command that made it | the `yardstick` job | as above, for stage 5 |
| H-K-YARD-LIBREAD | A build of the yardstick from the whole-file libraries of a KiCad install takes at least ten times as long as from the verified cache, with the same board bytes | the `build-install` and `build` steps | the ratio in three runs; refuted below 10 |
| H-K-YARD-HEAVY | Fenolite reads the two heavy demo boards of the corpus (84.8 MB, 69.6 MB) and round-trips them with RT1 equal on the CI runner, within the job's limit | the `heavy-read` and `heavy-rt1` steps | both boards with no error issue and RT1 equal in three runs; their seconds and MiB become budgets |
| H-G-DSN-YARD | Freerouting 2.4.1 through its plugin, with c0107's planes and c0109's budget, leaves the stage-4 board with no more open connections than its ratchet | the `route` step of stage 4 | three runs; first record: 32 open after 1 003 s on the stand-in (measurement 8) |

`H-G-DSN-YARD` has the backend `specctra`; the others `kicad`. All start `INFERRED`, with the measurements of the Context as first record, each marked as taken at `27ef3ad7` on a stand-in. No statement holds a budget clause: "each step within its budget, on the CI runner" was taken out on 2026-10-07, because seconds and MiB are measures of one runner and not facts of KiCad. A run that passes KiCad's verdict and crosses a budget fails the job and leaves the label where it is. Ids used without changing their level: `H-K-01`, `H-K-CLI-DOCKER`, `H-K-REL-LOOP40`, `H-K-DRC-LIMIT`, `H-K-AN-CREEP-2`, `H-K-LIB-READ`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| stage 1 on the CI runner | `KICAD-VERIFIED (10.0.x)` after three scheduled runs; `INFERRED` with the local record before | `H-K-YARD-STAGE1` |
| stages 2 to 5 | `KICAD-VERIFIED (10.0.x)` per stage reached | `H-K-YARD-STAGE2` to `-STAGE5` |
| runner, record, budgets | mechanical | `tests/unit/test_yardstick.py` |
| a step within its seconds and MiB | measured per run on the CI runner; no evidence label | the record's `budgets` and `verdict`, the `Runs` table |
| the job's shape | mechanical | `tests/unit/test_ci_workflow.py -k yardstick` |
| the example's structure | mechanical | `tests/unit/test_examples.py -k yardstick` |
| library read cost | `INFERRED` until three runs | `H-K-YARD-LIBREAD` |
| heavy boards | `INFERRED` until three runs | `H-K-YARD-HEAVY` |
| routing of stage 4 | `ORACLE-VERIFIED(freerouting 2.4.1)`, judged by KiCad's count | `H-G-DSN-YARD` |

## Risks / Trade-offs

- **A scheduled run fails unseen.** The summary and the artefact show it; the page gets a row per stage and per release; the release record names the newest run.
- **Runner noise crosses a budget.** Budgets come from three runs with a margin of 1.5 on time; a run that fails a budget once and passes on the next is noted in the page, and the budget is not raised for it.
- **A late change holds a stage.** Stages are reached without cut parts; stage 1 needs no other change.
- **The built schematic does not pass ERC or parity at 370 parts.** Not measured on `dev`. Task 2.2 finds out; a finding the example cannot remove is accepted with its owner named, counted in every record, and shown on the page until its repair lands.
- **Proofs that are scheduled runs.** Tasks 5.2 and the stage tasks end in "three scheduled runs", which nobody can run inside an iteration. Each such task therefore has a local proof that closes the code, and a follow-up line that the coordinator ticks after the runs.
- **The board drifts with the libraries.** Library ids of the pinned 10.0.6 tag, in a verified cache keyed on its pin.
- **The router does not repeat.** Ratchets come from three runs; the record keeps each run's counts.
- **Memory on the runner.** Java held 1.9 GB of heap on the stand-in and RT1 of the heavy boards may need several GB; both are recorded and budgeted.
- **A long job.** Stage 4's route budget of 3 600 s and the heavy rows make the job about an hour; `timeout-minutes` 180.

## Migration Plan

- Additive: an example, a tool, a budgets file, a page, a job, tests. Nothing in the package or in other jobs changes.
- Rollback: remove the job; the example and the tool can stay.

## Budget (8.75 days)

| part | days |
|---|---|
| entry check, registers, recorded probes | 0.5 |
| stage 1 of the example: circuit, floor plan, channel cell, rules, zones | 1.5 |
| the example's structure test, README rows | 0.25 |
| runner: steps, measures, record, rules, accepted findings, budgets, `row`, `rebase`, tests with a fake CLI | 1.75 |
| budgets file, evidence page | 0.5 |
| job, workflow test, first runs, budgets from them | 0.75 |
| heavy rows | 0.25 |
| stage 2 | 0.5 |
| stage 3 | 1.0 |
| stage 4 | 1.0 |
| stage 5 | 0.5 |
| documentation and closing | 0.25 |

Cut order: (1) stage 5, recorded as not reached; its changes have their own acceptance. (2) `rebase`. (3) The heavy rows, whose part of G60 then returns to the roadmap. (4) Stage 3's parts of c0113 and c0114, recorded. Never cut: stage 1, the runner with its budgets, the job, the page.

## Open Questions

- **The catalog.** c0076 is archived; when c0077 is too, should the example take catalog ids where the catalog has the part, so that it builds offline and its build test is hermetic? Default: no in v0.4; the yardstick measures the path through the official libraries.
- **A placement step.** With c0096 on `dev`, should the runner add `place --strategy constrained --dry-run` on a copy with the placements removed, to measure the constrained placer at 370 parts? Default: no; c0096 has its own acceptance, and the step would need a second form of the script.
- **Whole-file libraries.** A build from a KiCad install takes 101 s to 161 s against 6 s (measurement 6). Default: a new roadmap line, `library-read-speed`, for the maintainer to place; the `build-install` budget tracks it until then.
- **Reply sizes.** Record only, or a budget on `check --format concise` as well (5 807 bytes at 369 parts, 5 820 at 665)? Default: record only.
- **The schedule.** Nightly, or weekly once stage 4 routes for an hour? Default: nightly; reconsidered if the job passes 60 minutes.
- **A release gate.** Should a release need the newest run to have passed? Default: the record names it, and the maintainer decides per release.
