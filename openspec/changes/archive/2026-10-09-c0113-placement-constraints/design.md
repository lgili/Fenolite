## Context

**Scope.** The review of 2026-10-05 of the gaps to a complex board gave milestone v0.4 (`docs/roadmap.md`, "The complex board, c0100–c0120"; the branch the proposal was written on called the group v0.2c) four placement gaps that no change and no roadmap line owned: proximity constraints and their check (decoupling, crystal, gate driver); placement keep-outs; part heights; wire length and congestion numbers in the replies of `place` and `check`. This change keeps three of them. Part heights and height limits left it on 2026-10-07 by the maintainer's decision and are c0140-part-height-rules (Decision 3). The connectivity-driven placer stays on its roadmap line (v0.5a, annealing placer); a placement frame per module is in no change, and this change depends on neither.

**What exists** (read at `origin/dev` `9aba2dff` on 2026-10-07):

- *Placement.* `placement.legality.check(extents, outline_rings, *, edge_clearance=0, names, touching_overlaps)` judges courtyard overlaps, the outline and the edge clearance, with exact integer predicates (`interiors_intersect`: rings that only touch do not meet). It has no keep-out branch, and `placement/codes.py` has no keep-out code. `placement.grid.place(boxes, region, *, occupied, cutouts, pitch, gap, margin)` packs boxes in the order given and knows no net.
- *`fenolite place`* (`cli/cmd_place.py`, unchanged since the proposal was written). The grid avoids the boxes of the courtyards on the board and of the cut-outs (lines 299–307). Legality runs without keep-outs (line 329). The command already loads `.fenolite/` with `canonical.load_dir` to find parts locked by the script (`_script_locked`). `result` holds `board`, `strategy`, `moved`, `unplaced` and `legality`.
- *`fenolite build`.* `cmd_build.placement_guard` reads the planned board back and runs the same legality check, every issue at most a warning; `result.placement` is `{ran, counts}`. The living "Placement legality in a build" says the guard does not run with `--target altium`. The `.fenolite/` model of a KiCad build is `merge_layout(built, readback).design`: its circuit and board come from the merge, its rules layer from the built design unchanged.
- *Model.* `Keepout(outline, layers, no_tracks, no_vias, no_pads, no_copper_pour, no_footprints)` is read and written; c0103 adds `name`. `RuleSet` holds `rules`; c0104, c0105 and c0114 propose more fields.
- *DSL.* `Part.place(x, y, …)` is absolute and called once; `Module` has no placement. `Part.pad(number, *, index=None)` returns a `PadRef` for copper intents. No call states a distance between parts or an area that parts must avoid.
- *Checks, two pipelines.* `run_checks` (`checks/stages.py`) runs `STAGE_ORDER` on a KiCad project: `model.validate`, `erc.kicad`, `copper.clearance`, `zone.fill`, `drc.kicad`, `parity`, `netlist.assignment_compare`, `roundtrip`, `roundtrip.rt2`, `render`; `OPT_IN_STAGES` is the last two. `run_document_checks` (`checks/documents.py`, c0088, open on `dev`) runs `DOCUMENT_STAGES` on Altium documents: `model.validate`, `erc.lite`, `copper.clearance`, `parity`, `netlist.assignment_compare`, `roundtrip.rta0`, `roundtrip.rta1`, `roundtrip.rta2`. Both receive the `.fenolite/` model of a built project. `checks` imports only `model`, `geometry` and `backends.base`, and reaches the board frame through the validator (`BoardFrame`); `AltiumBackend` has `board_pads`, `placed_extents` and `design_rules`, as `KicadBackend` has.
- *Explain* (c0066). Every issue code needs a table in `src/fenolite/cli/data/explain.toml`; `tests/unit/cli/test_explain_cmd.py` fails for a code without one.
- *Views* (c0066). `net`, `region` and `neighbors` give pad positions, boxes and neighbours; no length and no congestion.
- *KiCad's rule language* has no maximum distance between footprints: among the constraint types of the token inventory (S-0010), `courtyard_clearance` is a minimum. A proximity rule cannot be lowered to `.kicad_dru`.
- *Pitch.* The project templates that `build` writes hold the class `Default` with a 0.2 mm track and a 0.2 mm clearance. `DesignRulesSource.design_rules` returns the project's classes, `Default` included (`pro.apply_project`).
- *Not on `dev`, on its own branch:* c0096 (`codex/c0096-constrained-placement`), with `--strategy constrained`, `place.constraint`, `place.objective` and a full MODIFIED "Place command" ("Relation to c0096" below).

**Measured on 2026-10-05**, on the branch the proposal was written on (base `7203e4b6`). Scripts, command lines and outputs are in this change's probe folder; none is committed, and nothing was measured again at `9aba2dff`: task 1.2 repeats measurement 1 as recorded probes. `placement/`, `cli/cmd_place.py` and the three living requirements this change modifies have no commit between the two.

1. *Keep-outs that forbid footprints.* 18 benches on the rules bench of `tests/kicad/rules/_rulebench.py` with c0071's scoped canary, written with `write_board` for each target (the writer writes `Keepout.no_footprints` as `(footprints not_allowed)`). Each holds one probed part, a control part outside every area, and one rule area. `kicad-cli pcb drc --format json --severity-all` on 10.0.6 locally and on 9.0.9 in the pinned image (one container, 28 s). The canary fired in every run; the verdicts are identical on both majors. `Mini_R_0603` at 0°: courtyard rectangle x −1.5..1.5 mm, y −0.75..0.75 mm (line centres, 0.05 mm stroke), pad copper x 0.35..1.25 mm, Reference text above the courtyard.

   | case | area | probed part | `items_not_allowed` names the footprint |
   |---|---|---|---|
   | `in` | `F.Cu`, over the whole part | top | yes |
   | `crt-only` | `F.Cu`, x 1.30..3.0 mm: courtyard margin, no pad | top | yes |
   | `over-10um` | `F.Cu`, from x 1.49 mm | top | yes |
   | `touch` | `F.Cu`, from x 1.50 mm (the line centre) | top | no |
   | `gap-10um`, `gap-30um` | `F.Cu`, from x 1.51 and 1.53 mm (inside the stroke) | top | no |
   | `text-only` | `F.Cu`, over the Reference text only, 0.1 mm above the courtyard | top | no |
   | `rot-crt` | `F.Cu`, from x 0.9 mm | top, turned 90° | no |
   | `bot-front` | `F.Cu` only, whole part | bottom | no |
   | `bot-back` | `B.Cu` only, whole part | bottom | yes |
   | `bot-both` | `F.Cu` and `B.Cu`, whole part | bottom | yes |
   | `top-back` | `B.Cu` only, whole part | top | no |
   | `inner-only` | `In1.Cu` only, four-layer board | top | no |
   | `tht-front` | `F.Cu`, whole `Mini_LED_THT_3mm` (front courtyard only) | top | yes |
   | `tht-back` | `B.Cu`, whole `Mini_LED_THT_3mm` | top | no |
   | `nocrt-in`, `nocrt-pad`, `nocrt-mid` | `F.Cu`: whole part, pad 2 only, between the pads | top, courtyard removed | no |

   The violation names the footprint, never its pads, with the description "Items not allowed (keepout area)" on both majors. The predicate of Decision 5, run with `KicadBackend().placed_extents` and `placement.legality.interiors_intersect` on the read boards, gives the same verdict in all 18 cases.
2. *Measures on the boards of the review's scale probe*, three boards of 100, 400 and 600 parts generated by a script authored for Fenolite and not committed (four layers, `GND` and `+3V3` zones on the inner layers; "script" is the placement the generator computed, "grid" the result of `place --strategy grid`). Prototype of Decision 7 in pure Python, with its definitions: 2 mm cells, so 5 tracks per layer at the pitch of 0.4 mm of the class `Default`. Decoupling pairs are each capacitor with one pad on `GND` and the other on a net of an IC of its module, measured to the nearest such IC pad: the rules a script would declare.

   | board | measured nets | HPWL | spanning tree | cells needing more than 1 / 2 layers | busiest cell | pairs within 3 / 5 / 10 mm | median, max |
   |---|---:|---:|---:|---:|---:|---:|---:|
   | 100, script | 101 | 3.57 m | 2.91 m | 48 / 0 | 10 tracks | 0 / 5 / 12 of 23 | 10.0, 32.3 mm |
   | 100, grid | 101 | 3.89 m | 3.18 m | 39 / 0 | 9 tracks | 0 / 1 / 9 of 23 | 16.5, 47.1 mm |
   | 400, script | 298 | 13.11 m | 10.97 m | 166 / 12 | 13 tracks | 0 / 17 / 24 of 80 | 15.0, 43.5 mm |
   | 400, grid | 298 | 20.35 m | 17.54 m | 336 / 22 | 11 tracks | 0 / 0 / 1 of 80 | 45.5, 115.8 mm |
   | 600, script | 406 | 17.96 m | 15.09 m | 304 / 18 | 13 tracks | 0 / 25 / 32 of 113 | 15.3, 43.5 mm |
   | 600, grid | 406 | 31.18 m | 27.70 m | 617 / 75 | 14 tracks | 0 / 0 / 2 of 113 | 52.5, 178.0 mm |

   The two zone nets are left out (`GND` alone has 320 pads at 600 parts). The busiest cell does not tell the 600-part variants apart (13 and 14 tracks); the counts of cells do (304 and 617 needing more than one layer, 18 and 75 more than two). At 100 parts the grid variant is the less crowded one: the counts follow the board, not the method.
3. *Cost at 600 parts* (a machine shared with test suites: upper bounds). The measures take at most 0.25 s per board. Their inputs cost more: `read_board` 9 to 13 s, `board_pads` 2.1 s, `placed_extents` 3.5 to 4 s. `check` already pays the read; `place` already pays `placed_extents` once or twice.

**Constraints.** Stdlib only; integer nanometres; no float in the model or in a reply. Fenolite ships no distance: the script gives every value. The DSL imports only `core` and `model`; `checks` and `placement` import only `model`, `geometry` and `backends.base`.

## Goals / Non-Goals

**Goals**
- A script states which parts belong near which pads and where parts may not go.
- `place`, `build` and `check` judge those rules, and `place` and `check` say how long and how crowded the wiring of a placement will be, so an agent can compare two placements before routing.
- A keep-out that forbids footprints gets the same verdict from Fenolite as from KiCad's DRC, under one code.
- The rules are model data that the placer of v0.5a can read.

**Non-Goals**
- Everything under "Non-goals" in the proposal, with the destinations named there.
- Moving parts to satisfy a rule. `place` and the grid report; they do not optimise (Decision 11).
- Judging routed copper. The measures are about placement; routed length is c0106's.

## Decisions

1. **Placement rules are model data of the rules layer, not KiCad rules.** KiCad's rule language cannot hold a maximum distance (Context), so nothing is lowered. `RuleSet` gains `proximity: tuple[ProximityRule, ...]`, value objects in name order, empty by default, so a `rules.json` without it loads and an unchanged design writes the same bytes. The rules layer of `.fenolite/` comes from the built design (Context), so `check` and `place` find the rules of the last build there.
   - They are value objects, not entities: a rule is named by its key and has no id, so "Identifier derivation", which c0103 modifies, stays untouched.
   - They are no rule kind. `RuleKind`, `KIND_SUPPORT` and the Altium rule table of c0084 (`rulemap.TABLE`, one row per kind) do not change, and no test of that table sees a new kind.
   - Rejected: new kinds in `RuleSet.rules`. Every reader of rules (the KiCad lowering, the Altium table, `read_rules`, the clearance resolver) would have to skip kinds that are never written, and no selector names a pad.
   - Rejected: footprint properties on the board (`fenolite.near = "U1:7 2mm"`). A relation between two parts is no property of one of them, and a text that a person may edit in KiCad would need a parser and its errors.
   - Rejected: a file beside the script, like c0069's `placements.toml`. The script is the source and `.fenolite/` its cache (`design-model`, "Layout authority"); a third place would drift.

2. **`near`: each part of one side near the other side, centre to centre.** `design.near(key, parts, anchor, *, within, severity="error")`.
   - `parts` and `anchor` each take a `PadRef` (`u1.pad(7)`, `u1.pad("A1", index=0)`), a `Part`, a `Module`, or a non-empty list or tuple of them. A `PinHandle` is refused with the hint `part.pad(n)`: on `dev` a symbol pin reaches its pads only through the library, at build time (Open Questions, for c0123). `within` is a positive length; `severity` is `error` or `warning`; the key follows the pattern of copper keys and is unique among `near` rules.
   - `to_model` turns a part into `PadSelection(path)`, a `PadRef` into `PadSelection(path, number, index)`, and a module into one `PadSelection(path)` for each part of it and of its sub-modules, in path order. A part or module that is not in the design raises `DslError` naming it, as `copper()` does.
   - The rule holds for a part when the distance between the positions (`BoardPad.position`) of one of its selected pads and one pad of `anchor` is at most `within`, compared exactly on squares. Each part that fails gives one `placement.too-far` with the rule's severity, naming the rule, the part, the nearest anchor pad, the distance and `within`. A part on both sides is at distance 0.
   - **One rounding.** The verdict never rounds. The distance that a message or a reply prints is rounded up to the nanometre. For a maximum that is the only rounding that agrees with the verdict: a part that fails prints a distance above `within`, and one that passes never does. c0096 rounds the pad-centre distance of its objectives the same way, so the two changes print one number for one pair of pads. (The proposal first floored it; a part 0.4 nm too far would then have printed exactly `within` and still failed.)
   - So `near("dec7", c5.pad(1), u1.pad(7), within=mm(2))` is a decoupling rule, `near("xtal", (y1, c13, c14), (u1.pad(12), u1.pad(13)), within=mm(5))` a crystal rule, and `near("ch1", ch1, ch1.u, within=mm(15))` keeps a module together. A gate driver takes two rules: driver output near the gate, driver return near the source.
   - Why centres: `BoardPad.position` is where tracks end (c0068 keeps it at the pad's `at` for an offset drill), it is exact in integers for every pad shape, and the distance between two centres is a lower bound of any trace that joins them.
   - The word `anchor` here is the reference side of a rule. c0111's `AnchorRef` is a point in a part's frame and c0096's `Part.place(…, anchor=…)` the reason of a locked placement; no identifier is shared, and `docs/dsl.md` tells them apart in one sentence (task 9.1).
   - Rejected: copper edge to edge. The distance between two polygons is irrational, and two touching pads read 0 whatever their size. Rejected: courtyard to courtyard, which says nothing of which pin is near. Rejected: pairing a capacitor with "the nearest pin of the same net" automatically; the script names the pin it means.
   - Rejected: `severity="ignore"`, a rule that judges nothing.

3. **Part heights and height limits are not in this change.** The maintainer decided on 2026-10-07 to take them out into c0140-part-height-rules, written after c0099 is on `dev`. The proposal had given a part's height a second home (`Component.height`) beside `ComponentBody`, which c0099 extends with `z_min`, `z_max` and `projection_unknown` and for which c0121 reserved a later DSL decision; c0140 names one source. What this change leaves ready for it:
   - named rule areas (c0103) and the face rule of Decision 5, which c0140 reuses for "a part under an area";
   - `RuleReport.counts`, a mapping by rule family that holds `near` here and to which a later change adds a family;
   - `rules_of(model)`, the one place that collects the placement rules of a model;
   - the stage `placement.rules` and the reports of `place` and `build`, which c0140 extends by ADDED requirements that name them.
   - Nothing of heights stays here: no `Part(height=…)`, no `Component.height`, no `HeightLimit`, no second run of the grid, and the codes `placement.too-tall` and `placement.height-unknown` are c0140's.

4. **One report shape for every rule family.** `judge(design, rules, *, pads) -> RuleReport(issues, counts)`; `counts` maps a family to its counts and holds `{"near": {"judged", "failed", "skipped"}}` in this change. Callers print the mapping as it is, so a family added later appears in `summary.rules`, `result.rules` and `result.placement.rules` without a change of their contracts.
   - Rejected: fixed keys `near` and `height` with zeros until c0140 lands: a reply that names a rule family Fenolite cannot judge yet.

5. **Keep-outs that forbid footprints are judged as KiCad judges them.** `footprints` joins c0103's `FORBID` and maps to `Keepout.no_footprints`, which the writer already writes. `placement.legality.check` gains `keepouts=()`.
   - For a keep-out with `no_footprints` and a judged extent: when the area's layers hold `F.Cu` and the interior of a front ring meets the area's interior, or `B.Cu` and a back ring, the part gets `place.keepout` (error), whose message names the area (by `Keepout.name`, or "an unnamed keep-out") and the face. The predicate is `interiors_intersect`, the one of overlaps, so an area that only touches a courtyard does not count. Measurement 1 agrees in all 18 cases.
   - An extent of source `pads` (no courtyard) is never reported by KiCad (measurement 1). Fenolite judges its pad hull and reports `place.keepout-no-courtyard` (warning): a part without a courtyard in an antenna keep-out is a defect that no other check would see.
   - The grid avoids the bounding box of every keep-out that forbids footprints, as it avoids cut-outs.
   - This is the one keep-out predicate and the one code of the package ("Relation to c0096").
   - Rejected: judging pads or the footprint's box, which disagrees with the DRC that `place` promises to anticipate. Rejected: skipping parts without a courtyard in silence.

6. **Rules and measures live in `checks.placement`; keep-outs in `placement.legality`.** The `check` stage must run the rules and the measures, and `checks` may import only `model`, `geometry` and `backends.base` (`package-layering`). So `fenolite.checks.placement` holds `judge` and `measure`, and `cmd_place` and `cmd_build` call them, as `cmd_build` already calls `checks.copper` for its copper guard. Keep-outs stay in the legality check, which KiCad's DRC repeats; `check` does not judge them a second time.
   - `checks.placement.board_box(design)` gives the box of the board from `Board.outline` or from the graphics on the layer of kind `edge` (an arc by `Arc.bbox`), because `checks` cannot call `backends.kicad.outline`. For a closed outline of lines it equals the box that `cmd_place` takes from `board_outline`, and with arcs it differs from it by less than the arc tolerance of `board_outline`; a part is off the board when its position lies outside it, as for the grid and the lens.
   - Rejected: the code in `placement` with an edge `checks → placement`. It needs a MODIFIED "Allowed import edges" and a MODIFIED "Check stages and statuses", two long living requirements, for one consumer; c0045 rejected an edge change for the same reason. Rejected: two copies of the measures.

7. **Measures from pad positions, in integers.** `measure(design, *, pads, pitch=None) -> Measures`.
   - Counted pads: those of footprints on the board (Decision 6). Measured nets: two counted pads or more and no zone on the board. A net carried by a zone joins through it, and it would dwarf every other net (measurement 2). `left_out` counts zone nets, one-pad nets and parts off the board.
   - `hpwl`: the sum over measured nets of the width plus the height of the box of their pad positions. `ratsnest`: the sum of each net's Euclidean minimum spanning tree over its pad positions (Prim, squared distances compared exactly, each edge floored to the nanometre: a sum of lengths, where the floor keeps a lower bound; the rounding of Decision 2 is for a distance judged against a maximum). It is Fenolite's own tree; KiCad's ratsnest is not compared, since `kicad-cli` does not export it. `longest`: the five nets of largest `hpwl`, ties by name.
   - Congestion follows the idea of a rectangular uniform wire density (S-0680): square cells of side `cell`, 2 mm, or the box's longer side divided by 128 when larger (whole micrometres); each measured net spreads its `hpwl` uniformly over its box, grown to at least one cell in each direction; a cell's demand is the sum of the shares, each floored. `tracks` of a cell is its demand divided by `cell`, floored: the number of cell-long tracks it must carry. With a pitch (track width plus clearance of the class `Default`) no larger than `cell`, `tracks_per_layer` is `cell` divided by the pitch, floored, and `layers_needed` counts the cells that carry a track by the layers they need, `tracks` divided by `tracks_per_layer` and rounded up; otherwise both are `null`. `busiest`: the five cells of most tracks, by position, in the frame of `place()`.
   - The reply is bounded: five nets and five cells whatever the board's size.
   - Rejected: a single peak, which measurement 2 shows to be blind. Rejected: a router model; the router is the judge, and the estimate only compares placements of one board. Rejected: a ratio in a float; counts and lengths are integers.

8. **`check` gains the default stage `placement.rules`, in both pipelines.** In `STAGE_ORDER` it runs after `copper.clearance` and after c0106's `length.rules` when that exists, before `zone.fill`. In `DOCUMENT_STAGES` it runs after `copper.clearance` and before `parity`. It is not an oracle stage and runs no subprocess.
   - Inputs: the board model of the run (`Validation.read.design`, or the PCB reading of the documents), pads from the validator as `BoardFrame`, the class `Default` from it as `DesignRulesSource`, and the rules of the `.fenolite/` model of a built project.
   - Native input: the measures only. Built input: rules and measures. Skips: `read-refused`; `cache-unreadable` when the built project's cache failed to load; `no-frame` when the validator gives no board frame; on document input also `single-source` without a PCB document, as the copper stage there.
   - Status `errors` when a finding has severity `error`, so `check` exits 5. Summary: `rules` (the counts of `judge`) and `measures`.
   - Evidence: that of the reading when no rule was judged, so the measures lower nothing; combined with `checks.placement.EVIDENCE` (`INFERRED`) when one was.
   - Rejected: findings inside `copper.clearance`, whose status and evidence mean copper. Rejected: an opt-in stage; a rule that a default `check` does not judge does not gate a board. Rejected: the stage on KiCad input only (Decision 13).

9. **`place` judges rules and reports measures, and refuses only for legality.**
   - It loads `.fenolite/` once, for locks and rules.
   - The legality check gets the board's keep-outs. Rules are judged on the layout after the moves; every finding is at most a warning and never refuses the write. `result.rules` holds the counts.
   - `result.measures` holds the measures after the moves, and `change`: `hpwl` and `ratsnest` after minus before, in nanometres, when a part moved. The pitch comes from `KicadBackend().design_rules` on the board's copy set.
   - Evidence: `placement.EVIDENCE`, combined with `legality.KEEPOUT_EVIDENCE` when the board holds a keep-out that forbids footprints, and with `checks.placement.EVIDENCE` when a rule was judged.
   - Rejected: refusing `place` for a `near` finding. The grid ignores rules by design and would refuse its own output; `check` is the gate.

10. **`build`'s placement guard judges keep-outs and rules.** It passes the planned board's keep-outs to the legality check and runs `judge` with the rules of the built model, every finding at most a warning; `result.placement` gains `rules`. It reports no measures: `check --stages placement.rules` gives them without `kicad-cli`, and the reply of `build` stays as large as it is.
    - Rejected: refusing a build for a rule finding. A first build stages every part without `place()`, and c0022 (Decision 9) already keeps placement findings at warnings for that reason.

11. **How the rules feed the placer of v0.5a.** The rules are model data, so the annealing placer of the roadmap reads them as its inputs:
    - hard constraints: the legality check (overlaps, outline, edge clearance, keep-outs), and c0140's height limits when they exist; a move that breaks one is rejected;
    - cost: `hpwl` of `measure`, the wire length that plan D11 names as that placer's cost, plus a penalty per `near` rule that grows with the distance beyond `within`, plus the cells that need more layers than the board has;
    - acceptance: on c0119's board with its rules, no error of `placement.rules` and a `hpwl` no larger than the script's own placement, instead of the 40-part board of the plan.
    - The placer sits in `placement`, which may not import `checks`. The v0.5a change moves `judge` and `measure` into `placement` and gives `checks` the edge to it, or keeps them and gives `placement` the edge; `checks.placement` imports nothing that blocks either.
    - Rejected: a greedy "next to its anchor" step in the grid now. It is a placer by another name, which the roadmap gives v0.5a, and it would change the grid's contract.

12. **Changes in flight** (checked on 2026-10-05, and again at `origin/dev` `9aba2dff` on 2026-10-07).
    - The three requirements this change modifies ("Placement legality", "Place command", "Placement legality in a build") read on `dev` as they did when the deltas were made, and no open change on `dev` holds a delta of any of them. The deltas here are the living texts with this change's edits.
    - c0096 is not on `dev` and holds its own full MODIFIED "Place command". It lands first; this change then regenerates that delta ("Relation to c0096").
    - c0103 (a proposal of v0.4) gives `rule_area`, `FORBID`, `Keepout.name` and the area names; its text lists four `forbid` values, fixes `no_footprints == False` and refuses `forbid=("footprints",)` in a scenario. c0103 lands first. "Placement keep-outs in the DSL" is ADDED here because "Rule areas in the DSL" is not living on `dev`; when it is, task 0.1 turns it into a MODIFIED of that requirement, regenerated from the living text with three edits (the `forbid` list, the `no_footprints` clause, the refused call of the scenario), so that no two MUSTs disagree. If c0103 is not on `dev` when this change starts, only task 3.3 waits; legality still judges keep-outs drawn in KiCad, whose `no_footprints` the model reads today.
    - c0106 inserts `length.rules` right after `copper.clearance`; `placement.rules` follows it. Whichever lands second states the order in its stage-order scenario.
    - c0104, c0105 and c0114 add fields to `RuleSet` and regenerate `rules.json`. The schemas are generated, so the later one regenerates; the fields do not overlap.
    - c0102 builds holes as parts with courtyards on both sides (the maintainer's decision 2 of 2026-10-07 gives `hole` to c0102); they are judged by keep-outs like any part.
    - c0088 and c0090 (open on `dev`, closed by `0.3.0`) hold "Document check pipeline". This change does not modify it: "Placement rules stage" adds the stage to `DOCUMENT_STAGES` by name, as it adds it to `STAGE_ORDER`, so it lands after that requirement is living (Prerequisites).
    - c0062 and c0072 are archived; "Check stages and statuses" allows a later change to insert a stage, and this change adds its stage through an ADDED requirement and modifies nothing there.
    - c0066: `check` pages its `issues`, the new findings included; the new keys of `place` are bounded.
    - c0140 lands after this change and extends its stage and reports by ADDED requirements.
    - Rejected: asking c0103 to take the `footprints` value now. c0103 leaves it here on purpose (its Decision 1), and taking it back would make that change judge placement.

13. **The second backend.** Nothing new is silent in an Altium build or on Altium input.
    - *Rule table.* A `near` rule is no `RuleKind` (Decision 1), so `rulemap.TABLE` gains no row and refuses nothing.
    - *Build.* `build --target altium` stores `RuleSet.proximity` in `.fenolite/rules.json` like any model data. It runs no placement guard, which the living requirement says and this change keeps; its reply says so in one `altium.not-lowered` info of kind `placement-rule`, outside `LOSS_KINDS`, naming the count and that `check` judges them. The info is given where the Altium build counts what it does not write, `backends/altium/lower.py` on `dev`; task 0.1 confirms the place.
    - *Check.* `placement.rules` is in `DOCUMENT_STAGES`, so `fenolite check` on a built Altium project judges the `near` rules on the pad positions of the written `.PcbDoc` (`AltiumBackend.board_pads`) and gives the measures; on documents Fenolite did not build it gives the measures only. The pitch is that of a class `Default` when the document's rules give one, else `None`, and the congestion counts by layer are then `null`.
    - *Keep-outs.* `forbid=("footprints",)` in an Altium build: the area itself goes where c0103 sends any rule area; the restriction on footprints has no fact row in `docs/formats/altium/`, so it is reported in one `altium.not-lowered` info of kind `keepout-footprints`, outside `LOSS_KINDS`, naming the areas. On Altium input no stage judges a part in a keep-out: `place` reads KiCad boards, and `checks` may not import `placement.legality`. `docs/altium.md` says so.
    - *Evidence.* The stage combines the evidence of the reading, so a verdict on Altium input is never above the import's level.
    - Rejected: the stage on KiCad input only. A script built for both targets would have its `near` rules judged on one and silently not on the other.
    - Rejected: a placement guard in the Altium build in this change. It is a second legality path (the Altium board frame, the outline of a document) with its own tests; it can follow when `place` reads documents.

14. **Explain entries and the model key.** Tasks 4.1 and 5.1 add the tables of the five codes to `src/fenolite/cli/data/explain.toml` with the codes. Task 2.1 writes into `docs/design-model.md` that `proximity` is omitted when empty, so every output of 0.2.0 keeps its bytes, and that 0.2.x and 0.3.0 cannot read a `rules.json` that carries the key (the rule of `docs/roadmap.md`, decision 32).

## Relation to c0096

c0096 (`codex/c0096-constrained-placement`, implemented on its branch, not on `dev`) adds `--strategy constrained` to `place`. Its design lists eight rows against c0102, c0103 and this change and leaves them to the coordinator. The maintainer decided on 2026-10-07 (decision 2): this proposal wins, and c0096 adapts. For the rows that touch this change:

| row of c0096 | c0096 as implemented | what holds |
|---|---|---|
| 3. a part in a keep-out | `place.constraint` (error), located at the board, touching counts | **`place.keepout`, the predicate of Decision 5, backed by KiCad's DRC (`H-K-PLACE-KEEPOUT`): located at the reference, courtyard interiors must intersect, touching does not count, faces by copper layer; `place.keepout-no-courtyard` for a part without a courtyard.** c0096's constrained checker calls `placement.legality.check(…, keepouts=…)` for this verdict and gives it under this code. `place.constraint` stays c0096's code for the hard constraints that are only its own (a group region, a reservation, a drill); it no longer reports a part in a rule area that forbids footprints |
| 5. distance between pads | `PlacementObjective`, exact pad ids, distance rounded up, `place.objective` (warning) | `near` is the persistent rule of the design and `placement.too-far` its finding; `PlacementObjective` stays the cost of c0096's search. Both print the pad-centre distance rounded up to the nanometre (Decision 2). No conversion from a rule to an objective is in this change (Open Questions) |
| 6. heights | request `MechanicalVolume`, `MechanicalConstraints` | not this change any more: c0140 |
| 7. the command | a full MODIFIED "Place command" with `constrained`, `--constraints`, `--max-candidates`, `--preview-dir`, `result.placement`, `result.preview` | one requirement, composed as below |
| 8. the word `anchor` | `Part.place(…, anchor=…)`, `Placement.anchor` | no identifier shared (Decision 2) |

**Which lands first.** c0096 lands first (it is implemented; the review's order puts the three changes of board authoring before the proposals of the complex board). The delta of "Place command" in this folder is made from the living text of `dev` at `9aba2dff`, which has no `constrained`. When c0096 is on `dev`, task 0.1 regenerates the delta from the then living text and applies this change's edits again:

- the signature keeps c0096's `--strategy grid|manual|constrained` and its three options;
- **Rules of a built project**, **Rules**, **Measures** and **Evidence** hold for every strategy: after a constrained placement the rules are judged and the measures given like after any other;
- **Grid** (the boxes of keep-outs that forbid footprints join the cut-outs) is the grid's;
- **Legality** with `keepouts` holds for grid and manual as c0096 words it ("For grid/manual"), and c0096's paragraph on `constrained` gains the sentence that its checker gives a part in such a keep-out as `place.keepout`;
- **Result**: one contract. `board`, `strategy`, `moved`, `unplaced`, `legality`, `rules` and `measures` for every strategy; `placement` and `preview` for `constrained` only, as c0096 has them. `build` keeps its own `result.placement` (`ran`, `counts`, `rules`), a key of another command;
- c0096's scenario "Constrained dry-run then confirmed placement" is kept, and one scenario is added: a constrained request that would put a part into a keep-out reports `place.keepout` at the part.

If this change were to land before c0096, c0096 regenerates its delta from the text this change leaves, by the same list.

**Code.** Task 4.2 exists only when c0096 is on `dev`: it changes `cli/placement_checks.py` so that the keep-out verdict of the constrained strategy comes from `placement.legality.check`, removes the keep-out case from what gives `place.constraint`, and updates the entry of `place.constraint` in `explain.toml`.

**Not this change's:** `Design.keepout()` against `rule_area` (c0103), `Design.hole` (c0102), a pad in a keep-out (`copper.keepout`, c0103).

## Files and public API

| file | content |
|---|---|
| `src/fenolite/model/rules.py` | `PlacementSeverity`; value objects `PadSelection(path, number="", index=None)`, `ProximityRule(name, parts, anchor, within, severity="error")`; `RuleSet.proximity` |
| `schemas/fenolite.model.v0/rules.json` | regenerated |
| `src/fenolite/dsl/design.py` | `Design.near(key, parts, anchor, *, within, severity="error")` |
| `src/fenolite/dsl/convert.py` | rules in `to_model` |
| `src/fenolite/dsl/items.py` (c0103) | `footprints` in `FORBID` |
| `src/fenolite/placement/legality.py` | `check(…, keepouts=())`; `KEEPOUT_EVIDENCE` |
| `src/fenolite/placement/codes.py` | `place.keepout`, `place.keepout-no-courtyard` |
| `src/fenolite/checks/placement.py` (new) | `EVIDENCE`; `board_box(design)`; `PlacementRules`, `rules_of(model)`; `RuleReport`, `judge(design, rules, *, pads)`; `Measures`, `measure(design, *, pads, pitch=None)`; `placement_stage(…)` |
| `src/fenolite/checks/stages.py`, `checks/documents.py`, `checks/codes.py` | `placement.rules` in `STAGE_ORDER` and in `DOCUMENT_STAGES`, the skip `no-frame`; three `placement.*` codes |
| `src/fenolite/cli/cmd_place.py`, `cli/cmd_build.py` | Decisions 9 and 10 |
| `src/fenolite/cli/placement_checks.py` (c0096, when on `dev`) | the keep-out verdict of the constrained strategy from `placement.legality.check` |
| `src/fenolite/backends/altium/lower.py` | the kinds `placement-rule` and `keepout-footprints` of `altium.not-lowered`, neither in `LOSS_KINDS` |
| `src/fenolite/cli/data/explain.toml` | one table for each of the five codes |
| `tests/unit/model/test_rules.py`, `tests/unit/dsl/test_placement_rules.py`, `tests/unit/placement/test_legality.py`, `tests/unit/checks/test_placement_rules.py`, `test_placement_measures.py`, `test_placement_stage.py`, `tests/unit/cli/test_place_cmd.py`, `test_build_placement_guard.py`, `test_check_altium.py`, `test_build_altium.py` | unit tests |
| `tests/kicad/place/_keepoutcases.py`, `test_place_keepout.py` (new) | the 18 cases of measurement 1 and their probes |
| `docs/placement.md`, `docs/dsl.md`, `docs/cli-contract.md`, `docs/design-model.md`, `docs/altium.md`, `docs/formats/kicad/board.md` | rules, keep-outs, measures, the stage on both inputs, the codes, the model key and its compatibility sentence; the keep-out facts with `H-K-PLACE-KEEPOUT` |

No file under `tests/data/` is added: every bench and layout is written by its test.

## Sources registered by this change

| id | source | licence | used for |
|---|---|---|---|
| S-0680 | https://portal.fis.tum.de/en/publications/fast-and-accurate-routing-demand-estimation-for-efficient-routabi/ (the record of "Fast and accurate routing demand estimation for efficient routability-driven placement", DATE 2007) | bibliographic record; the idea only, nothing copied | a rectangular uniform wire density per net as an estimate of routing demand |

The proposal first reserved S-0390, which `dev` gave to another page (a package drawing). S-0680 is the first id of the block S-0680–S-0699 handed to this group on 2026-10-07 (`dev` ends at S-0601; c0115 holds S-0681 and S-0682). The KiCad facts rest on S-0020 and S-0029, the two `kicad-cli` oracles already registered, and on S-0010 for the constraint types.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-PLACE-KEEPOUT | A rule area with `(footprints not_allowed)` makes `pcb drc` report `items_not_allowed` naming a footprint exactly when the interior of its front courtyard meets the area's interior and the area's layers hold `F.Cu`, or of its back courtyard and `B.Cu`: an overlap of 10 µm is reported; an area edge on the courtyard's line centre and gaps of 10 and 30 µm are not; an area on inner layers only, a footprint without a courtyard and silkscreen outside the courtyard are never reported (S-0020, S-0029) | `tests/kicad/place/test_place_keepout.py` | each probe `place-keepout-<case>` gives the outcome of measurement 1 on 9.0.9 and 10.0.6 with the canary firing, and `place-keepout-agree` is `equal`: the legality check gives the same verdict as the DRC in every case |

`H-K-PLACE-KEEPOUT` is free in `docs/hypotheses.md` at `9aba2dff`. It starts `INFERRED`, with measurement 1 as its first record. Ids used without changing their level: `H-K-PLACE-TOUCH`, `H-G-FRAME-CRTYD-2`, `H-G-ROT-DIR`, `H-G-BOTTOM-PLACE` (pad positions), `H-K-AREA-KEEPOUT` (c0103, when it is on `dev`).

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| `place.keepout` agrees with KiCad's DRC | KICAD-VERIFIED (9.0.x, 10.0.x) | `H-K-PLACE-KEEPOUT` |
| `near` rules | INFERRED: Fenolite's rules, which no oracle judges; pad positions rest on the verified rows above on KiCad input and on the import's level on Altium input | unit tests on authored layouts |
| measures | mechanical definitions on the board frame | unit tests with values computed by hand; the 600-part check of task 6.3 |
| grid avoidance, DSL, model, stage wiring on both pipelines | mechanical | unit tests |

## Risks / Trade-offs

- **Hundreds of findings.** 300 decoupling rules on a first placement give 300 `placement.too-far`. Mitigation: `check` pages its issues (c0066), and `--format concise` keeps one per code with a count.
- **Rules of the last build.** `place` and `check` read `.fenolite/`; a rule changed in the script applies at the next build. The reply names the rule, so a stale one is visible.
- **The congestion number read as a verdict.** It is documented as an estimate for comparing placements of one board; the router decides.
- **Conservative grid.** Areas are avoided by their boxes, so a board with large areas leaves more parts staged (`place.no-room`).
- **A slower `check`.** The stage reads the pads again, about 2 s at 600 parts; the measures add 0.25 s (measurement 3).
- **Agreement on two majors only.** A later KiCad that judges keep-outs otherwise fails `test_place_keepout.py` before the code drifts.
- **Two changes on one command.** "Place command" is modified by c0096 and by this change; the order and the composition are written above, and task 0.1 regenerates.

## Migration Plan

- Additive for scripts: without the new calls, `to_model` gives equal models and builds write equal bytes, since an empty `proximity` is left out of the canonical form. Every output of 0.2.0 keeps its bytes.
- The other direction does not hold: 0.2.x and 0.3.0 cannot read a `rules.json` that carries `proximity`. `docs/design-model.md` says so.
- `check` runs one more default stage, on KiCad projects and on Altium documents. On a built project with rules it can now exit 5.
- `place` refuses a move into a keep-out that forbids footprints unless `--force`, and its grid leaves such areas free. `CHANGELOG.md` says both.
- Rollback: drop the stage from `STAGE_ORDER` and `DOCUMENT_STAGES`, the keep-out branch from legality and the DSL call; the model field can stay empty.

## Budget (5.5 days)

| part | days |
|---|---|
| entry check, registers, keep-out cases and probes on both majors | 0.75 |
| model: value objects, `RuleSet.proximity`, schema, the compatibility sentence | 0.25 |
| DSL: `near`, `footprints`, conversion | 0.5 |
| legality: keep-outs and codes; c0096's checker when it is on `dev` | 0.5 |
| `judge`: `near`, unresolved and skipped rules | 0.5 |
| `measure`: HPWL, spanning tree, congestion; the 600-part check | 0.75 |
| the stage `placement.rules` in `run_checks` | 0.5 |
| the stage on document input, the two Altium infos | 0.25 |
| `place`: grid avoidance, rules, measures, evidence | 0.5 |
| `build`'s guard | 0.25 |
| documentation, explain entries and closing | 0.75 |

The proposal had 6.5 days with heights; c0140 carries their part. Cut order: (1) congestion (−0.4); (2) `change` in `place` (−0.1); (3) the spanning tree, keeping `hpwl` (−0.15). Never cut: `near` and its check on both inputs, keep-outs agreeing with KiCad under one code, wire length in `place` and `check`.

## Open Questions

- **Default severity of `near`.** Default: `error`, so `check` gates a declared rule; `severity="warning"` is one argument away.
- **A `near` rule as an objective of c0096's search.** A rule that names one pad on each side maps to one `PlacementObjective` with `within` as its maximum. A rule over several pads means "one of them", which c0096's objective, a list of exact pad ids, cannot say. Default: no conversion here; the constrained strategy judges the rules after its moves like every strategy. A later change decides the mapping.
- **A `PinHandle` in `near`.** c0123 (on its own branch) gives a component `pads_of(pin)`. Default: the refusal stays, with its hint; if c0123 is on `dev` when task 3.1 starts, the task records it and a `PinHandle` may be accepted by a later edit of "Placement rules in the DSL".
- **A greedy "next to its anchor" step in the grid.** Default: no (Decision 11); the placer of v0.5a.
- **Measures in `build`'s reply.** Default: no (Decision 10).
- **Rules for a board without a script**, in a file beside the board. Default: no; nobody asked, and the files of neither backend can hold them.
- **Options for the cell size and the pitch.** Default: none; 2 mm cells and the class `Default`.
- **Keep-outs judged on Altium input.** Default: no (Decision 13); it needs `place`, or a legality stage, on documents.
