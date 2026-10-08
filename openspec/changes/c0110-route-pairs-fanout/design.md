## Context

**Scope.** Milestone v0.4 (`docs/roadmap.md`, "v0.4: proposals on other branches", row c0110 `route-pairs-fanout`; called v0.2c until c0136 renamed the milestones on 2026-10-07), from the review of 2026-10-05: differential pairs in the routing protocol and in the Specctra file; escape of QFN and BGA parts; time-boxed behind a feasibility gate, as c0016 was. It depends on c0104 (the pair name rule `model.pairs`, the class pair values, the pair rule kinds) and on c0107 (plane layers, `JobNet.layers`, the plane fan-out, the project's rules in `route`). Bordering rows: c0105 (impedance widths, which routers take from class values), c0106 (meanders on script copper), c0108 (open-connection selection), c0109 (process, time and order control of the plugins), c0111 and c0112 (via-in-pad).

**What exists** (checked on `origin/dev` at `9aba2dff`, 2026-10-07; `routing/pairs.py`, `routing/escape.py` and `model/pairs.py` do not exist there, and `capabilities` lists no router feature):

| place | fact |
|---|---|
| `routing/protocol.py:31-57` | `JobNet` holds width, clearance and via sizes; `RoutingJob` holds `design`, `nets`, `layers`, `options`, `extra`; no pair and no part |
| `routing/select.py:22-36` | a net with any track, arc or via, or with a zone, is not a candidate |
| `cli/cmd_route.py:219-239`, `:269-270` | one `JobNet` per candidate from its class; `extra` holds `board_pads` and `outline` |
| `routing/plugins/kicad/routingtools.py:113-135` | one `route.py` process per net, `--nets <name>` with width, clearance and via flags; every router option is appended as `--key value`, unchecked |
| `routing/plugins/specctra/freerouting.py:208-228`, `:262-274` | the command line holds no fanout or neck-down setting; `max-passes` is the only option |
| `backends/specctra/dsn.py:424-445` | the network section holds nets and classes only |
| `lens/build.py:459-470` | pairs are known by name (`is_pair`, `pair_hint`); c0104 moves the rule to `model.pairs` |
| `cli/cmd_capabilities.py:105-121` | the reply holds `matrix` (the backend matrix) beside `routers`; a router entry has no `features` |
| `lens/altium.py:79` | an Altium build keeps a pair interface in the model and names it in one `altium.not-lowered` info; nothing of this change reaches that build |

**Sources read on 2026-10-05.** KiCadRoutingTools at tag `v0.22.1` (S-0215, S-0216): the README and `docs/differential-pairs.md` (S-0662) and `docs/utilities.md` (S-0663) describe `route_diff.py`, `bga_fanout.py` and `qfn_fanout.py`, to run before `route.py`; the `--help` of the four scripts, printed by the checkout that c0016 installed outside the repository (commit `023d3f79`), names their options: `--diff-pair-gap`, `--no-gnd-vias`, `--polarity-swap-nets` (no swap when omitted), `--diff-pair-intra-match`, `--length-match-tolerance`, `--keep-input-copper`, `--same-net-pad-clearance`, `--escalation {off,board,fab}` (default `fab`: sizes may drop below the board's own minimums), `--no-fix-drc-settings` (by default the written project's floors are loosened), `--plane-drop` and `--grid-step`, which the escape scripts and `route.py` must share. Freerouting at tag `v2.4.1` (S-0222): `router.fanout.enabled` (default true) and `router.automatic_neckdown` (default true), given as `--<key>=<value>`; no setting names a pair. Freerouting's issue 358 (S-0664): a request for pair routing that quotes the `(pair (nets P N))` form; the maintainer answered on 2024-10-17 that nobody would implement it soon, and a bot closed it as stale. The Specctra reference (S-0224), read on line under ADR-0006: a `pair` list in the network section names two nets. No source code of either tool, of KiCad or of Freerouting was read.

**Measured on 2026-10-05.** Benches authored for this change with the DSL as it was on 2026-10-05 (commit `7203e4b6`), built for target 10 (and the pair bench for target 9), 4 copper layers:
- *pair bench*: 50 mm × 30 mm, two 1×08 headers of 1.27 mm pitch 40 mm apart; pairs `USB_P`/`USB_N` and `LV0_P`/`LV0_N` and four single nets cross between them; class `DP` 0.2 mm width, 0.15 mm clearance;
- *name bench*: two 1×10 headers 30 mm apart, five pairs `A_P`/`A_N`, `B+`/`B-`, `C_P0`/`C_N0`, `DP1`/`DN1`, `E_DP`/`E_DN`, all of which KiCad pairs (c0104, measurement 4);
- *QFN bench*: 50 mm × 40 mm, a QFN-48 of 0.5 mm pitch (exposed pad on GND) and a 2×20 header of 1.27 mm pitch; 40 signal nets from all four sides; GND and VCC zones on In1.Cu and In2.Cu; class 0.15 mm width and clearance, 0.5/0.25 mm via;
- *BGA bench*: 60 mm × 50 mm, a BGA-121 of 0.8 mm pitch (0.35 mm pads) and two 2×25 headers; the 96 balls of the three outer rings are signals, the inner 25 GND and VCC; class 0.1 mm width and clearance, 0.4/0.2 mm via.

Freerouting 2.4.1 (OpenJDK 26.0.2) ran as `java -jar <jar> -de board.dsn -do board.ses -mp 20 -mt 1 -da --gui.enabled=false [setting]` on files written by the `write_dsn` of that day, edited per variant; KiCadRoutingTools v0.22.1 ran as `<venv python> py_router/<script>.py …` on a copy of the built project, each step reading the board of the step before; the copper whose uuid the input lacked, on the selected nets, was merged with `routing.merge.apply` and judged by `kicad-cli pcb drc --format json --severity-all --refill-zones -o drc.json <board>` (10.0.6), and by `docker run --rm --platform linux/amd64 -v <folder>:/p -w /p -e HOME=/tmp kicad/kicad:9.0.9@sha256:e638b79b… kicad-cli pcb drc --format json --severity-all -o drc.json <board>` where 9.0.9 is named. Pair rules were appended to the rules file: `diff_pair_gap` 0.13 mm to 0.17 mm, `diff_pair_uncoupled` max 6 mm (3 mm in measurement 2), and `skew` max 0.1 mm with `(within_diff_pairs)`, all on `A.inDiffPair('*')`.

1. *Pairs through Freerouting.* The same 8 nets routed in 7 s with no `pair` list (p00), with `(pair (nets P N))` per pair (p01), and with a `(rule (width 200) (clearance 150))` inside each list (p02): the three sessions' `routes` sections are byte-identical, and the log names no list. The pairs were routed as single nets: `USB_P`/`USB_N` parallel 1.07 mm apart over 34.9 mm, `LV0_P`/`LV0_N` with no parallel run within 2 mm; 0 unconnected items.
2. *How KiCad counts coupling*, on the routed board of p00 (two pairs, 42.3 mm and 43.2 mm long), identical on 10.0.6 and 9.0.9:

   | rules file | `diff_pair_gap_out_of_range` | `diff_pair_uncoupled_length_too_long` |
   |---|---|---|
   | gap rule only | 4 | 0 |
   | uncoupled rule (3 mm) only | 0 | 1, on `LV0`: "actual 18.396 mm" |
   | both | 8 | 2, "actual 42.334 mm" and "actual 43.156 mm" |
   | neither | 0 | 0 |

   With a gap rule, every segment outside its range counts as uncoupled; without one, parallel segments far apart count as coupled (c0104, row UC). A pair is judged only with both rules.
3. *Pairs through KiCadRoutingTools* (`route_diff.py --nets <the four pair nets> --track-width 0.2 --diff-pair-gap 0.15 --clearance 0.15 --via-size 0.6 --via-drill 0.3 --layers F.Cu In1.Cu In2.Cu B.Cu --no-gnd-vias --keep-input-copper --same-net-pad-clearance 0.15 --escalation off --no-fix-drc-settings`, then `route.py` for the four single nets), 10.0.6:

   | run | coupled at 0.15 mm (USB / LV0) | skew (USB / LV0) | DRC |
   |---|---|---|---|
   | k00 | 96.2 % / 97.1 % | 0.084 / 2.303 mm | 0 unconnected; no gap or uncoupled finding; 1 `skew_out_of_range` (LV0); 24 `track_width` |
   | k01, `--diff-pair-intra-match --length-match-tolerance 0.1` | 96.2 % / 92.6 % | 0.084 / 0.621 mm; the tool reports "meanders-ran-out" for LV0 | as k00, 37 `track_width` |
   | k02, width 0.25 mm, gap 0.2 mm, pairs only | 94.4 % / 94.8 % at 0.2 mm | 0.062 / 2.970 mm | no gap, uncoupled or width finding |
   | k04, as k01 on the target-9 bench, judged by 9.0.9 | as k01 | as k01 | as k01: the same lengths and findings |

   No via was used. The `track_width` findings are pair legs of 0.1996 mm under the template's board minimum of 0.2 mm: with 0.2/0.15 mm the tool writes legs 0.4 µm narrower than asked, with 0.25/0.2 mm exactly 0.25 mm. Single nets of `route.py` are 0.2 mm exactly. The gate's pair bench therefore sets a board minimum width of 0.15 mm, below its pair width.
4. *Names* (k03, 0.25/0.2 mm): `A_P`/`A_N`, `B+`/`B-`, `C_P0`/`C_N0` and `E_DP`/`E_DN` routed coupled at 0.2 mm (95.4 % to 95.6 %); `DP1`/`DN1` was not taken as a pair ("Found 4 differential pair(s)") and got no copper, with no failure listed.
5. *QFN bench* (signal nets only; GND and VCC are zone nets and stay open without c0107's fan-out):

   | run | router | open signal connections | wall | DRC errors on routed copper |
   |---|---|---|---|---|
   | e12 | Freerouting, every layer a signal layer | 0 | 391 s | 5 `track_width`: tracks of 0.1124 mm under the 0.15 mm minimum, at pins |
   | e30 | Freerouting, In1.Cu and In2.Cu `(type power)` | 0 | 562 s | none |
   | e31 | as e30, `--router.automatic_neckdown=false` | 0 | 798 s | none |
   | e14 | as e12, `--router.automatic_neckdown=false` | 0 | 415 s | 3 `track_width`: two wires of 0.1124 mm remain |
   | e15 | as e12, `--router.fanout.enabled=false` | 0 | 598 s | none; the autorouter's neck-down narrowed 0.3 mm power wires to 0.2598 mm |
   | e16 | as e12, fanout stage and neck-down off | 0 | 659 s | none; no wire narrower than its class |
   | e17 | as e30, fanout stage and neck-down off | 2, after the 20 passes of the plugin's default | 66 s | none; no wire narrower than its class |
   | k10 | `qfn_fanout.py` (40 of 40 pins escaped in 1.7 s, surface stubs, no via), then `route.py` on F.Cu and B.Cu | 2 (`Q04`, `Q33`) | 99 s | none (5 `track_dangling` warnings) |
   | k11 | `route.py` alone | 5 | 150 s | none |

   Freerouting's fanout stage escaped 82 of 89 SMD pins with four signal layers and 5 of 89 with two; its autorouter closed the rest. The 0.1124 mm wires come from the fanout stage: they stay with neck-down off (e14) and vanish with the stage off (e15, e16); neck-down narrows only at pins the autorouter reaches (e15).
6. *BGA bench*:

   | run | router | open signal connections | wall | DRC errors on routed copper |
   |---|---|---|---|---|
   | e40 | Freerouting, inner layers `power` | no session within 900 s: the fanout stage took 390 s and escaped 19 of 217 pins; pass 1 took 457 s and left 51 unrouted | 900 s | — |
   | e41 | as e40, neck-down off | no session within 900 s (fanout 374 s, 20 of 217; 48 unrouted after pass 1) | 900 s | — |
   | e42 | as e41, `--router.fanout.enabled=false --router.optimizer.enabled=false`, 1800 s | no session within 1800 s; pass 17, ending at about 1780 s, left 7 unrouted | 1800 s | — |
   | k20 | `bga_fanout.py`, default method (96 of 96 balls escaped in 7.5 s; 48 of its vias sit at the centre of their own ball, in the pad, although `--same-net-pad-clearance 0.1` was given), then `route.py` | 10 | 744 s | 191 `hole_clearance` under the template's board-setup hole clearance of 0.25 mm; none with a board-wide `hole_clearance` rule of 0.15 mm |
   | k21 | `route.py` alone | 96: no output within 900 s | 900 s | — |
   | k22 | `bga_fanout.py --escape-method dogbone` (96 of 96 escaped in 3.6 s, 24 vias, every one in a gap between balls), then `route.py` | 7 | 168 s | as k20: 149 `hole_clearance` under 0.25 mm, none under 0.15 mm (20 `track_dangling`, 3 `via_dangling` warnings) |

   With 0.1 mm copper clearance and a 0.4/0.2 mm via, a track passes 0.2 mm from a via's hole; the template's 0.25 mm hole clearance, which neither tool is given by Fenolite, cannot hold on such a board. The gate's BGA bench therefore carries a `hole_clearance` rule of 0.15 mm (c0071), as a board with this BGA would.
7. A first batch of Freerouting runs was stopped from outside the probe after 510 s to 520 s without a session; the runs above were made again. None of these probes is committed; each becomes a recorded probe or test of this change. Scripts, command lines and outputs are kept in the change's probe folder.

**What the measurements decide.** Freerouting 2.4.1 cannot route a pair, and writing the pair list changes nothing (1). KiCadRoutingTools routes pairs coupled at the class gap, through its own pair script, with two limits: names it does not pair, and skew its matching leaves (3, 4). A pair is judged by KiCad only with a gap rule beside the uncoupled rule (2). On the QFN bench Freerouting completes and KiCadRoutingTools needs its escape script to come close; on the BGA bench only KiCadRoutingTools with its escape script makes progress, and its default method puts vias in pads (5, 6). Freerouting's fanout stage, on by default, makes wires that KiCad rejects when inner layers are signal layers, closes connections that stay open without it when they are planes, and its automatic neck-down narrows wires at pins (5).

## Goals / Non-Goals

**Goals:**
- A pair of a board is routed coupled at its class gap by a router that can, and is never routed uncoupled without the user asking.
- Fine-pitch parts are escaped before routing where the router offers it, at the job's sizes and nothing smaller.
- What each tool does with pairs and fine pitch is measured on authored benches, on both majors, before the code that relies on it is written.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- A router of Fenolite's own, for pairs or for escape: nowhere, because routers are plugins (plan D11).

## Decisions

1. **The feasibility gate comes first** (task group 1, after the registers; 2.5 of the 8 days). A script that uses only `fenolite build`, `write_board`, `read_board`, `write_dsn`, `read_session`, `routing.merge.apply`, `subprocess` and `kicad-cli`, no plugin code, runs the pinned tools on four benches authored for Fenolite (`tests/routing/_pairbench.py`, `_namebench.py`, `_escapebench.py`: the pair, name, QFN and BGA benches of Context), built for targets 9 and 10, and records what follows. The pair bench carries c0104's gap, uncoupled and skew rules (Decision 11) and a board minimum width of 0.15 mm, below its pair width (measurement 3); the QFN and BGA benches have c0107's plane layers and fan-out, and the BGA bench a `hole_clearance` rule of 0.15 mm (measurement 6). The outcomes:
   - `krt-pair-t9`, `krt-pair-t10` (`H-K-KRT-PAIR`): the steps of Decision 6 on the pair bench, then `route.py` for the single nets; `equal` when the board's major reports no unconnected item, no `diff_pair_gap_out_of_range`, no `diff_pair_uncoupled_length_too_long`, and no other type of severity error that the unrouted bench lacks; `skew_out_of_range` is recorded with its values and gates nothing (measurement 3).
   - `krt-pair-names` (`H-K-KRT-PAIRNAMES`): the name forms routed coupled.
   - `krt-escape-<bench>-t<M>` and `dsn-escape-<bench>-t<M>` (`H-K-KRT-ESCAPE`, `H-G-DSN-FANOUT`): open signal connections, new error types, vias inside pads and wall time, with and without the escape, at most 900 s per run: `equal` (none open), `improved` (fewer open than without the escape), each with no new error type and no via inside a pad, or `different`.
   - `dsn-pair-ignored` (`H-G-DSN-PAIR`), `dsn-narrow-fanout` and `dsn-narrow-off` (`H-G-DSN-NARROW`).
   - **Verdict.** Pairs pass when both `krt-pair-t<M>` are `equal`. Escape passes for KiCadRoutingTools when its four escape outcomes are `equal` or `improved`.
   - **What still lands when a part fails.** If pairs fail: `JobPair`, `job_pairs`, `route.pair-skipped` and `--pairs-as-nets` still land, so no router routes a pair uncoupled unasked; KiCadRoutingTools declares no `pairs`, the requirement "KiCadRoutingTools routes pairs" is removed from this change, the register row is refuted with the open connections or violations, and a pair is routed by script copper (c0068's tracks and arcs, c0111's anchors). If escape fails: "KiCadRoutingTools escapes parts" is removed and `--escape` is not added; Freerouting's settings of Decision 10 still land; fan-out stays with c0107's engine and c0111. The benches stay as recorded probes for the next pin of either tool.
   - **Time box.** At day 3 the verdict is written into `docs/evidence/routing.md` and the roadmap; the budget of a step that is not built is returned.
   - The outcomes go to `docs/evidence/routing.md` and the tools' result files (`routing/freerouting-2.4.1.json`, `routing/krt-v0.22.1.json`), never to `docs/evidence/kicad/probes/`, which stay reproducible with `kicad-cli` alone; the coupling probe of Decision 11 is such a `kicad-cli` probe.
   - Rejected: building the plugin steps first and probing after (c0023 did, and its facts stayed `INFERRED` until the probes ran). Rejected: the blink as the gate board: it has no pair and no fine-pitch part.

2. **A pair in the routing job.** `JobPair(name, positive, negative, width, gap, via_gap=None, skew_max=None)` and `RoutingJob.pairs`; `positive` and `negative` name nets that stay in `job.nets`, so a router that takes pairs finds their pads and class values there, and the merge, the lift and `route.unrouted` work per net as before. The width, gap and via gap are the class pair values of c0104, which KiCad's own router reads; `skew_max` is the `max` of the `diff_pair_skew` rule that governs the pair, so a router that matches skew matches to the user's limit.
   - Rejected: a pair entity in the model. c0104 decided that a pair is an interface known by its names.
   - Rejected: the router's own defaults (KiCadRoutingTools reads the `Default` class's pair values, else 0.101 mm): a gap nobody chose.
   - Rejected: per-layer widths from c0105's targets. The tool takes one width per pair; c0105 warns when a class value differs from a target's row.

3. **Which nets form a pair: KiCad's names, both selected, one class.** `routing.pairs.job_pairs` pairs two candidates when c0104's `pair_base` does, as KiCad's DRC (`inDiffPair`) and router do. `route` reads KiCad's files, not `.fenolite/`, as c0107 decided for planes, and c0104's build already warns when a declared pair's names do not pair. A pair is routed as a pair only when both nets are candidates and share a class; otherwise its selected net is left out with `route.pair-skipped`, because half a pair routed alone is uncoupled copper that blocks the other half.
   - Rejected: pairs from the interfaces of `.fenolite/`. A board not built by Fenolite has none, and a pair renamed in KiCad would go unseen.
   - Rejected: routing the selected half as a single net (the copper would have to be ripped to couple the pair).

4. **Routers declare features.** `ROUTER_FEATURES = {"pairs", "escape"}`; a router lists what it takes in a `features` attribute, read by `router_features(router)`, which gives an empty set without it. The command removes from the job what the router cannot take, so no plugin receives a pair it would route as two nets.
   - Rejected: a `features` member of the `Router` protocol: every third-party router would stop type-checking.
   - Rejected: plugins that receive pairs and ignore them.

5. **Pairs and a router without the feature: left out, unless asked.** The nets of each pair are removed from the job with `route.pair-skipped` (warning, hint: `--pairs-as-nets`, or a router with `pairs`). `--pairs-as-nets` forms no pair; the nets go to the router as single nets, each pair with `route.pair-uncoupled` (info). Measurement 1 shows what Freerouting makes of a pair; measurement 2 shows KiCad rejecting it.
   - Rejected: routing them as single nets by default with a warning. The copper is wrong for a pair, and once a net has copper `route` does not select it again until c0108 or `--rip`.

6. **KiCadRoutingTools pair steps.** In the run folder, after the escape steps and before the single nets, one `route_diff.py` process per pair with the arguments of "KiCadRoutingTools routes pairs": the job's sizes, `--layers` from the net's layers (c0107) without plane layers, `--no-gnd-vias`, `--keep-input-copper`, `--same-net-pad-clearance` at the clearance (which asks for no via in a pad; the gate counts them, Decision 9), `--escalation off` (sizes exact: a pair that cannot be routed at them fails visibly), `--no-fix-drc-settings` (the project file of the run stays Fenolite's), and intra-pair matching to `skew_max` when set.
   - **Names.** `PAIR_NAME_FORMS` holds the forms recorded by `krt-pair-names`; on measurement 4 they are a polarity `+`/`-` with no tail, `P`/`N` after `_` with a tail of digits or none, and the base ending in `_D` (`X_DP`/`X_DN`). Other pairs give `route.pair-skipped`, because the tool skips them silently.
   - **Never passed:** `--polarity-swap-nets` (a swap changes the netlist), `--impedance` (c0105 owns impedance, and the tool would choose the width), `--rip-existing-nets`, `--force-reroute`; given through `--router-option` they give `route.option-ignored`.
   - **Ground vias** are off: the lift keeps copper of the job's nets only, and a via on GND beside a pair via would be dropped half-made.
   - **One process per pair**, each a run of c0109's job budget (Decision 14): it gets the time left, is listed in `runs`, and keeps its copper when it ends in time.
   - Rejected: one `route_diff.py` process for every pair. A failed pair then fails the run's output for all; per pair, an output exists for each.
   - Rejected: restoring the 0.4 µm of measurement 3. Widening a leg narrows the gap inside the pair below the class clearance, which KiCad reports; the width guard (Decision 10) reports it instead.

7. **Freerouting: no pairs, no pair list.** The plugin declares no feature. `write_dsn` writes no `pair` list: Freerouting 2.4.1 routes the same with it (measurement 1), and a reader of the file would take the pair for routed coupled. `docs/formats/specctra/dsn.md` records the list as a fact of S-0224 with `H-G-DSN-PAIR`, and the gate runs the probe on every new pin.
   - Rejected: writing the list for other Specctra readers. Fenolite runs one.
   - Rejected: routing a pair as one wide net and splitting it after the session. That is a pair router of Fenolite's own (plan D11).

8. **Escape requests are explicit.** `fenolite route --escape REF[=grid|perimeter]`, repeatable, `REF` a glob over references. `routing.escape.escape_kind` tells a grid of pads (some pad has neighbours at the part's pitch on two orthogonal axes, both ways) from a perimeter (QFN, QFP, SOIC), from the centres of the part's pads without a drill, turned or not; the suffix overrides it. A request names the job nets on the part.
   - The QFN bench stands for perimeter parts, QFN and QFP alike, which the same script serves (S-0663).
   - Rejected: escaping every fine-pitch part automatically. Escape stubs fix the path out of a part before routing; a part the router escapes well by itself (measurement 5, Freerouting) would get worse routes, and a pitch threshold would be a shipped value.
   - Rejected: KiCad's `pad_prop_bga` pad property as the test. The board reader keeps it opaque, and authored footprints do not set it.

9. **KiCadRoutingTools escape steps.** Before every pair and net step, one process per request: `bga_fanout.py --escape-method dogbone` for a grid, `qfn_fanout.py` (surface stubs, its default) for a perimeter, with the arguments of "KiCadRoutingTools escapes parts": the request's nets, the smallest width and via and the largest clearance among them, `--plane-drop off` (c0107's fan-out makes plane vias), `--same-net-pad-clearance` at the clearance, `--escalation off`, `--no-fix-drc-settings`, and the pairs on a BGA through `--diff-pairs`. The grid step, when the router option `grid-step` is given, goes to the escape steps and to `route.py` alike, as the tool's help asks. Escape copper is lifted with the nets it belongs to; a net escaped but not routed keeps its stubs and stays in `unrouted`, so c0108's second pass can complete it.
   - **Dog-bones, not vias in pads.** The default method put 48 vias in their own balls on the BGA bench although the pad clearance forbade it (measurement 6, k20); a via in a pad needs a filled and capped via, which c0112 owns. `dogbone` placed all 24 of its vias between balls (k22). The gate counts vias inside pads, and an escape outcome with one is not `equal` or `improved`.
   - Rejected: one escape for all parts in one process. The scripts take one component each.
   - Rejected: Fenolite's own dog-bones (c0107's `plan_fanout` applied to signal pads) in this change. It needs c0108's selection to finish nets that hold copper; it is the fallback named by Decision 1 if the escape gate fails.

10. **Freerouting at fine pitch, and the width guard.** The plugin always passes `--router.automatic_neckdown=false`, and passes `--router.fanout.enabled=false` when the router option `fanout=off` is given; the fanout stage stays on by default, as today and as c0107 assumes. Measurement 5: with four signal layers the stage wrote wires of 0.1124 mm under a 0.15 mm class at QFN pins, which KiCad reports, with neck-down on or off (e12, e14), and without the stage none (e15, e16); with plane layers, the configuration of c0107 and of the yardstick, the stage escaped 4 or 5 pins, wrote no narrow wire and closed every connection (e30, e31), while without it 2 stayed open after the plugin's 20 passes (e17); neck-down alone narrowed 0.3 mm wires at pins (e15). In `route`, a routed track or arc narrower than its job width gives `route.width-below-job` (warning) per net, whatever the router, and its hint for Freerouting names `fanout=off`: measurement 3 found 0.4 µm legs, and the stage or a later pin may make more.
    - The gate records the escape outcomes with the stage on and off (Decision 1); if `fanout=off` is better on both benches and both majors, task 1.6 makes it the default.
    - Rejected: the stage off by default. On the bench with plane layers it left 2 connections open that the stage closed (e17 against e30).
    - Rejected: the stage always on, with no option. Its narrow wires on boards with inner signal layers fail KiCad's DRC, and the user needs a way out.
    - Rejected: neck-down kept, with c0103's area rules as the place to allow it. c0107 does not send area rules to Freerouting, so nothing would bound it.
    - Rejected: refusing narrower copper. The DRC is the judge, and a 0.4 µm shortfall is clean on a board whose minimum is below the class width.

11. **The judge of a pair needs both rules.** Measurement 2: KiCad counts as uncoupled what lies outside a gap rule's range; without a gap rule, `USB_P`/`USB_N`, parallel 1.07 mm apart over 34.9 mm of its 42.3 mm, got no uncoupled finding at a 3 mm limit, and `LV0_P`/`LV0_N` only 18.4 mm of its 43.2 mm. The gate benches therefore carry both rules, and `docs/routing.md` tells users to give `pair(gap_min=…, gap_max=…, uncoupled_max=…)` together (c0104). The fact becomes `H-K-DRU-PAIRCOUPLE`, a `kicad-cli` probe on an authored bench of script copper, so it can be re-run without a router.
    - Rejected: leaving it to c0104. Its rows measured each kind alone; the combination decides how this change's gate judges.

12. **Replies and codes.** `result.pairs` lists `{name, positive, negative, width, gap, routed}` and `result.escape` lists `{ref, kind, pitch, nets}`; `result.selected` names every net given to the router. New codes in `routing.codes.ISSUE_CODES`:

    | code | severity | when |
    |---|---|---|
    | `route.pair-skipped` | warning | a pair left out: no router feature, one net selected, two classes, no pair width or gap, a name form the tool does not pair |
    | `route.pair-uncoupled` | info | `--pairs-as-nets` routed a pair as two single nets |
    | `route.escape-skipped` | warning | an `--escape` pattern matched no part, the part has no job net, or the router has no `escape` |
    | `route.width-below-job` | warning | routed copper narrower than its job width |

    None changes the exit code. `capabilities` lists each router's `features`.
    - Rejected: one code per reason a pair is skipped. The remedies differ only in the hint, which names the reason and the way out.

13. **Order of a `route` run.** c0107's plane fan-out (merged before the job) → candidates (c0108's selection by open connections) → `job_pairs` → feature check → escape requests → the router: escape steps, pair steps, single nets (KiCadRoutingTools); one run (Freerouting) → merge → width guard → write.
    - Rejected: pairs before the escape. A pair that leaves a BGA leaves through the escape (`--diff-pairs`), and the pair step starts from its stubs.
    - Rejected: single nets before pairs. Pairs need the most room; routed last, they find the channels taken.

14. **Order with other changes** (checked on `origin/dev` at `9aba2dff`, 2026-10-07; task 0.1 checks again). One living requirement is modified, "Freerouting plugin"; every other requirement here is ADDED, and none of the names exists on `dev`.
    - **"Freerouting plugin"** is touched by three proposals of v0.4 in a fixed order (review of 2026-10-07, item 14): c0078 (the jar's location), c0109 (budget, tiers, optimizer, netless nets), then this change (neck-down always off, the option `fanout`). The first draft added a requirement beside the living one, which said "the only router option is `max-passes=N`" and fixed the command line: two texts that disagreed. It is now a MODIFIED delta. No open change on `dev` holds a delta of the requirement and neither c0078 nor c0109 is on `dev` at `9aba2dff`, so the delta is generated from the living text with only this change's two edits; task 0.1 regenerates it from the text c0109 leaves (its options `max-passes` and `optimize`, its Tiers and Optimizer bullets, `others="netless"`) and re-applies the two edits.
    - c0104 and c0107 are archived first: `model.pairs`, the class pair values and `diff_pair_skew`; `RoutingJob.plane_layers`, `JobNet.layers`, `design_rules` in `route`. `pairs` and `escape` come after the fields of c0107 and c0109 in `RoutingJob`.
    - c0108 is archived first: its selection gives the candidates, and a pair counts as selected when both nets are; an escaped net left open is completed by its second pass.
    - c0109 is archived first: its process groups replace one `route.py` per net and already pass `--escalation off` and `--no-fix-drc-settings`; the escape steps run before the first tier and the pair steps of a tier before its groups, all inside its job budget, and its result keeps the copper of finished steps. The two KiCadRoutingTools requirements of this change point at "Routing time budget" and "Routing tiers".
    - The second backend: no rule kind, selector, model field or document content is added, so no row of the Altium rule table and no Altium requirement changes. Pairs in an Altium build are c0104's.
    - Two meanings of "fan-out" meet here: c0107's plane fan-out (Fenolite's vias from SMD pads to planes, `kicad.fanout.*`, `--no-plane-fanout`) and Freerouting's fanout stage (the router option `fanout=on|off`, `H-G-DSN-FANOUT`). `docs/routing.md` tells them apart in one paragraph; "escape" is this change's word for the per-part step.
    - c0106 measures the skew this change's routes leave; meanders on router copper are not taken (proposal).

## Files and public API

| file | content |
|---|---|
| `src/fenolite/routing/protocol.py` | `JobPair`, `JobEscape`, `RoutingJob.pairs`, `RoutingJob.escape`, `ROUTER_FEATURES`, `router_features(router)` |
| `src/fenolite/routing/pairs.py` (new) | `job_pairs(design, candidates) -> (pairs, singles, issues)` |
| `src/fenolite/routing/escape.py` (new) | `escape_kind(points) -> str`, `pitch(points) -> Nm`, `requests(parts, patterns, nets) -> (requests, issues)` |
| `src/fenolite/routing/codes.py`, `src/fenolite/cli/data/explain.toml` | the four codes, each with its `explain` entry |
| `src/fenolite/routing/plugins/kicad/routingtools.py` | `features`, `PAIR_NAME_FORMS`, `REFUSED_OPTIONS`, the escape and pair steps |
| `src/fenolite/routing/plugins/specctra/freerouting.py` | `features = frozenset()`; `--router.automatic_neckdown=false`; `--router.fanout.enabled=false` for `fanout=off` |
| `src/fenolite/cli/cmd_route.py` | `--escape`, `--pairs-as-nets`, the pair and escape stages, the width guard, `result.pairs`, `result.escape` |
| `src/fenolite/cli/cmd_capabilities.py` | `features` per router |
| `tests/routing/_pairbench.py`, `_namebench.py`, `_escapebench.py` (new) | the authored benches |
| `tests/routing/test_pair_gate.py`, `test_escape_gate.py` (new) | the gate and the oracle loop (`needs_router`, `needs_freerouting`, `needs_kicad`) |
| `tests/kicad/rules/test_pair_coupling.py` (new) | `dru-pair-couple-<case>` |
| `tests/unit/routing/test_pairs.py`, `test_escape.py` (new); `test_protocol.py`, `test_routingtools.py`, `test_freerouting.py`; `tests/unit/backends/specctra/test_dsn.py`; `tests/unit/cli/test_route_cmd.py`, `test_capabilities.py`; `tests/_fakerouter.py` | hermetic |
| `tests/data/kicad/routing/pair_two_headers.kicad_pcb` (new, authored) | the command's pair scenarios |
| `docs/routing.md`, `docs/cli-contract.md`, `docs/formats/specctra/dsn.md`, `docs/evidence/routing.md`, `docs/evidence/routing/krt-v0.22.1.json` | pairs, escape, features, forms, limits; outcomes |

Layering: `routing` imports `core`, `model` and `geometry` (`model.pairs` for the name rule); `cmd_route` turns `BoardPad`s into the plain pads that `requests` takes. No model or schema change, no new FEN code.

## Sources registered by this change

| id | source | licence | used for |
|---|---|---|---|
| S-0662 | https://github.com/drandyhaas/KiCadRoutingTools/blob/v0.22.1/docs/differential-pairs.md | MIT | what `route_diff.py` does: centre line and constant-gap legs, paired vias, ground vias, polarity swaps, intra-pair matching, stated limits |
| S-0663 | https://github.com/drandyhaas/KiCadRoutingTools/blob/v0.22.1/docs/utilities.md | MIT | `bga_fanout.py` and `qfn_fanout.py`, their options, to run before `route.py` |
| S-0664 | https://github.com/freerouting/freerouting/issues/358 | GitHub terms (facts only) | the `(pair (nets P N))` form quoted by a user, and the maintainer's answer that pair routing is not implemented |
| S-0665 | the `--help` text of `route_diff.py`, `bga_fanout.py`, `qfn_fanout.py` and `route.py` at tag `v0.22.1`, printed by running the scripts | MIT | the options passed by the plugin and their defaults |

S-0215, S-0216, S-0222 and S-0224 are used as registered. The four ids are of the block S-0660 to S-0679 given to this group on 2026-10-07 (S-0660 is c0107's, S-0661 is reserved by c0108); `docs/evidence/sources.md` ends at S-0601 on `9aba2dff`. The first draft named them S-0410 to S-0413, which `dev` has since given to catalog datasheets.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-KRT-PAIR | `route_diff.py` at the pinned tag, run as Decision 6 states, routes both pairs of the pair bench coupled at the class gap, and the board's major reports no unconnected item, no gap and no uncoupled-length finding under the bench's rules (S-0662, S-0665) | `tests/routing/test_pair_gate.py::test_krt_pair` | `krt-pair-t9` and `krt-pair-t10` `equal`; skew recorded |
| H-K-KRT-PAIRNAMES | `route_diff.py` pairs `X_P`/`X_N`, `X+`/`X-`, `X_P0`/`X_N0` and `X_DP`/`X_DN`, and not `XP1`/`XN1` (S-0662) | `test_pair_gate.py::test_krt_names` | `krt-pair-names` equals `PAIR_NAME_FORMS` |
| H-K-KRT-ESCAPE | `qfn_fanout.py`, or `bga_fanout.py --escape-method dogbone`, then `route.py`, leave fewer open signal connections on the QFN and BGA benches than `route.py` alone, add no error type and put no via in a pad, on both majors within 900 s (S-0663, S-0665) | `tests/routing/test_escape_gate.py -k krt` | the four `krt-escape-*` outcomes `equal` or `improved` |
| H-G-DSN-PAIR | Freerouting 2.4.1 writes the same routes for a design file with `pair` lists, with or without a rule inside, as without them (S-0224, S-0664) | `test_pair_gate.py::test_dsn_pair_ignored` | `dsn-pair-ignored` `equal` |
| H-G-DSN-NARROW | Freerouting 2.4.1's fanout stage writes wires narrower than their class at fine-pitch pins whatever `router.automatic_neckdown` holds; with the stage off and `--router.automatic_neckdown=false`, no wire is narrower than its class (S-0222) | `test_escape_gate.py -k narrow` | `dsn-narrow-fanout` `present` and `dsn-narrow-off` `absent` on the QFN bench with four signal layers |
| H-G-DSN-FANOUT | Freerouting 2.4.1 with neck-down off connects every signal pad of the QFN bench with plane layers within 900 s with its fanout stage, and leaves some open without it; it writes no session for the BGA bench within 900 s either way (S-0222) | `test_escape_gate.py -k dsn` | `dsn-escape-qfn-t<M>` `equal` with the stage; the other outcomes recorded |
| H-K-DRU-PAIRCOUPLE | KiCad counts as uncoupled every segment of a pair outside the range of the `diff_pair_gap` rule that governs it, and without one counts far parallel segments as coupled (S-0020, S-0029) | `tests/kicad/rules/test_pair_coupling.py` | `dru-pair-couple-<case>` as measurement 2, on 9.0.9 and 10.0.6 |

All start `INFERRED`, with the measurements of Context as their first record. Ids used without changing their level: `H-K-KRT-CLI`, `H-K-KRT-ROUTE`, `H-G-DSN-ACCEPT`, `H-G-DSN-PROTECT`, `H-G-DSN-INCOMPLETE`, `H-K-DIFFPAIR-NAMES-2`, `H-K-DRU-PAIR`, `H-G-DSN-LAYERS`, `H-K-FANOUT`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| pair routing through KiCadRoutingTools | KICAD-VERIFIED (9.0.x, 10.0.x) for the pinned tag | `krt-pair-t9`, `krt-pair-t10` |
| name forms sent to the tool | ORACLE-VERIFIED(kicadroutingtools v0.22.1) | `krt-pair-names` |
| escape steps | KICAD-VERIFIED (9.0.x, 10.0.x), `improved` at least | `krt-escape-*` |
| Freerouting: pair list ignored, narrow wires | ORACLE-VERIFIED(freerouting 2.4.1) | `dsn-pair-ignored`, `dsn-narrow-*` |
| Freerouting escape | recorded, KICAD-VERIFIED where `equal` | `dsn-escape-*` |
| coupling in KiCad's DRC | KICAD-VERIFIED (9.0.x, 10.0.x) | `dru-pair-couple-*` |
| protocol, pair selection, escape kind, command, width guard | mechanical | unit tests |
| a routed board | UNVERIFIED, as every route | — |

`routingtools.EVIDENCE` and `freerouting.EVIDENCE` gain the new hypothesis ids; a route stays `UNVERIFIED`.

## Risks / Trade-offs

- **Pairs left unrouted on boards routed today.** Nets named `X_P`/`X_N` routed by Freerouting now give `route.pair-skipped`. Mitigation: the hint names `--pairs-as-nets`; `CHANGELOG.md` says it.
- **Skew left by the tool** (0.62 mm on LV0 with matching). KiCad's DRC reports it under a `diff_pair_skew` rule, and c0106 measures it; a script meander on router copper is not available in v0.4.
- **The tool's name forms are narrower than KiCad's.** Pinned by `krt-pair-names`; a skipped pair is named with the form to use.
- **Undocumented tool behaviour at a new tag** (leg widths, silent skips). Each is a gate outcome; a new pin re-runs the gate before `PINNED_TAG` moves.
- **Escape stubs that `route.py` then fails to reach** (k10: two nets open with dangling stubs). The nets stay in `unrouted` with their stubs; KiCad warns `track_dangling`; c0108's second pass or `--rip` handles them.
- **Narrow wires from Freerouting's fanout stage** on boards whose inner layers carry signals (e12, e14). Mitigation: `route.width-below-job` names the nets with the hint `fanout=off`, KiCad's DRC reports them, and the gate may make `fanout=off` the default (Decision 10).
- **Long runs.** The QFN bench took 66 s to 798 s in Freerouting, and the BGA bench had 7 connections open after 1780 s; a 300-part board will take longer. Time control and partial results are c0109's.
- **External processes stopped.** A probe batch was stopped from outside (Context 7); the gate tests record the wall time and the exit of every run.

## Migration Plan

- Additive in the protocol: jobs and routers written before this change keep working; a router without `features` takes no pair and no escape.
- `route` behaviour changes for pair nets: they go only to a router that takes pairs, or with `--pairs-as-nets`. Freerouting's command line gains `--router.automatic_neckdown=false`, so its routes change where it narrowed wires; `fanout=off` is new.
- No file format and no model change: a model document is read by 0.2.x and 0.3.x as before. Rollback: drop the features; `--pairs-as-nets` becomes the only behaviour.

## Budget (8 days)

| part | days |
|---|---|
| entry check, registers, sources | 0.5 |
| benches authored and built for both targets | 0.75 |
| gate: pair and name runs, coupling probe, both majors, verdict | 1.0 |
| gate: escape runs with both tools, both majors | 0.75 |
| protocol, features, codes | 0.5 |
| `job_pairs`, `escape_kind`, `requests` | 0.75 |
| `route`: options, stages, width guard, replies, capabilities | 0.75 |
| KiCadRoutingTools pair steps and name forms | 0.75 |
| KiCadRoutingTools escape steps | 0.75 |
| Freerouting: fanout and neck-down settings, no pair list, fact row | 0.25 |
| oracle through the command on both majors | 0.75 |
| documentation and closing | 0.5 |

Cut order: (1) intra-pair matching (0.1; KiCad reports the skew); (2) the escape kind's override suffix (0.1); (3) the option `fanout=off` (0.1); (4) the escape steps for perimeter parts, when Freerouting's outcome for the QFN bench is `equal` (0.35); (5) the escape steps for grid parts (0.4). Never cut: the gate, `job_pairs` with `route.pair-skipped`, neck-down off, the width guard and the pair steps if their gate passes.

## Open Questions

- **Should ground vias beside pair vias be lifted as plane vias?** Default: no; `--no-gnd-vias` always, until a bench measures them against c0107's fan-out.
- **Should a pair whose net is half routed be completed?** Default: no; both nets must be candidates. c0108 may revisit it.
- **Should `--escape` accept a pitch or kind selector instead of references?** Default: references only (Decision 8).
- **Should the 0.4 µm legs be reported to the tool's maintainers?** Default: yes, as an issue citing the bench; it changes nothing here.
- **Should the fanout stage be off by default?** It made narrow wires with four signal layers (e12, e14) and none with plane layers, where turning it off left 2 connections open (e17). Default: on, as today; the gate decides (Decision 10).

## Implementation notes (2026-10-08, on `v04`)

Defaults taken while building the change on the integration branch, where no maintainer was asked:

- **Prerequisites stacked, not archived.** c0104, c0107, c0108 and c0109 are built on `v04` and not
  archived; the change is built on them as they are there (task 0.1).
- **The gate is not run here.** The machine of the implementation has neither `kicad-cli` nor the two
  routers, so tasks 1.2 to 1.6, 4.3, 6.1 and 8.2 stay open. Following Decision 1 ("What still lands when a
  part fails" and the verdict), `KicadRoutingToolsRouter.features` is empty until the verdict is written:
  the pair and escape steps are built and tested with fakes (`GATED_FEATURES` names them), and `route`
  gives every pair `route.pair-skipped` meanwhile. `PAIR_NAME_FORMS` holds the forms of measurement 4.
- **Hint without a router that routes pairs.** While no registered router lists `pairs`, the hint of
  `route.pair-skipped` names `--pairs-as-nets` and "kicadroutingtools, once its pair gate holds".
- **Coupling probes not registered.** `dru-pair-couple-<case>` are written (`_couplebench.couple_probes`)
  but not added to `_probes.PROBES`: an id there without its recorded outcome fails the probe-results test
  on every machine with `kicad-cli`. They are added with their outcomes when task 1.2 runs.
- **The pair board of the command** (`pair_two_headers`) is committed with its project file, since a
  KiCad board holds no net class and the pair values come from the project; its parts are one-pad rows of
  the test footprint library, not 1.27 mm headers, which the command's scenarios do not need.
- **Escape step layers and sizes.** A request's layers are those of its first net (its own set, else the
  job's routing layers); the pairs of a grid part go to `--diff-pairs` with the smallest gap among them. A
  part with fewer than two surface pads gives `route.escape-skipped` (no kind can be found).
- **Escape copper and the verdict.** An escape step's nets are not counted routed or unrouted by that
  step; the step that routes the net decides, so an escaped net that no later step routes stays in
  `unrouted` with its stubs.
- **`features` in the default view only** of `capabilities`; the brief view is unchanged.

