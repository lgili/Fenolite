## Context

**Scope.** Milestone v0.4 (`docs/roadmap.md`, "v0.4: proposals on other branches", row c0107 `route-planes-layers`; the group was called v0.2c until c0136 renamed the milestones on 2026-10-07). The gap, from the review of 2026-10-05: fan-out vias for pads of a net that has a plane; plane layers kept out of signal routing; routing layers per class; keep-outs, edge clearance and class-to-class clearance sent to the router. The review found these in no change and on no roadmap line. Bordering rows: c0108 (open-connection selection, locks), c0109 (process, time and order control of the plugins), c0110 (pairs, escape of QFN and BGA signal pads), c0111 (script copper in a part's frame), c0112 (via protection), c0103 (keep-outs and area rules from the script), c0105 (impedance widths, which it asks c0107 or c0110 to route at).

**What exists** (checked on `origin/dev` at `9aba2dff`, 2026-10-07; the routing package, `cmd_route.py` and `select.py` have not changed since the proposal was first written):

| place | fact |
|---|---|
| `routing/select.py:33-36` | `unrouted()` drops every net with a track, arc or via, and every net with a zone unless `include_zone_nets` |
| `cli/cmd_route.py:174-206`, `:269-276` | zone nets give `route.zone-net-skipped`; the job carries `board_pads` and `outline` in `extra`; the board is written only when `outcome.routed` is not empty |
| `cli/cmd_route.py:117-136` | the project's classes are applied; its rules file and board-setup minimums are not read |
| `routing/protocol.py:31-57` | `JobNet` holds width, clearance and via sizes; `RoutingJob` holds `design`, `nets`, `layers`, `options`, `extra`; no layer per net, no plane |
| `backends/specctra/dsn.py:493-495` | every copper layer is written `(type signal)`; zones are not written |
| `dsn.py:431-445`, `:516-522` | one `class` per net class with `width`, `clearance` and `use_via`; a default `rule`; no `class_class`, no `use_layer`, no edge clearance; model rules are not lowered (c0023, "Fitted to c0016") |
| `dsn.py:343-352` | a net of one pad whose name starts with `unconnected-(` is not declared; its pad is a pin on no net (c0061, commit 65c43f42). The living "Design files are written from the model" still says "every net with pads": this change's delta records the fact |
| `dsn.py:498-514` | outline cut-outs as `keepout` polygons on `signal`; model keep-outs with `no_tracks` or `no_vias` as `keepout`, `wire_keepout` or `via_keepout` polygons per copper layer |
| `routing/direct.py` | routes a two-pad net on the first shared layer in stack order |
| `routing/plugins/kicad/routingtools.py:108-136` | writes the board, project and rules files and runs one process per net with width, clearance and via flags; no layer option |
| `backends/kicad/layers.py:44`, `:137-156` | a copper row type is one of `signal`, `power`, `mixed`, `jumper`; created rows are `signal`; the reader keeps the type in `Layer.ext["kicad"]` |
| `lens/build.py:113`, `:145-156` | `board(planes=…)` gives `build.plane-not-lowered` on KiCad through `plane_issues(planes)`; the layer stays `signal`. The Altium build writes the plane (`altium-build`, "Internal planes in an Altium build") |
| `backends/kicad/copper.py:648-885` | the stitch resolver (`_Obstacle` to `_resolve_stitch`): exact disc-to-copper tests over a spatial index, the pattern a via search can reuse |
| `checks/clearance.py` | `ClearanceResolver` gives the clearance KiCad applies between two items (c0029, c0068) |
| `backends/kicad/copperrules.py:71`, `backend.py:150` | `design_rules` applies a project's classes and lifts its rules file into `Design.rules` |
| `routing/codes.py` | `route.project-unread`, emitted by `cmd_route.py:130`, is missing from `ISSUE_CODES` |
| `model/rules.py:18-31` | `RuleKind` holds twelve kinds; `tests/unit/dsl/test_minimums.py:32` asserts the count |
| `backends/altium/rulemap.py:81-139` | `TABLE`, one row per kind in the model's order (c0084); `tests/unit/backends/altium/test_rulemap.py:78` asserts `TABLE` order equals `get_args(RuleKind)`, so a kind without a row fails the suite |
| `cli/explain.py:23`, `cli/data/explain.toml` | `TABLES` names every code table and `tests/unit/cli/test_explain_cmd.py` fails for a code without an entry; `build.plane-not-lowered` has one (line 867) |
| `model/board.py`, `dsn.py:500-513` | `Keepout.no_tracks` is a flag of a keep-out; the rule kind of Decision 9 shares the word and nothing else |

The review's probe built 4-layer designs of 100 to 600 parts with GND and +3V3 zones on In1.Cu and In2.Cu. Each SMD pad of the two nets needed a stub and a via from coordinates computed outside the DSL: 83 vias at 100 parts, 549 at 600. Routing was not measured.

**Sources read on 2026-10-05.** The Freerouting documentation at tag `v2.4.1` (S-0221, S-0222): `-inc` takes net class names to skip; `--router.layers.routable=<flags>` marks layers routable; a fanout stage (escapes of 2.5 mm to 4.5 mm with 0.25 mm vias by default) and an optimizer run by default, and no setting bounds the optimizer's time. The Specctra reference (S-0224), read on line under ADR-0006, in Fenolite's words: a layer's type is `signal`, `power`, `mixed` or `jumper`, and wires are not routed on a `power` layer; a `plane` names a net and a shape, with optional cut-outs; a class's `circuit` may hold `use_via` and `use_layer`; `class_class` gives rules to each pair of the classes it names; a class may hold a `layer_rule` per layer; no clearance type applies to the boundary. No source code of Freerouting or KiCad was read.

**Measured on 2026-10-05.** Freerouting 2.4.1 with OpenJDK 26.0.2, one run at a time, on DSN files written by the `write_dsn` of that day (commit `7203e4b6`; the writer has since gained only the one-pad rule above) and edited per variant; the routed copper merged with `routing.merge.apply` and judged by `kicad-cli` 10.0.6 after a refill. Bench `b4`: 40 mm × 30 mm, four copper layers, GND and VCC zones on In1.Cu and In2.Cu, an SOIC-8, three 0603 parts, headers of 8 and 2 pins; classes PWR, SIG (0.2 mm width and clearance) and HV (0.5 mm, 0.3 mm); a rule of 1.0 mm between HV and SIG; 0.5 mm edge clearance. Bench `b4f`: `b4` plus one 0.4 mm track and one 0.6/0.3 mm through via per SMD pad of GND and VCC (6 pads).

| # | file | Freerouting | KiCad 10.0.6 |
|---|---|---|---|
| 1 | `b4` as written today | wires on In1.Cu (3) and In2.Cu (13), signals among them; GND and VCC, not selected, routed as tracks | 0 unconnected |
| 2 | In1, In2 `(type power)` | no wire on them; GND and VCC as surface tracks | 0 unconnected; 1 HV–SIG clearance |
| 3 | 2 + `(plane GND …)`, `(plane VCC …)` over the board | no wire on In1, In2; no via to a plane; "1 unrouted connection" for GND and for VCC; the same with every net selected | 2 unconnected |
| 4 | 3 + `--router.fanout.enabled=false` | GND 3 and VCC 2 unrouted connections | 5 unconnected |
| 5 | planes on `signal` layers | GND 2 vias, VCC 1 via; 15 signal wires on In2.Cu | 0 unconnected |
| 6 | 5 + `--router.layers.routable=true,false,false,true`, or + `use_layer F.Cu B.Cu` in every class | no inner wire; no via to a plane | 2 unconnected each |
| 6b | 5 + a wire keep-out over all of In1.Cu and In2.Cu | no inner wire; GND and VCC routed as surface tracks, no via | 0 unconnected |
| 7 | `b4f`, power layers and planes | "8 of 14 SMD pins needing fanout (6 already connected)"; no copper added to GND or VCC; no inner wire | 0 unconnected; 2 HV–SIG clearance |
| 8 | 7 + `(circuit (use_layer F.Cu))` in SIG | SIG wires on F.Cu only | 7 HV–SIG clearance |
| 9 | 7 + `(class_class (classes HV SIG) (rule (clearance 1000)))` | closest HV–SIG wires 1.0685 mm apart | 0 violation, 0 unconnected |
| 10 | 7 + `(layer_rule F.Cu (rule (width 350)))` in SIG | SIG wires 0.35 mm on F.Cu (6), 0.2 mm on B.Cu (1) | not run |
| 11 | 7 + a wire keep-out band across F.Cu and B.Cu; + a via keep-out around U1 | no wire inside the band, three nets left open; the new via outside the via keep-out | — |
| 12 | 9 + edge bands of 1.8 mm half width, judged under a 2 mm edge rule | routed | 0 unconnected, no edge finding; but no wire came within 2.69 mm of the edge with or without the bands |

The 100-part board of the review's probe, with its 83 hand vias, In1.Cu and In2.Cu written `power` and one plane per zone: "225 of 340 SMD pins needing fanout (84 already connected, 31 netless)"; the 128 open connections of 101 signal nets were closed after 11 passes (120 s), and the optimizer was still running at the 600 s timeout, so no session was written. With `--router.optimizer.enabled=false`: 0 unrouted in 365 s on a shared machine; 1133 tracks and 170 vias, none on In1.Cu or In2.Cu, none added to GND or +3V3. KiCad 10.0.6 after refill: 0 unconnected, no violation of severity error (the 136 `silk_over_copper` and 68 `silk_overlap` warnings of the unrouted board, unchanged). Freerouting counted 83 violations of its own from its first pass to its last; KiCad found none.

Wire edge to obstacle, authored two-layer benches (20 mm × 10 mm, two SMD pads, B.Cu closed), where the wire must wrap the obstacle:

| obstacle | default / class clearance (µm) | gap (µm) |
|---|---|---|
| a 1 mm notch in the signal boundary | 100/100, 200/200, 200/350, 200/800, 500/200, 1000/200 | 557, 516, 543, 539, 516, 516 |
| a passage between a wall and the boundary, 1.0 mm and 1.4 mm / 2.0 mm | 200/200 | not routed, also with the fanout stage disabled / routed, 1.50 mm from the edge, 0.25 mm from the wall |
| `keepout` polygon on `signal` | 100/100, 200/350, 500/200 | 108, 372, 514 |
| `wire_keepout` polygon | 200/350, 500/200 | 372, 514 |
| `keepout` path of 1 mm width | 200/200, 500/200, 200/350 | 207, 553, not routed |
| a boundary drawn 0.6 mm inside the board, beside a wall 2 mm from the edge | 200/200 | not routed, also with the fanout stage disabled |
| a `keepout` band 0.1 mm to 0.6 mm from the edge, beside the same wall | 200/200 | not routed |
| the same band beside a wall 3 mm from the edge; the band and wall 3 mm lower | 200/200 | routed |

`kicad-cli` 10.0.6 and 9.0.9 (pinned image), on the routed board of row 1 (tracks on both inner layers): with In1.Cu and In2.Cu of type `power`, the board loads and DRC reports no new violation type (10.0.6 refilled, 9.0.9 stored fill); the Gerbers and the job file give `Copper,L2,Inr` and `Copper,L3,Inr`, as for `signal`; `pcb upgrade --force` keeps the type on 10.0.6 (9.0.9 has no `pcb upgrade`); `read_board` keeps it and `write_board` writes it back. A rule `(layer "In2.Cu") (condition "A.NetClass == 'SIG'") (constraint disallow track)` gives 6 `items_not_allowed`, one per SIG track on In2.Cu, on both majors; `(layer inner)` gives 9 on both; a board without inner SIG tracks gives 0 (10.0.6). c0100 measured the same Gerber fact on a six-layer table.

Commands: `java -jar freerouting-2.4.1.jar -de board.dsn -do board.ses -mp 20 -mt 1 -da --gui.enabled=false [setting]` in a fresh folder that is also `HOME`; `kicad-cli pcb drc --format json --severity-all [--refill-zones --save-board] -o drc.json <board>`, `kicad-cli pcb export gerbers --output g/ <board>` and `kicad-cli pcb upgrade --force <board>`, locally for 10.0.6 and through `docker run --rm --platform linux/amd64 … kicad/kicad:9.0.9@sha256:e638b79b… kicad-cli …` for 9.0.9, which has neither `--refill-zones` nor `pcb upgrade`. None of these probes is committed; each becomes a recorded probe or test of this change.

**What the measurements decide.** A `power` layer keeps Freerouting's wires off a plane, but Freerouting does not bring a pad to a plane there (rows 3, 4, 6), and on a `signal` layer it routes across the plane (rows 1, 5). One protected via per SMD pad closes the plane net (row 7, the 100-part board). `use_layer`, `class_class` and `layer_rule` carry what they name. The board edge has no construct, and Freerouting keeps a margin of its own from the boundary that ignores every clearance value; keep-outs get the larger of the default and the class clearance.

## Goals / Non-Goals

**Goals:**
- A board with inner planes routes without tracing its plane nets, and every SMD pad of a plane net gets its via without a coordinate in the script.
- Signals stay off plane layers, and a class can be kept to some layers, in the router and under KiCad's DRC.
- Class-to-class clearance, per-layer widths, keep-outs and edge clearance reach Freerouting, and whatever cannot is named in the reply.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- Making Freerouting's own fanout stage reach planes: nowhere, because Fenolite's fan-out does it (Decision 3). The stage stays enabled for signal escapes, as today.

## Decisions

1. **A plane is a zone with a net on a copper layer of type `power`.** The type is KiCad's own row type, kept by both majors, by `read_board` and by `write_board`, and set in KiCad's board setup as well as by the script. `layers.plane_layers(design)` gives those layers in stack order; `fanout.plane_nets(design, plane_layers)` gives the nets with a zone on one of them.
   - Rejected: every zone on an inner layer. A pour on a signal layer is not a plane; signals must stay allowed there.
   - Rejected: a marker in `.fenolite/` or a model field. `route` reads only KiCad's files, a KiCad save would drop a foreign key, and c0100 owns the layer table.

2. **`board(planes=…)` sets the row type; the copper stays a zone.** On the KiCad target each plane layer of the script gets the type `power` in the board the build writes, also after the merge with an existing board, where the board's own types are otherwise kept. A plane whose net has no zone on its layer gives `build.plane-zone-missing` (warning) with the hint `design.zone(<net>, layers=("<layer>",))`; `build.plane-not-lowered` is no longer given for KiCad. A layer typed `power` in KiCad stays `power` when the script names no plane on it; a plane removed from the script leaves its type.
   - Rejected: a zone over the outline made by the build. c0100 rejected it (a name, settings and a rebuild rule for a zone the script did not declare), and one `design.zone()` call gives the same copper.
   - Rejected: the script's planes replacing every type of the board. A type set in KiCad would be undone by every build, silently.
   - c0100's objection to the type (a rebuilt board keeps its own table) is met by setting the type after the merge.
   - The Altium target is untouched: it already writes each plane of the script as an internal plane, zone or not, so it gives neither code. `build.plane-not-lowered` is then given by no target and leaves `BUILD_ISSUE_CODES` and `explain.toml`. `plane_issues(planes)` becomes `plane_issues(planes, design)`: a signature change of a function `cmd_build` alone calls.

3. **Fenolite makes the plane fan-out.** Freerouting reaches a plane only on a signal layer, where it also routes signals across it (rows 3 to 6). Protected vias make the plane net complete (row 7). Rejected: Freerouting's fanout settings (its stage added no plane via in any run). Rejected: planes on signal layers with `use_layer` or non-routable layers (row 6: no via to the plane).

4. **The fan-out is a step of `route`, before the router; the engine is a pure function.** `backends/kicad/fanout.py` holds `plan_fanout`; `cmd_route` runs it for the plane nets that the patterns select and merges its copper before it builds the job. Every router then sees that copper as existing copper; the Specctra file protects it.
   - Rejected: a script intent in this change. Script copper is regenerated on every build, which would follow a moved part; but the intents, their uuids and codes are tables that c0068 and c0111 modify, and c0111 owns script copper in a part's frame. c0111 can call `plan_fanout` from an intent.
   - Rejected: a fan-out inside the Freerouting plugin. The direct router and KiCadRoutingTools would get none.

5. **The fan-out geometry (a dog-bone per pad).** For each plane net, in board footprint order then pad order:
   - **Pads.** Its SMD pads, those without a drill, on placed footprints. A pad is *joined*, and skipped, when a via of its net overlaps its copper, or when a chain of its net's tracks and arcs on its layer leads from an end inside its copper, through equal end points or ends inside another pad of the net, to a via of the net or a through-hole pad of the net. Joined is evaluated with the copper made so far, so a pad tied by a track to a fanned-out pad gets no second via.
   - **Sizes.** Track width, via diameter `D` and drill from the net's class, else the project's `Default` class, else `route`'s constants (0.2 mm, 0.6 mm, 0.3 mm), as the job's values are taken. The neck `g` between the via's copper and its own pad's copper is the net's clearance from the same source.
   - **Directions.** The outward direction runs from the footprint's position to the pad's position; when they coincide it is the pad's own +X turned by the pad's board rotation. The eight directions at multiples of 45° from +X of the model frame are tried in order of their angle to the outward direction, ties in index order.
   - **Distances.** Along a direction the step `s` is `D/4` rounded up to a whole micrometre. The first distance is the smallest multiple of `s` at which the via keeps `g` from its pad's copper; eight more steps follow. Each via centre is rounded to a whole micrometre, so the Specctra file writes it without rounding.
   - **Tests**, exact in integers and `Fraction`, over a spatial index: the via's disc keeps the clearance in force (Decision 6) from every copper item of another net on every copper layer (pads, holes of pads without copper, tracks, arcs, vias), does not overlap another pad of its net or another via, lies inside a zone outline of its net on a plane layer by at least `D/2`, keeps the board's edge clearance from every outline ring and lies outside every cut-out, and touches no keep-out that forbids vias on any copper layer. The track from the pad's position to the via keeps the clearance in force from other nets' copper on the pad's layer and crosses no keep-out that forbids tracks there. A `hole_to_hole` rule of the whole board is kept between the drill and every other drill. Zone fills are not obstacles: they are refilled after routing.
   - **Result.** The first candidate that passes gives one track on the pad's layer and one through via, with ids derived from the net name and the geometry as `routing.merge.apply` derives them. When none passes, `kicad.fanout.failed` (warning) names the pad, the net and what blocked its first candidate, and the pad stays open.
   - Rejected: a via in the pad (c0111, with c0112's plugging). Rejected: one via shared by neighbouring pads. It saves vias and makes the result depend on pad order in more ways; the chain rule above already shares a via through a track. Rejected: blind vias to the nearest plane (no yardstick item needs them).

6. **Fan-out clearances are the copper check's.** `plan_fanout` takes a callable that gives the clearance between two `RuleSubject`s; `cmd_route` builds it from `checks.clearance.ClearanceResolver` over the project's rules (`DesignRules`), so the fan-out passes `check` by construction. Rejected: the router's larger values of Decision 9, which would waste room around dense pads where KiCad allows less.

7. **Plane nets in `route`.** A plane net is never given to a router, whatever the selection gives, also with `--include-zone-nets`; zone nets without a plane are selected as before. Each plane net that the patterns select gives `route.plane-net` (info). With `--rip`, the selected plane nets are ripped as other nets, then fanned out. `--no-plane-fanout` skips the step. The command also plans a write when the fan-out made copper and the router added nothing. `result.plane_layers` lists the plane layers, and `result.plane_fanout` holds `nets`, `pads`, `joined`, `tracks`, `vias` and `failed`.
   - Rejected: tracing plane nets under `--include-zone-nets`, as today. Freerouting cannot reach a plane on a `power` layer (row 3), so it would route the net as surface tracks and leave it open.
   - Rejected: the fan-out as a separate command. It would be one more step to forget before every `route`, and its copper must exist before the router runs.

8. **Plane layers in the Specctra file.** `write_dsn(…, plane_layers=…)` writes those layers `(type power)`. Each zone with a net that has pins, on each plane layer it covers, gives `(plane <net> (polygon <layer> 0 <outline>))` after the boundaries, in zone order. A zone whose outline has fewer than three points gives `specctra.plane-skipped` (warning) and no plane. Via padstacks keep a shape on every copper layer.
   - Rejected: plane layers kept `signal` and closed by a wire keep-out over the whole layer. Signals stay off, but the plane nets are routed as surface tracks (row 6b), which the plane makes needless.
   - Rejected: `--router.layers.routable`. It is a setting of one router, not of the file, and planes on such layers are not reached either (row 6).

9. **Routing layers per class: the rule kind `no_tracks`.** `Rule(kind="no_tracks", selector_a, layers=…)`: tracks and arcs of the items that `selector_a` selects are not allowed on `layers`. It takes no limit and no B side; its leaves are `net` and `netclass`, combined with `and`, `or` and `not`, or `all`. It is lowered to one KiCad rule per layer, `(layer "<L>") (condition …) (constraint disallow track)`, with c0071's per-layer names; `KIND_SUPPORT` holds `{9, 10}` from the probes. `read_rules` lifts a `disallow track` rule with one layer name; any other `disallow` rule, `(layer inner)` included, stays opaque. `routing.layers.allowed_layers` subtracts, for each net, the layers of every `no_tracks` rule (severity not `ignore`) whose selector matches a track of that net, from the routing layers (the copper layers that are not plane layers). The command puts the result into `JobNet.layers` (`None` when every routing layer is allowed); a net left with none gives `route.no-layer` (warning) and is not routed. The writer adds `use_layer` to the class circuit; nets of one class with different sets are written as one class per set, named `<class>@<n>`, each with the class's rule; a net without a class but with a set gets a class of its own.
   - **The second backend.** c0084's table must hold one row per kind. `no_tracks` gets the row `RuleRow("no_tracks", "no-counterpart", note=…)`, last. Altium has a rule that names the layers a scope may be routed on (its documentation, to be registered as `S-0660` by task 3.6), which is the counterpart in meaning; but no file under the sources register holds its record (kind number, keys), and `exact` needs that (c0084, "Rule lowering table"). So the build gives `altium.not-lowered` (warning, `where` `design-rules/no_tracks`) per rule, as it does for `creepage`. Rejected: `scope-unsupported` (the scope is fine, the record is unknown). Rejected: leaving the kind out of the table until someone needs it: `test_rulemap.py` fails the day `RuleKind` grows. The Altium reader maps no record to the kind.
   - **The word.** `Keepout.no_tracks` (a flag: no track inside an outline) and the rule kind `no_tracks` (no track of some nets on some layers) are told apart in `docs/dsl.md` and `docs/routing.md` by one sentence each. Rejected: another name for the kind (`track_layers`, `disallow_track`): the rule says what the flag says, for a layer instead of an outline.
   - Rejected: a CLI option per class. It is not in the design, KiCad's DRC cannot check it, and an agent must repeat it on every call.
   - Rejected: a `NetClass.layers` field. KiCad's net classes have no place for it, so `route`, which reads KiCad's files, would never see it.

10. **Rules in the Specctra file: a closed table, conservative.** The writer takes, for every pair of classes, the largest value of every rule that can apply, so the router never keeps less than KiCad's DRC asks, and may keep more where a later rule lowers a value.

    | model rule (severity not `ignore`) | written as |
    |---|---|
    | `clearance`, A `all`, B absent or `all` | every class clearance and the default rule's raised to at least `min` |
    | `clearance`, A one class or an `or` of classes, B absent or `all` | those classes' clearances raised to at least `min` |
    | `clearance`, A and B classes or `or`s of classes | `class_class (classes <a> <b>) (rule (clearance min))` per pair of written classes; a class with itself raises its clearance |
    | `track_width`, A `all` or classes, with `opt` | the width of those classes; with a layer clause, `layer_rule <layer> (rule (width opt))` instead |
    | `track_width`, A `all` or classes, without `opt` | each of those class widths clamped into `[min, max]` |
    | `edge_clearance`, A `all` | keep-out bands (Decision 11) |
    | `no_tracks` | `use_layer` (Decision 9) |
    | a layer clause on `clearance` or `edge_clearance` | dropped, the rule written for every layer, `specctra.rule-widened` (info) |
    | any other selector (`net`, `ref`, `item_kind`, a glob, `not`, c0103's `area`) or kind | not written, `specctra.rule-not-sent` (info) naming the rule and why |

    Rejected: a class per net for net selectors. It multiplies classes, is not measured, and c0104 rejected it for pairs. Rejected: area rules as keep-outs, which would forbid copper the rule only spaces.

11. **Edge clearance as keep-out bands.** `E` is the largest of the project's `min_copper_edge_clearance`, which the command adds to the job's design as a board-wide `edge_clearance` rule, and every board-wide `edge_clearance` rule. When `E` exceeds the default rule clearance `d` written in the file, each edge of every outline ring, the board and its cut-outs, gives `(keepout (path signal <2(E − d)> <x1 y1 x2 y2>))`. A wire keeps at least `d` from a keep-out (measured: the larger of `d` and its class clearance), so its copper keeps `E` from the edge.
    - Rejected: a boundary drawn `E` inside the board. It needs an offset of any outline, which the stdlib core lacks, and on the bench it closed a passage that the board left open.
    - Rejected: Freerouting's own margin from the boundary (515 µm to 557 µm measured). It follows no value Fenolite writes and is not documented.
    - The bands are `INFERRED` until a bench brings a wire near the edge (`H-G-DSN-EDGE`). Fallback: if that bench gives a `copper_edge_clearance` on routed copper, or loses a route that the file without bands makes, no band is written and the edge clearance is reported with `specctra.rule-not-sent`.

12. **Routing job fields and the three routers.** `RoutingJob.plane_layers: tuple[str, ...] = ()` and `JobNet.layers: tuple[str, ...] | None = None` are added after the existing fields, as c0023 added `extra`. The direct router takes the first shared layer that is in the net's layers and is not a plane layer. KiCadRoutingTools has no documented option for either; its run reads the board and rules files, which hold the types and the `disallow` rules, and what it does with them is not measured (`H-K-KRT-PLANES`), so the plugin gives one `route.constraint-not-sent` (warning) per run when the job has plane layers or layer sets. The Freerouting plugin passes `plane_layers` and the layer sets to `write_dsn`; the rules travel in `job.design`.
    - Rejected: both in `extra`. They are model data that `routing` can type, and `extra` holds what it cannot (`board_pads`).
    - Rejected: `-inc <class>` to keep plane nets out of Freerouting. It skips whole classes, and with planes declared and the fan-out protected the plane nets are already complete (row 7); which nets a run leaves alone is c0109's.

13. **`route` reads the project's rules.** `KicadBackend.design_rules` replaces `_with_project_classes`: classes and the rules file's lifted rules reach `job.design`, and an unreadable file gives `route.project-unread` as the project file does today. `route.project-unread` joins `ISSUE_CODES`.
    - Rejected: each plugin reading the rules file. A plugin gets no file path, by the protocol's rule, and the same rules serve the fan-out, which runs before any plugin.

14. **Order with other changes** (checked on `origin/dev` at `9aba2dff`, 2026-10-07; task 0.1 checks again):
    - c0068 and c0071 are archived (2026-10-05): the fan-out reads `BoardPad.copper` where KiCad puts it, and the kind table is living text.
    - c0084 (open on `dev`, part of `0.3.0`) adds "Rule lowering table". It lands first; "Track layer rules in the Altium rule table" is an ADDED requirement beside it, so its text is not copied here.
    - c0100 modifies "Planes in a build" and lands first. This delta is generated from the living text of `9aba2dff`; task 0.1 regenerates it from c0100's archived text (its hint names `design.zone`, its six-layer scenario).
    - "Rule kinds and limits" and "Rule constructor in the DSL" are MODIFIED here from the living text (the count, the row, the exception for a rule without a limit). c0104 adds five kinds to the first and c0103 a selector to "Closed selector grammar"; both land after this change (review of 2026-10-07, waves 4 and 5) and regenerate from its archived text. No open change on `dev` holds a delta of either.
    - "Design files are written from the model" and "Specctra issue codes and facts": no open change on `dev` modifies them. This change lands before c0109 and c0110, which build on its text (c0109's "Nets outside the routing job in design files" names the Network bullet as it reads here).
    - c0108 modifies "Net selection" and "Route command" and lands first; this change adds requirements beside them and modifies neither. A plane net is removed from the job after c0108's selection, whatever its open connections, which stay open in c0108's count until `fill` connects the fan-out vias. c0108's locks keep locked copper out of a rip of plane nets.
    - c0111 may call `plan_fanout`; c0112's board default protection applies to fan-out vias; c0103's keep-outs are written as today, its area rules are reported as not sent; c0105's per-layer `track_width` rules with `opt` reach Freerouting as `layer_rule` widths, its pair values are c0110's.
    - Rejected: writing these deltas on the drafts of c0100 and c0109, which may still change before they are archived.

## Found on 2026-10-08

Corrections made while the change was implemented, each with what showed it.

1. **Entry check.** `0.3.0` is not released, and c0084, c0100 and c0108 are implemented on the integration branch and not archived. The maintainer's instruction for the night of 2026-10-07 replaces the stop of task 0.1: the deltas are written against the branch. "Planes in a build" was regenerated from c0100's delta (its six-layer scenario is kept, with the new outcome); the four other MODIFIED requirements equal the living text with this change applied; no other open change modifies them, but c0104, which lands later.
2. **Edge bands are not written (Decision 11's fallback).** `dsn-edge-band` was `different`: on the edge bench (a slot between two pads, 2 mm of board past its ends, edge clearance 0.5 mm) the file with bands lost the route that the file without bands made, although a legal route exists. With 4 mm of board the bands worked: no `copper_edge_clearance` on tracks, where the file without bands gave 3. `H-G-DSN-EDGE` is refuted and `H-G-DSN-EDGE-2` records both facts. The writer writes no band; an `edge_clearance` rule gives `specctra.rule-not-sent`. The requirement "Routing rules in design files", its scenario, the Structure bullet and `docs/` say so. The fan-out still keeps the edge clearance by its own test, and `route` still adds the project's `min_copper_edge_clearance` to the design as a rule, for the fan-out and for the report.
3. **`layer_rule` is honoured in part.** `dsn-layer-rule` was `different`: 14 of 20 segments take the layer width, 6 are 262.4 µm, at pins. The list is still written (cut-order item 2 was not taken): it moves the wire to the rule's width, and the register row of `H-G-DSN-CLEARANCE` says what was seen.
4. **Class split names.** The requirement gave the class's name to the group of its first net, and its scenario to the group without a layer set. The scenario is kept: the group that may use every signal layer keeps the name, which leaves the common case (most nets unrestricted) under the class's own name.
5. **`KIND_SUPPORT["no_tracks"]` holds 10 only.** The requirement ties the entry to the probe files, and the probe of 9.0.9 could not be recorded that night. A target-9 build with a `no_tracks` rule is refused with `rules.kind-unchecked` (or dropped with `--allow-lossy`) until `dru-kind-no_tracks` is `present` in `9.0.9.json`; then the entry gains 9, in one line of `rulemap.py`, and `test_kind_support_of_no_tracks_follows_the_probe_files` says so by failing.
6. **Fan-out order.** Pads are taken in one pass over the board, in footprint order then pad order, whatever the order of `nets`; the built board lists its footprints by reference, so `C2-2` comes before `U1-4`. `result.plane_fanout.failed` is then in board order without a second sort.
7. **The fan-out oracle selects the plane nets.** `route --router direct` on the whole bench would add straight tracks that cross each other, so `route-fanout-t<M>` runs it with `--nets GND --nets VCC`.
8. **The bench.** `tests/routing/_planebench.py` uses two four-pin headers and two two-pin headers of the catalog in place of the eight-pin header of the first measurements, with the `HV` nets on their own headers: a `HV` pad beside a `SIG` pad on one header breaks the 1 mm rule in the build's own copper check. `hv_near=True` gives the variant of the class-to-class gate.
9. **The Freerouting tests use the writer's arguments from the start.** Task 1.4's tree edits were skipped, as the writer existed when the jar became available; only the edge bands are a tree edit, because the writer does not write them.
10. **Meeting c0109** (landed on the branch the same night): `JobNet.layers` and `RoutingJob.plane_layers` come before c0109's `tier` and `budget`; `_Writer.plane_nets()` returns the nets of the planes the file holds; with `others="netless"` a net also stays declared when the rules raise its class above the default rule or pair its class with the class of a selected net; the KiCadRoutingTools plugin writes a rule set read from a file with `write_rules`.
11. **The jar.** The Freerouting outcomes were recorded with the jar of the routing image already on the machine (2.4.1, sha256 `00ba5b87…`), whose hash differs from the pinned file; each outcome names its jar, and the proof with the pinned jar is the `routing` job's.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/backends/kicad/layers.py` | `plane_layers(design) -> tuple[str, ...]`; `with_plane_types(layers, planes) -> tuple[Layer, ...]` |
| `src/fenolite/backends/kicad/fanout.py` (new) | `FanoutSizes(width, via_diameter, via_drill, neck)`; `FanoutPlan(tracks, vias, pads, joined, failed, issues)`; `plane_nets(design, plane_layers)`; `plan_fanout(design, pads, *, nets, plane_layers, outline, edge_clearance, clearance) -> FanoutPlan`; `FANOUT_ISSUE_CODES`; `EVIDENCE` |
| `src/fenolite/backends/kicad/rulemap.py`, `lowering.py`, `dru.py` | the `no_tracks` row: `disallow track`, its grammar, `KIND_SUPPORT`, the lift |
| `src/fenolite/model/rules.py` | `no_tracks` in `RuleKind`, last |
| `src/fenolite/backends/altium/rulemap.py`, `docs/formats/altium/pcb-copper.md` | the `no_tracks` row, `no-counterpart`, and its line in "The lowering table" |
| `src/fenolite/cli/data/explain.toml`, `src/fenolite/cli/explain.py` | nine entries added, `build.plane-not-lowered` removed; `FANOUT_ISSUE_CODES` in `TABLES` |
| `src/fenolite/backends/specctra/dsn.py` | `write_dsn(…, plane_layers=(), net_layers={})`; power layers, planes, `use_layer`, class splits, the rules table, edge bands; three codes |
| `src/fenolite/routing/protocol.py` | `RoutingJob.plane_layers`, `JobNet.layers` |
| `src/fenolite/routing/layers.py` (new) | `routing_layers(layers, plane_layers)`, `allowed_layers(design, net, routing_layers)` |
| `src/fenolite/routing/direct.py`, `plugins/kicad/routingtools.py`, `plugins/specctra/freerouting.py`, `codes.py` | layer choice; `route.constraint-not-sent`; the new arguments; `route.plane-net`, `route.no-layer`, `route.constraint-not-sent`, `route.project-unread` |
| `src/fenolite/cli/cmd_route.py` | rules from `design_rules`, plane nets, the fan-out step, `--no-plane-fanout`, `result.plane_layers`, `result.plane_fanout`, the write rule |
| `src/fenolite/dsl/design.py` | `rule()` takes `no_tracks` without a limit and with layers |
| `src/fenolite/lens/build.py`, `src/fenolite/cli/cmd_build.py` | plane types after the merge; `build.plane-zone-missing` |
| `schemas/fenolite.model.v0/rules.json` | regenerated |
| `tests/routing/_planebench.py` (new), `tests/routing/test_freerouting_planes.py` (new), `tests/kicad/board/test_layer_power.py` (new), `tests/kicad/rules/test_rule_kinds_new.py`, `tests/kicad/routing/test_fanout_oracle.py` (new) | the bench of `b4` rebuilt from the offline catalog (no KiCad library needed), the gate and oracle tests |
| `docs/formats/specctra/dsn.md`, `docs/formats/kicad/board.md`, `docs/formats/kicad/rules.md`, `docs/routing.md`, `docs/dsl.md`, `docs/cli-contract.md`, `docs/evidence/routing.md` | facts, the fan-out rules, the reply keys, the outcomes |

## Sources registered by this change

| id | source | used for |
|---|---|---|
| S-0660 | Altium's public documentation of its routing-layers design rule (the page is opened, and its address and date written into the register, by task 3.6) | the note of the `no_tracks` row: a counterpart exists in meaning, its record is in no public file |

S-0660 is the first id of the block S-0660 to S-0679 given to this group on 2026-10-07; `docs/evidence/sources.md` ends at S-0601 on `9aba2dff`. S-0221 and S-0222 were read at tag `v2.4.1` for the settings named in Context; S-0224 for the format facts, under ADR-0006; S-0020 and S-0029 are the two `kicad-cli` oracles.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-G-DSN-LAYERS | Freerouting 2.4.1 routes no wire on a layer written `(type power)`, and keeps the wires of a class whose circuit holds `use_layer` on the named layers (S-0224) | `tests/routing/test_freerouting_planes.py -k layers` | outcomes `dsn-power-layers` and `dsn-use-layer` `equal` on the `b4` bench |
| H-G-DSN-PLANE | A `plane` on a `power` layer joins every pin of its net that a protected via or a through-hole pad reaches, and Freerouting 2.4.1 adds no copper to that net; it brings no SMD pin to such a plane by itself (S-0224) | `… -k plane` | `dsn-plane-fanout` `equal` (no copper on the plane nets, no open plane connection); `dsn-plane-alone` recorded `open` |
| H-G-DSN-CLEARANCE | Freerouting 2.4.1 keeps a `class_class` clearance between the two classes' wires, a `layer_rule` width on its layer, and the larger of the default and class clearance from `keepout` and `wire_keepout` polygons and `keepout` paths (S-0224) | `… -k clearance` | `dsn-class-class`, `dsn-layer-rule`, `dsn-keepout` `equal` |
| H-G-DSN-EDGE | With keep-out paths of half width `E − d` along each outline edge, Freerouting 2.4.1 routes a bench whose shortest route runs along the edge, and KiCad finds no `copper_edge_clearance` on its copper | `tests/routing/test_freerouting_planes.py -k edge` | `dsn-edge-band` `equal` on 10.0.6; else Decision 11's fallback |
| H-K-LAYER-POWER | A copper row of type `power` loads on 9.0.9 and 10.0.6, adds no DRC finding, gives the Gerber file function `Copper,L<n>,Inr` of a signal row, and is kept by `pcb upgrade --force` on 10.0.6 (S-0020, S-0029) | `tests/kicad/board/test_layer_power.py` | probes `pcb-layer-power-t<M>` `equal` on each major, `pcb-layer-power-resave` `equal` on 10.0.6 |
| H-K-DRU-NOTRACKS | `(constraint disallow track)` with `(layer "<name>")` and a condition on `A.NetClass` or `A.NetName` gives one `items_not_allowed` per track of the selected items on that layer, and none elsewhere (S-0020, S-0029) | `tests/kicad/rules/test_rule_kinds_new.py -k no_tracks` | probe `dru-kind-no_tracks` `present` and its control `absent` on both majors; `KIND_SUPPORT` equals them |
| H-K-FANOUT | The fan-out of `route` on the `b4` bench with `planes=` gives no finding of `check` and, after `fill`, no unconnected item and no violation of severity error under `kicad-cli` of the board's major | `tests/kicad/routing/test_fanout_oracle.py` | probe `route-fanout-t<M>` `equal` on both majors (the target-9 board filled by `fenolite fill` with 10.0.6, judged by 9.0.9) |
| H-K-KRT-PLANES | KiCadRoutingTools v0.22.1 routes no track on a `power` layer and honours a `disallow track` rule of its rules file | `tests/routing/test_krt_gate.py -k planes` | recorded when a checkout exists; until then the plugin warns |
| H-G-DSN-EDGE-2 | Added on 2026-10-08 as the successor of the refuted `H-G-DSN-EDGE`: the bands keep the edge clearance where the board leaves room and lose the route of a narrow passage, so the file holds none and the rule is reported | `tests/routing/test_freerouting_planes.py -k edge`, `tests/unit/backends/specctra/test_dsn_rules.py -k edge` | 4 mm passage routed without an edge finding, 2 mm passage not routed, with bands added by the test; the writer writes no band |

All start `INFERRED`, with the measurements of Context as their first record. Ids used without changing their level: `H-G-DSN-ACCEPT`, `H-G-DSN-PROTECT`, `H-G-DSN-ROUTE`, `H-G-DSN-INCOMPLETE`, `H-K-DRU-KIND-2`, `H-K-COPPER-ZONECLR`, `H-G-FRAME-OFFSET`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| power layers, planes, `use_layer`, `class_class`, `layer_rule`, keep-outs in the Specctra file | ORACLE-VERIFIED(freerouting 2.4.1) | `dsn-*` outcomes in `docs/evidence/routing/freerouting-2.4.1.json` |
| edge bands | KICAD-VERIFIED (10.0.x), or the fallback | `dsn-edge-band` |
| row type `power`, track layer rules | KICAD-VERIFIED (9.0.x, 10.0.x) | `pcb-layer-power-*`, `dru-kind-no_tracks` |
| fan-out | KICAD-VERIFIED (9.0.x, 10.0.x) | `route-fanout-t<M>` |
| allowed layers, rules table, class splits, plane nets in `route` | mechanical | unit tests |
| the `no_tracks` row of the Altium rule table | INFERRED (a statement that no public record exists; nothing is written) | `test_rulemap.py -k complete` |
| a routed board | UNVERIFIED, as every route | — |

## Risks / Trade-offs

- **A pad without room.** Dense parts may leave pads open. Mitigation: each is named with what blocked it; KiCad's DRC lists it as unconnected; script copper (c0111) or a moved part closes it.
- **Fan-out copper after a part moves.** It is routed copper: a later build keeps it where it was. The build's copper guard reports a via that a moved part now overlaps; `route --rip --nets <plane net>` redoes the fan-out. c0108's locks will keep hand-made copper out of the rip.
- **Conservative clearances.** The router may keep more than KiCad asks; dense boards lose some room. The DRC remains the judge.
- **Edge bands near narrow passages.** The benches lost routes beside the boundary in ways not explained. Mitigation: the oracle bench and the fallback of Decision 11.
- **Freerouting's optimizer.** On 100 parts it outran a 600 s timeout and the whole result was lost. That is c0109's to bound; this change records it.
- **Freerouting version.** Every fact is pinned to 2.4.1 and re-checked by the gate tests on a new pin.

## Migration Plan

- Boards without a `power` layer and scripts without `planes=` route and build as before.
- A KiCad build with `planes=` writes `power` rows, and gives `build.plane-zone-missing` instead of `build.plane-not-lowered` when a zone is missing. `CHANGELOG.md` says so.
- `route` on a board with plane layers adds fan-out copper and stops routing plane nets with `--include-zone-nets`.
- The Specctra file of a board with rules gains classes, `class_class` and bands; `route` replies gain `plane_layers` and `plane_fanout`.
- `rules.json` gains the kind `no_tracks`. Releases 0.2.x and 0.3.x cannot read a model document that holds such a rule (their `RuleKind` lacks the value); a document without one is byte for byte what it was. `CHANGELOG.md` and `docs/design-model.md` say so.
- `build.plane-not-lowered` is no longer a code; `fenolite explain build.plane-not-lowered` then answers as for any unknown code.
- An Altium build of a script with a `no_tracks` rule gains one `altium.not-lowered` warning per rule.
- Rollback: drop `plane_layers` from the job; the file returns to signal layers, and fan-out copper already written stays as routed copper.

## Budget (10 days)

| part | days |
|---|---|
| registers; Freerouting outcomes and KiCad probes recorded | 1.0 |
| plane layers: `plane_layers`, types after the merge, `build.plane-zone-missing`, oracle rows | 0.75 |
| track layer rules: kind, lowering, lift, DSL, probes, the Altium row, explain entries | 1.25 |
| job fields, `allowed_layers`, direct router, KiCadRoutingTools warning | 0.5 |
| Specctra writer: power layers, planes, `use_layer` and class splits, rules table, codes, fact page | 1.75 |
| edge bands and their bench | 0.5 |
| Freerouting plugin, gate tests on the bench | 0.75 |
| fan-out engine and unit tests | 1.5 |
| `route`: rules, plane nets, fan-out step, replies, codes | 0.75 |
| fan-out oracle on both majors | 0.5 |
| documentation and closing | 0.75 |

Cut order: (1) edge bands (0.5; edge clearance reported as not sent); (2) `layer_rule` and the `track_width` rows (0.25); (3) class splits (0.25; a class whose nets differ gets no `use_layer`, reported); (4) the KiCadRoutingTools warning (0.1). Together 8.9 days. Never cut: plane layers, the fan-out and its oracle, `use_layer` and track layer rules, `class_class`.

## Open Questions

- **Should the fan-out take its own via size, neck and reach?** Default: the class values and Decision 5's steps; options can follow when a board needs them.
- **Should `planes=` also make the plane's zone?** Default: no, as c0100 decided; `build.plane-zone-missing` names the call.
- **Should a plane removed from the script reset the row to `signal`?** Default: no; the type may have been set in KiCad.
- **Should per-class edge clearance be widened to every net instead of not sent?** Default: not sent; a 3 mm band for one class would cost every net the same band.
- **Should KiCad's DRC check plane layers by itself?** Default: no automatic rule; `rule(…, "no_tracks", layers=<plane layers>)` makes it.
