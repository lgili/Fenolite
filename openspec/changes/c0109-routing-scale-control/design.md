## Context

**Scope.** Milestone v0.4 (`docs/roadmap.md`, "v0.4: proposals on other branches", row c0109 `routing-scale-control`; called v0.2c until c0136 renamed the milestones on 2026-10-07).

**The code on `origin/dev`** (`9aba2dff`, checked 2026-10-07; both plugins, `cli/cmd_route.py` and `cli/main.py` have not changed since the proposal was first written, so the line numbers below hold):

- *KiCadRoutingTools plugin* (`routing/plugins/kicad/routingtools.py`): one process per net (`:113`), each with `--nets <one name>` (`:123-124`). For each net the board is written and read again (`:114`, `:116`, `:170`). Each process has 600 s (`:58`, `:145`), and nothing bounds the job. A timeout gives `route.tool-failed` (error) for that net and the loop goes on (`:148-158`). The living requirement "KiCadRoutingTools plugin" asks for one run with `--nets <names…>` and an empty result on failure; no decision records the loop.
- *Order*: `select.unrouted` sorts the nets by name (`select.py:38`); the command keeps that order.
- *Freerouting plugin* (`routing/plugins/specctra/freerouting.py`): one process with `-mp 20 -mt 1 -da --gui.enabled=false` (`:208-221`) and 900 s (`:39`). A timeout returns no copper and `route.tool-failed` (`:303-309`).
- *Design file*: every net that has pads is declared, selected or not (`backends/specctra/dsn.py:425-430`), with one exception that `dev` gained with c0061 (commit 65c43f42, `dsn.py:343-352`): a net of one pad named `unconnected-(…)` is not declared and its pad is a pin on no net. That is the mechanism of Decision 4, applied to one family of nets; `to_copper` drops the copper of the nets that were not selected (`ses.py:305-311`, `:336`).
- *`--timeout`* defaults to 600 (`cli/cmd_route.py:76`) and works as a sentinel: a router is built again only when the value differs (`:97`, `:101`), and for Freerouting 600 becomes 900 (`:104`). Asking for 600 s gives 900 s.
- *Writes*: under `--confirm` the planned writes are made even when the result holds errors; the exit code is then 5 (`cli/main.py:295-308`). c0108 changes this for `route`: no write is planned when an issue of severity error is reported.

**The tools**, from their pages and from running them as programs (ADR-0006; c0016):

- KiCadRoutingTools v0.22.1, `route.py --help` of the pinned checkout (S-0216): `--nets` takes several names or globs; `--ordering {inside_out,mps,original,bus}`, default `mps`; `--clearance` sets the Default class of the run, and "Nets in other classes route at their own class clearance (pairwise max, as KiCad does)", read from the project file beside the board; `--track-width`, `--via-size` and `--via-drill` take one value per run; `--json-out FILE` writes the run's summary; no option bounds time. `--escalation {off,board,fab}`, default `fab`, retries a failing net below the requested sizes, "down to the fab tier floor, below the board's own minimums".
- Freerouting 2.4.1, its command-line page at the tag (S-0221): `-inc` lists classes whose nets "the autorouter will not route"; `-mt 0` is "to disable route optimization"; no argument limits time; `-do` "Saves the routing results when the routing is finished". Its settings page at the tag (S-0222): `router.optimizer.enabled`, default true.

**Measured on 2026-10-05** with the Freerouting 2.4.1 jar (OpenJDK 26.0.2), the KiCadRoutingTools v0.22.1 checkout and `kicad-cli` 10.0.6 on macOS arm64. The machine was shared with other runs (load average 33 to 88 on 10 cores), so wall times are upper bounds; Freerouting's own CPU seconds are given beside them. The bench is a generated board, not committed. Its generator is the script of the review's scale probe (the one c0107 and c0108 cite for 100 to 600 parts), written for Fenolite: the net names (`ch01_*` and so on) and the board size are what it gives for 100 parts, not values of an existing board. Task 1.2 writes that statement, checked against the script, into the evidence page. The board has 4 copper layers, 76 × 92 mm, 100 parts (an LQFP-100 controller, 5 ICs, 90 passives, 3 headers), 103 nets; GND is a zone on In1.Cu and +3V3 on In2.Cu, and each of their 84 SMD pads already has a stub and a via to its plane; classes PWR (0.4 mm track, 0.2 mm clearance) and SIG (0.2 mm, 0.15 mm), Default 0.2 mm and 0.2 mm. Unrouted, KiCad counts 128 unconnected items.

Runs 2 to 4 call the jar directly, `java -jar freerouting-2.4.1.jar -de board.dsn -do board.ses -mp 20 -mt 1 -da --gui.enabled=false` plus the arguments named, on the design file the plugin writes for run 1's job. The runs of 5 call `route.py <board> <out> --nets <names> --track-width 0.2 --via-size 0.6 --via-drill 0.3 --json-out <file>` plus the flags named, in a folder written by `write_triad`. Each routed copy is merged with `routing.merge.apply` and judged with `fenolite fill <board> --confirm` and `fenolite check <board>` on KiCad 10.0.6.

1. *The plugin as built*: `fenolite route <board> --router freerouting --timeout 900 --confirm`. 101 nets selected, 103 declared. Fanout 21 s. The autorouter worked on 191 items, the 101 nets and the connections of GND and +3V3, and had 0 unrouted after 6 passes, at 256 s (119 CPU s). The optimizer started at 259 s and printed nothing more. The timeout killed it at 900 s: no copper, 101 `route.unrouted`, `route.tool-failed`, exit 5 after 912 s. KiCad still counted 128 unconnected items.
2. *The same design file with `--router.optimizer.enabled=false`*: the same passes and scores; the session was saved when the autorouter ended (863 s wall under load, 203 CPU s). 185 of its 525 wires were on GND and +3V3 and were dropped by `to_copper`. The 101 nets got 1190 tracks and 197 vias. After `fill`, KiCad counted 11 unconnected items, all between GND or +3V3 stubs and plane islands: 661 of the new tracks lie on In1.Cu and In2.Cu and split the two planes into 8 and 5 fills. DRC errors: `unconnected_items` 11, `track_width` 2 (two 0.12 mm segments under the 0.15 mm minimum). Fenolite's copper check: 0 findings.
3. *The same, with GND and +3V3 left out of the network section* (their pins netless, their stubs and vias written without a net and still protected): the autorouter worked on 103 items and had 0 unrouted after 4 passes; session at 423 s wall, 112 CPU s, 45 % less than run 2. No wire on GND or +3V3. The 101 nets got 1084 tracks and 190 vias. KiCad: 21 unconnected items, again all on GND and +3V3 plane islands (10 and 13 fills); no `track_width`, no clearance violation. Freerouting's own score counted 256 "violations" instead of 83; KiCad found none of them.
4. *The built blink* (3 nets): with `-mt 0` and with `-mt 1` the log shows "Optimization stage started"; with `--router.optimizer.enabled=false` it shows none and the session is saved when the autorouter ends. LED_A moved into a class `IGN` of its own and named with `-inc IGN` (first argument or last) or with `--router.ignore_net_classes=IGN` was routed every time: "3 unrouted items", 2 wires on LED_A. With GND left out of the network section: "2 unrouted items", no wire on GND.
5. *KiCadRoutingTools*, first on the 28 nets of one channel (`--nets 'ch01_*'`):
   - the plugin as built, one process per net: 527 s (load 27 to 45); the 28 nets closed; 345 tracks, 57 vias. 8 `route.copper-removed`: the tool removed copper of earlier nets and the plugin put it back, and KiCad reports `tracks_crossing` between `ch01_M4` and `ch01_P3` (Fenolite's copper check: one short). One via is 0.3 mm with a 0.15 mm drill where the class asks 0.6 mm and 0.3 mm (`via_diameter`, `drill_out_of_range`, `annular_width`).
   - one process with the 28 names, no `--clearance`, the tool's default escalation: 136 s; the 28 nets closed, no crossing, no short; the same three via errors. The tool's summary: "389 feature(s) on 10 net(s) delivered below the requested size", vias of 0.6 mm made 0.3 mm in pads.
   - the same with `--escalation off`: 24 s; the 28 nets closed; every track 0.2 mm and every via 0.6 mm with a 0.3 mm drill; no DRC error.

   Then on all 101 nets in one process: with the default escalation, 296 s, the 101 nets closed, and KiCad reports 199 `track_width`, 14 `via_diameter`, 14 `annular_width`, 12 `drill_out_of_range` and 6 `hole_clearance` errors (2261 features under the requested size on 43 nets, tracks down to 0.0889 mm). With `--escalation off --no-fix-drc-settings`, 70 s (load 13 to 22): 94 of 101 nets closed, the 7 others named by the tool's summary and open in KiCad, no other DRC error, copper check clean.

The commands, scripts and outputs are kept with the review's probes; task 1.2 records the numbers in `docs/evidence/routing.md`.

## Goals / Non-Goals

**Goals**
- `route` has one time limit, whatever the router, and keeps what finished inside it.
- A router spends its time on the nets of the job.
- KiCadRoutingTools routes the nets of a size group together, so its ordering and rip-up act across them.
- A caller can put critical nets first.
- The two plugin requirements say what the code does.

**Non-Goals**
- Everything under "Non-goals" in the proposal.
- Routing settings of either tool beyond the optimizer switch and the escalation floor: nowhere, because `--router-option` already passes any setting to KiCadRoutingTools, and no other Freerouting setting was measured.

## Decisions

1. **One budget per `route`.** `RoutingJob.budget: float | None = None`: wall-clock seconds for the plugin's `route()`. `None` gives the plugin's `DEFAULT_BUDGET`, 900 s for both external plugins. `fenolite route --timeout SECONDS` sets it for every router; the sentinel goes, so `--timeout 600` gives 600 s, and a value that is not positive exits 2. Each process gets the time left on a `time.monotonic()` clock started before the first process. `direct` starts no process and ignores it.
   - Rejected: per-process limits, as today (600 s for each of 101 nets, nothing for the job).
   - Rejected: a new option `--budget` beside `--timeout`: two names for one limit.

2. **A finished run is what is kept.** A router run (one process) that ends inside the budget keeps its copper, as today. The run under way when the budget ends is killed and gives none: Freerouting writes its session only when routing has finished (S-0221), and the output board of a killed KiCadRoutingTools process may be missing or cut, so the plugin does not read it. Runs never started are `RoutingResult.not_attempted`. One `route.budget-exhausted` (warning) per job gives the budget and the counts; the nets of the killed run and of the runs not started are in `unrouted` and get the command's `route.unrouted`. The exit code stays 0 when nothing else failed; c0108's option makes open nets an error when the caller asks.
   - Rejected: `route.tool-failed` (error) at the deadline, as today: the caller set the limit and nothing failed; and under c0108 an error plans no write, so the finished runs would be lost.
   - Rejected: a signal at the deadline and reading what the tool left: neither tool documents writing on a signal.
   - Rejected: Freerouting's `-im` snapshots: "a version-specific binary format", not a session.

3. **KiCadRoutingTools: one process per group.** A group is the nets of one tier (Decision 5) whose `JobNet` width, via diameter and via drill are equal. The command is `<python> <path>/py_router/route.py <board> <routed> --nets <names in job order> --track-width W --via-size D --via-drill H --escalation off --no-fix-drc-settings`, with the router options appended as today. `--no-fix-drc-settings` keeps the run folder's project file the one the plugin wrote, so a run never reads floors that an earlier run loosened (c0110 passes it to its pair steps too). There is no `--clearance`: the tool reads each class's clearance from the project file that the plugin already writes beside the board (measured 5). Groups run in the order of their first net in the job, and the board is written once per run, not once per net. `--router-option group-nets=N` splits a group into runs of at most N nets in job order, for smaller kept units. A run that exits non-zero or leaves no readable board gives `route.tool-failed` (error) naming its nets, and the next run starts.
   - `--escalation off`: the sizes are the job's; a net that does not fit is left open and reported, instead of a narrower track or via. Measured 5: with the default, one run on 101 nets made 2261 features smaller than asked and KiCad reported 245 size errors; with `off`, no size error, 7 of 101 nets left open, and a quarter of the time. Rejected: the tool's default `fab`, whose floor is a fabricator's, not the board's.
   - Rejected: one process per net (today; measured 5: four times slower on 28 nets, and a crossing of two nets from copper the tool had removed and the plugin put back).
   - Rejected: one process for every net, with widths from `--power-nets-widths`: one width per glob and one via size for all.

4. **Freerouting sees only its nets.** `write_dsn` gains `others: Literal["declared", "netless"] = "declared"`. With `"netless"`, a net that is not selected and owns no plane (c0107) is left out of the network section and of every class, as the writer on `dev` already leaves out a one-pad `unconnected-(…)` net in every mode; its pins become netless pins, and its wires and vias are written without a net and stay protected, so they remain obstacles. The plugin passes `"netless"`. Measured 3 and 4: the router works on the job's nets only, and KiCad found no clearance violation.
   - The router does not know the class of a left-out net. In run 3 the left-out class (0.2 mm) equalled the board's default rule (0.2 mm). `H-G-DSN-NETLESS` probes a left-out class wider than the default rule. If KiCad then reports a clearance violation, the fallback is: a left-out net whose class clearance exceeds the default rule stays declared, as today, and the plugin names it with `route.net-declared` (info), a code of `routing.codes`, whose list "Routing issue codes" leaves open; "Specctra issue codes and facts", whose list is closed, is not touched.
   - **Built on 2026-10-08: the fallback applies.** The probe gave `dsn-netless` = `present`: on a bench where the straight routes pass 0.3 mm from the pads of a left-out net of a 0.4 mm class (default rule 0.2 mm), Freerouting drew them straight and KiCad reported 2 `clearance` violations; with that net declared, the routes bend away and KiCad reports none (`dsn-netless-declared` = `absent`). `write_dsn(..., others="netless")` therefore keeps such a net declared, the plugin reports `route.net-declared`, and `H-G-DSN-NETLESS` is superseded by `H-G-DSN-NETLESS-2` (`docs/evidence/routing.md`, "Scale (c0109)"). On the bench of run 3 nothing changes: PWR's clearance equals the default rule, so GND and +3V3 still leave the network section.
   - Rejected: `-inc` with a class of the left-out nets: documented, but not honoured by the 2.4.1 jar (measured 4).
   - Rejected: declaring every net and dropping the copper, as today (measured 1 and 2: 191 items instead of 103, and the job's nets are fitted around copper that is thrown away).

5. **Tiers.** `--order GLOB` (repeatable): tier 0 holds the nets that match the first glob, tier 1 those that match the second and not the first, and the last tier the rest. `JobNet.tier: int = 0`, and `RoutingJob.nets` is sorted by tier, then by name. A plugin routes tier after tier, and the copper of earlier tiers is fixed input of later ones: KiCadRoutingTools finds it in the board it is given, Freerouting as protected wiring. Without `--order` there is one tier: one Freerouting run, one KiCadRoutingTools run per group. Inside a tier each tool keeps its own order.
   - Rejected: one net at a time in the caller's order (`--ordering original`): it gives up the rip-up the tool does between the nets of a run. `--router-option ordering=original` still reaches the tool.
   - Rejected: priorities inside one Freerouting run: version 2.4.1 documents none.

6. **Freerouting's optimizer is off by default.** The plugin passes `--router.optimizer.enabled=false` (S-0222); measured 2 and 4, the session is written when the autorouter ends. `--router-option optimize=on` adds a second run on the same file with the optimizer on, given the budget that is left; its session replaces the first when it ends in time, else the first is kept and `route.optimizer-cut` (info) says so.
   - Rejected: `-mt 0`, documented as disabling the optimizer: measured 4, it does not.
   - Rejected: the optimizer on by default: measured 1, every connection was closed at 256 s and all of it was lost at 900 s.

7. **What the result says.** `RoutingResult` gains `runs: tuple[RouterRun, ...] = ()` and `not_attempted: tuple[str, ...] = ()`, with `RouterRun(nets: tuple[str, ...], tier: int, seconds: float, outcome: Literal["done", "failed", "cut"])`. `route` adds `result.budget` (`seconds`, `spent`, `exhausted`), `result.runs` (per run: `tier`, `nets` as a count, `seconds` to 0.1 s, `outcome`) and `result.not_attempted`. Rejected: a time per net, which would be 600 lines on a yardstick board.

8. **Order with other changes** (checked on `origin/dev` at `9aba2dff`, 2026-10-07; task 0.1 checks again). No open change on `dev` holds a delta of "KiCadRoutingTools plugin", "Freerouting plugin" or a requirement this change adds; both MODIFIED deltas are generated from the living text of that commit, which is the text of 2026-10-05.
   - c0108 lands first. It modifies "Net selection" and "Route command" and adds "Router copper on open nets"; this change modifies none of them. Its selection is how a cut job resumes: `route` again selects the nets still open. Its verdict after the merge recomputes `routed` and `unrouted`; `not_attempted` and `runs` stay the plugin's account. Its rule that an error plans no write is why reaching the budget is a warning (Decision 2).
   - "Freerouting plugin" is touched by three proposals of v0.4, in a fixed order (review of 2026-10-07, item 14): c0078 (the jar's third location; it also relaxes "MUST NOT download"), then this change (run, tiers, optimizer, result), then c0110 (the option `fanout`, the neck-down argument). c0078 is not on `dev` at `9aba2dff`, so this delta still holds the living Location bullet and the living last line; task 0.1 regenerates it from c0078's archived text and re-applies only this change's edits. c0110 regenerates from the text this change leaves.
   - c0107 lands first. It adds planes, layers and rules through ADDED requirements, `RoutingJob.plane_layers` and `JobNet.layers`, and modifies "Design files are written from the model" (its Network bullet then states the one-pad rule); this change does not modify that requirement, it adds a mode of `write_dsn` beside it and names the bullet as c0107 leaves it. A plane's net stays declared (Decision 4). c0107's plane fan-out runs in the command before the plugin, outside the budget. `budget` and `tier` come after c0107's fields.
   - c0110 adds escape and pair steps that run, for KiCadRoutingTools, before the single nets, one process each. They are runs of this change: inside the budget, listed in `runs`, kept when finished. A pair's two nets share a tier. c0110 lands after this change and writes its steps on these groups; its two KiCadRoutingTools requirements point at "Routing time budget".
   - The part of c0120 that is written later (staged plans; decision 6 of 2026-10-07 split it) owns progress lines and resumable jobs. The end of a `RouterRun` is the natural progress event; this change prints nothing itself.
   - Nothing here meets the second backend: the Altium build takes routed copper from a KiCad board (`--copper-from`), whatever router and budget made it.

9. **Determinism.** Tiers, groups and their order follow from the job alone. A budget that is not reached keeps everything, so the copper is what the tools give today: Freerouting with `-mt 1` (`H-G-DSN-REPEAT`), KiCadRoutingTools by `H-K-KRT-REPEAT`. A budget that is reached keeps a set of runs that depends on the machine's speed; `result.runs` says which.

## Files and public API

| file | change |
|---|---|
| `src/fenolite/routing/protocol.py` | `RoutingJob.budget`, `JobNet.tier`, `RouterRun`, `RoutingResult.runs`, `RoutingResult.not_attempted` |
| `src/fenolite/routing/budget.py` (new) | `Budget(seconds)`: `left()`, `spent()`, `run(args, *, cwd, env) -> RunOutcome`, the one place that starts a process with the time left and kills it at the end |
| `src/fenolite/routing/codes.py`, `src/fenolite/cli/data/explain.toml` | `route.budget-exhausted` (warning), `route.optimizer-cut` (info), each with its `explain` entry; `route.net-declared` (info) with its entry only if the fallback of Decision 4 applies |
| `src/fenolite/routing/plugins/kicad/routingtools.py` | `DEFAULT_BUDGET = 900`; groups, tiers, `group-nets`, `--escalation off`, `--no-fix-drc-settings`; the constructor's `timeout` becomes `budget` |
| `src/fenolite/backends/specctra/dsn.py` | `write_dsn(..., others="declared" \| "netless")`; the fallback of Decision 4, if it applies, keeps wider classes declared |
| `src/fenolite/routing/plugins/specctra/freerouting.py` | `DEFAULT_BUDGET = 900`; netless other nets, the optimizer switch, tiers as runs, `optimize=on` |
| `src/fenolite/cli/cmd_route.py` | `--timeout` as the budget, `--order GLOB`, `result.budget`, `result.runs`, `result.not_attempted` |
| `tests/_fakerouter.py`, `tests/_fakefreerouting.py` | modes that record each run's nets and sleep a given time |
| `tests/unit/routing/test_budget.py` (new), `test_routingtools.py`, `test_freerouting.py`, `tests/unit/backends/specctra/test_dsn.py`, `tests/unit/cli/test_route_cmd.py` | the scenarios of the deltas |
| `tests/routing/test_krt_gate.py`, `test_freerouting_gate.py` | `test_group`, `test_no_optimizer`, `test_netless` |
| `docs/routing.md`, `docs/cli-contract.md`, `docs/evidence/routing.md`, `docs/formats/specctra/dsn.md` | the budget, tiers, groups, the netless mode, the measured record |

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-G-DSN-NOOPT | With `--router.optimizer.enabled=false`, Freerouting 2.4.1 runs no optimization stage and saves its session when the autorouter stage ends; `-mt 0` does not stop the stage (S-0221, S-0222) | `tests/routing/test_freerouting_gate.py::test_no_optimizer` | on the blink: outcome `dsn-noopt` = `absent` (no "Optimization stage" line, a session), `dsn-mt0` = `present` |
| H-G-DSN-NETLESS | Freerouting 2.4.1 routes no wire on a net left out of the network section, keeps its netless pins and protected wiring as obstacles, and keeps clear of them by at least the clearance KiCad requires when the left-out class is wider than the default rule; a class named with `-inc` is still routed (S-0221) | `::test_netless` | outcome `dsn-netless` = `absent` (no session wire on the left-out net; no KiCad clearance violation on the bench of task 1.3), `dsn-inc` = `present` |
| H-K-KRT-GROUP | At v0.22.1, one `route.py` run with every name of a group in `--nets`, the group's track width and via sizes, `--escalation off`, `--no-fix-drc-settings` and no `--clearance` exits 0, routes each net at its class clearance read from the project file, and the routed board has no unconnected item and no new error type under `kicad-cli` of its major (S-0216) | `tests/routing/test_krt_gate.py::test_group` | on the blink with two classes: `krt-group-t9` and `krt-group-t10` = `equal` |

All three start `INFERRED`, with the measurements of "Context" as their first record. Ids used without changing their level: `H-G-DSN-ACCEPT`, `H-G-DSN-PROTECT`, `H-G-DSN-ROUTE`, `H-G-DSN-REPEAT`, `H-G-DSN-INCOMPLETE`, `H-K-KRT-CLI`, `H-K-KRT-ROUTE`, `H-K-KRT-REPEAT`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| budget, kept runs, tiers, groups, `not_attempted`, codes | mechanical | unit tests with the fake tools |
| netless other nets in the design file | mechanical; `ORACLE-VERIFIED(freerouting 2.4.1)` for the router's reading | `test_dsn.py`; `H-G-DSN-NETLESS` |
| the optimizer switch | `ORACLE-VERIFIED(freerouting 2.4.1)` | `H-G-DSN-NOOPT` |
| grouped KiCadRoutingTools runs | `KICAD-VERIFIED (9.0.x, 10.0.x)` for the pinned tag | `H-K-KRT-GROUP` |
| every `route` result | `UNVERIFIED`, as today | — |

## Risks / Trade-offs

- **A budget that is too short keeps nothing.** One tier and one group make one run. Mitigation: the warning names the budget; `group-nets` and `--order` make smaller units; `route` again continues with the open nets (c0108).
- **Groups lose the per-net isolation of today.** A tool failure now leaves a whole group open. Mitigation: the failed run's nets are named; `group-nets=1` gives back one net per run.
- **Left-out nets lose their clearance class in Freerouting.** Mitigation: `H-G-DSN-NETLESS` and its fallback (Decision 4); KiCad's DRC judges every route.
- **`--escalation off` leaves nets open that the default would close** (7 of 101 on the bench). Those nets are reported, and a second pass or the other router can take them; the default closed them with 245 size errors that the user would have to remove by hand. `--router-option escalation=board` still reaches the tool and replaces `off`.
- **Until staged plans exist (the later part of c0120), a dry run and a confirm run each spend the budget** and may keep different runs. The receipt states what was written.
- **Machine load.** The measured times varied threefold with load; budgets are wall-clock. The record states the load.

## Migration Plan

- `--timeout` of `route` with KiCadRoutingTools bounds the job, not each net; a script that passed 600 for 600 s per net now gets 600 s in all. `CHANGELOG.md` says so.
- Freerouting runs without its optimizer unless `optimize=on`: routes may hold more vias and detours than a run that reached the optimizer's end, which no run of the plugin did on the bench.
- Reaching the budget gives `route.budget-exhausted` (warning) instead of `route.tool-failed` (error); exit 0 instead of 5.
- No file format and no model change: a model document is read by 0.2.x and 0.3.x as before. Reverting removes the new fields, which have defaults.
- The release acceptance loop (`tests/_acceptloop.py`, `tests/routing/test_acceptance_loop.py`) routes with `freerouting` and passes `--timeout`: with the optimizer off and the other nets netless its routed board changes. Task 7.1 runs it as the proof of the two defaults.

## Budget (7 days)

| part | days |
|---|---|
| registers, the netless and group probes, the measured record | 0.75 |
| protocol fields, `budget.py`, codes | 0.5 |
| `route`: `--timeout` as budget, `--order`, result keys | 0.75 |
| KiCadRoutingTools: groups, tiers, budget, `group-nets`, escalation, fake modes | 1.25 |
| design file: netless other nets | 0.5 |
| Freerouting: netless nets, optimizer switch, budget, tiers, `optimize=on` | 1.25 |
| oracle tests on both majors | 1.0 |
| documentation and closing | 1.0 |

Cut order: (1) `optimize=on`; (2) tiers in Freerouting, where `--order` then gives `route.order-ignored` (info); (3) `group-nets`; (4) `--order`. Never cut: the budget and the kept runs, the groups, the netless nets and the optimizer switch.

## Open Questions

- **The default budget.** Default: 900 s for both external routers. The yardstick of c0119 will say whether that is enough for 300 parts.
- **Escalation.** Default: `off`. `board` would allow sizes down to the board minimums, which KiCad's DRC accepts; the maintainer may prefer it.
- **`optimize=on`.** On the bench the optimizer ran over 640 s without an end. Default: offered, first in the cut order.
- **Left-out nets wider than the default rule.** Default: left out until `H-G-DSN-NETLESS` says otherwise; then the fallback of Decision 4.
- **Tiers for Freerouting.** Each tier is a full run, with its fanout. Default: tiers apply to both routers.
