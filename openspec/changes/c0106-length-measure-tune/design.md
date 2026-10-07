## Context

- **Scope.** The review of 2026-10-05 named the gaps to a complex board; since 2026-10-07 the group is milestone v0.4 (`docs/roadmap.md`, "Milestone names" and "v0.4: proposals on other branches", where the row of c0106 holds its id and slug only). The gap this change closes, in the review's words: "pin-to-pin length with vias, and skew within a pair (the v0.6 analysis, pulled forward); meander generation, which can be cut". It takes the v0.6 line "matched-length and skew analysis", which `docs/roadmap.md` still holds at `9aba2dff` (the Phase 5 table and the table of proposed cuts), and adds the generator that no line owned.
- **What exists** on `origin/dev` at `9aba2dff` (2026-10-07):
  - c0066 (archived 2026-10-06): `analysis.views.net_list` gives `NetRow.length`, the sum of the centre lines of a net's tracks and arcs; `net_view` gives the same per layer. `views.arc_length(arc)` computes r·θ in fixed point (2¹⁶⁰) and `views._distance` rounds a square root to the nearest nm. Nothing counts vias, die lengths or a path between pads. `fenolite net` prints that sum.
  - c0089 (archived 2026-10-07): `checks/equivalence/routing.py` holds a second implementation, `arc_length(start, mid, end)` with 128 fractional bits and `_distance(a, b)`, for the routed length per copper span of equivalence level 5 (`equiv.route-length`). It has the signature this change gives the kernel function. For collinear points with `mid` between the ends it returns the two straight parts, and for points the arc shape refuses (two of them equal, or `mid` outside the ends on their line) the distance of the ends; `views.arc_length` does the same for both inputs. It counts no via height, no die length and no zone fill, so its span lengths are sums of the same per-item lengths as `NetLength.routed`.
  - c0047 (archived): the package `analysis`, its closed code table `analysis.codes.ISSUE_CODES`, `AnalysisReport` (rows typed `CurrentRow | DistanceRow`), and `fenolite analyze` with the kinds `current`, `clearance` and `creepage`, which judge measures against a requirements file.
  - The kernel has `Segment.length2` and no length function (`geometry/shapes.py`).
  - The model has `Board.stackup: Stackup | None` (`StackLayer(name, kind, thickness, …)`). The KiCad reader never fills it: a board file with a stack-up reads back with `stackup is None`, and the writer writes only `(general (thickness …))`, 1.6 mm without a stack-up (`pcb.DEFAULT_THICKNESS`). `Pad` has no die length; the reader keeps `(die_length 1.5)` as an opaque slot of the pad and writes it back unchanged.
  - Rules: `RuleKind` holds the twelve kinds of c0071, no `length` or `skew`; c0104 adds them. `checks.clearance.rule_precedence` gives KiCad's rule order (c0018). The token inventory holds `rules-type-length`, `rules-type-skew` and `rules-within-diff-pairs` since 9, and `pad-die-delay` since 10 (time-domain tuning). Both project templates hold `use_height_for_length_calcs: true`.
  - `checks.stages.STAGE_ORDER` is `model.validate`, `erc.kicad`, `copper.clearance`, `zone.fill`, `drc.kicad`, `parity`, `netlist.assignment_compare`, `roundtrip`, `roundtrip.rt2`, `render` (c0062 and c0072 are archived); `copper.clearance` runs no tool. Document input (Altium files, c0088, implemented on `dev`) runs a second list, `checks.documents.DOCUMENT_STAGES`: `model.validate`, `erc.lite`, `copper.clearance`, `parity`, `netlist.assignment_compare`, `roundtrip.rta0`, `roundtrip.rta1`, `roundtrip.rta2`.
  - Script copper (c0028, c0068): track intents of points, pad ends, via steps of the four kinds and arc steps; every created item carries `copper_uuid(key, locator)`, and `lens.preserve.merge_layout` carries items with a copper uuid from the built design into the merged layout. `lens.build.build_design` calls `resolve_copper` on the fresh design, before the merge with an existing board.
  - Layering: `checks` and `analysis` import `model`, `geometry` and `backends.base` only and neither imports the other; `backends.<x>` and `lens` cannot import `analysis`.
- **The proposals this change builds on** (v0.4 proposals, not on `dev`; read as proposed on 2026-10-07; task 0.1 re-checks them once they are archived). c0104 keeps a pair as an `Interface` whose kind is a key of `model.pairs.PAIR_ROLES` (`diff_pair`, `usb2`), adds `RuleSubject.diff_pair` and the selector leaf `diff_pair <base>`, and the rule kinds `length` (`min`, `opt`, `max`), `skew` (the nets a rule selects against the longest of them) and `diff_pair_skew` (the two nets of each pair), all written as KiCad's `skew` or `length` constraint, with `opt` written and not checked. c0101 projects a stack-up node that KiCad uses into `Board.stackup`, mask, silkscreen and paste rows included, adds `Stackup.depth` and `Stackup.between`, holds no thickness without a node, and measured KiCad's default stack-up in the job file for 2 to 8 copper layers (`H-K-STACKUP-DEFAULT`).
- **Measured on 2026-10-05.** Benches built through the model and `write_board`, with a `{}` project file unless said, and one rule per net `(constraint length (max 0.001mm))` with the condition `A.NetName == '<net>'`, so that KiCad reports the net's length as the `actual` of a `length_out_of_range` violation. `kicad-cli pcb drc --format json --severity-all --units mm`, 10.0.6 locally and 9.0.9 in the pinned image. Tracks 0.25 mm; the pads of `Mini_R_0603` are 0.9 mm × 0.95 mm. KiCad prints four decimals of a millimetre.

  1. *Two layers, a 1.6 mm board written without a stack-up* (mm):

     | case | tracks and arcs | 10.0.6 | 9.0.9 |
     |---|---|---|---|
     | pad centre to pad centre | 18.4 | 18.4 | 18.4 |
     | pad edge to pad edge | 17.5 | 17.5 | 17.5 |
     | two collinear segments | 18.4 | 18.4 | 18.4 |
     | 4.2, a half circle of radius 3, 8.2 | 21.8248 | 21.8248 | 21.8248 |
     | a track through a pad, ending 0.8 mm beyond its centre | 19.2 | 19.2 | 19.2 |
     | 18.4 between two pads, a 5 mm stub to a third pad | 23.4 | 23.4 | 23.4 |
     | pad centre to pad centre, `(die_length 1.5)` on one pad | 18.4 | 19.9 | 19.9 |
     | through-hole pads, F.Cu | 20 | 20 | 20 |
     | 10 on F.Cu into a through-hole pad, 10 on B.Cu out of it | 20 | 20 | 20 |
     | 10 on F.Cu, a through via, 10 on B.Cu | 20 | 21.58 | 21.545 |
     | the same, stack-up of 35 µm, 1230 µm, 35 µm in the file | 20 | 21.3 | 21.265 |
     | the same, `use_height_for_length_calcs: false` | 20 | 20 | 20 |
     | top pad, via, pad of a bottom-side part | 18.4 | 19.98 | 19.945 |

  2. *Four layers: the height one via adds between 10 mm tracks* (µm). "Default": the file holds no stack-up. "Explicit": F.Cu 35, dielectric 110, In1.Cu 17.5, dielectric 1230, In2.Cu 17.5, dielectric 155, B.Cu 35.

     | copper of the net at the via | 10.0.6 default | 10.0.6 explicit | 9.0.9 default | 9.0.9 explicit |
     |---|---|---|---|---|
     | F.Cu, In1.Cu | 532.5 | 153.75 | 0 | 0 |
     | F.Cu, In2.Cu | 1047.5 | 1401.25 | 0 | 0 |
     | F.Cu, B.Cu | 1580 | 1600 | 1545 | 1565 |
     | In1.Cu, In2.Cu | 515 | 1247.5 | 0 | 0 |
     | In1.Cu, B.Cu | 1047.5 | 1446.25 | 0 | 0 |
     | F.Cu, In1.Cu at a blind via F.Cu–In1.Cu | 532.5 | 153.75 | 515 | 136.25 |
     | F.Cu only (both tracks) | 0 | 0 | 0 | 0 |
     | F.Cu, In1.Cu and B.Cu at one via | 1580 | 1600 | 1545 | 1565 |
     | two vias in series, F.Cu, In1.Cu, B.Cu | 1580 | 1600 | 0 | 0 |

     The explicit values are printed rounded (153.7, 1401.3, 1446.2, 136.3); the rows of the table are the values the rules below give, which round to the printed ones.
  3. *Four layers, explicit stack-up, pads at vias* (mm): a via in each end pad and the track on In1.Cu (18.4 of track): 18.7075 on 10.0.6, 18.4 on 9.0.9; a dog-bone (1 F.Cu, via, 16.4 In1.Cu, via, 1 F.Cu): the same two values; an F.Cu track of 18.4 to a via in a pad of a bottom-side part: 20.0 and 19.965; an F.Cu track of 10 to a via whose In2.Cu copper is a stored zone fill of its net: 10 on both, the fill reported as `isolated_copper`.
  4. *Rules, identical on both majors.* `skew (max 0.1mm) (within_diff_pairs)` with `A.inDiffPair('SK')` on `SK_P` (20 mm) and `SK_N` (21 mm): one violation, on `SK_P`, "actual -1.0000 mm; target net length 21.0000 mm (from SK_N); actual 20.0000 mm". `skew (max 0.1mm)` with `A.NetName == 'BUS*'` on 20, 21 and 23 mm: −3 mm on `BUS0`, −2 mm on `BUS1`, nothing on `BUS2`. `length (min 5mm) (max 50mm)` on a 2.4 mm net: "min length 5.0000 mm; actual 2.4000 mm"; on a net of two pads and no copper: "actual 0.0000 mm". `length (opt 5mm)`, alone or with `(max 50mm)`, on a 2.4 mm net: no violation. A skew group holding a net of pads only reports it at length 0.
  5. `pcb export stats --format json` holds no net length. The `actual` of a violation is the only headless readout of KiCad's length.

  What the numbers show, on both majors unless said:
  - KiCad's length of a net is the sum of the centre lines of all its tracks and arcs (stubs and dangling copper included), plus a height per via, plus the die length of each of its pads. A track counts from its end inside a pad, not from the pad edge. A through-hole pad adds no height. A zone fill is not copper a via joins.
  - *Depths.* On 9.0.9 the depth of every copper layer is the thickness of the copper and dielectric layers above it plus half its own. On 10.0.6 the same holds for inner layers, while the first copper layer starts at its outer face (depth 0) and the last ends at its outer face (the sum of every copper and dielectric thickness). Masks do not count.
  - *Via height, 10.0.6*: the depth difference between the outermost two copper layers on which a track, an arc or a pad of the net touches the via; 0 with fewer than two. *9.0.9*: the depth difference between the via's own two end layers when the net touches the via on both, else 0.
  - *Default stack-up* (a file without one): copper layers of 35 µm, and dielectrics that share equally the board thickness less 20 µm of mask and the copper: 1.51 mm for two layers, 0.48 mm each for four, at 1.6 mm.
  - *Rules*: a length rule judges `min` and `max`, not `opt`; every net with a pad or copper is judged, a net of pads only at length 0. A skew rule groups the nets it governs, each pair apart with `within_diff_pairs`; each net's skew is its length less the longest of its group, reported when its magnitude exceeds `max`.

  The scripts, command lines and outputs are kept with the probes of the review; none is committed. Task 1.2 turns the benches into canaries. The measurements were made on the branch `review-roadmap-complex-board` and were not repeated on `dev`. The bench parts and nets (`Mini_R_0603`, `SK_P`, `BUS0`) and the layer thicknesses are authored for the benches, taken from no board of anyone.

## Goals / Non-Goals

**Goals**
- Fenolite gives, for any net, the length KiCad's DRC will judge, as the target major counts it, and the pin-to-pin lengths along its copper.
- The skew of each differential pair, and the verdict of c0104's length and skew rules, without `kicad-cli`.
- A script can bring a script track to a target length or to the length of another script track.

**Non-Goals**
- Everything under "Non-goals" in the proposal.
- Judging pair gap and uncoupled length in Fenolite: c0104 writes them for KiCad, whose DRC judges them headless; nowhere else for now.
- A model field for die lengths: nowhere for now, because the pad's opaque slot already holds the value (Decision 5).

## Decisions

1. **Two lengths per net: KiCad's total and the pin-to-pin path.** The total is what KiCad's DRC judges, so a verdict on it agrees with `drc.kicad`. The path is the length a signal travels from one pad to another; it differs from the total wherever the net has a stub, a branch or a fly-by load.
   - Rejected: the total only. A stub or a second load makes it longer than any signal path, and the report would hide it.
   - Rejected: the path only. KiCad judges the total; a Fenolite verdict on the path would disagree with KiCad on every net with a stub.

2. **The total is a KiCad fact, computed in the KiCad backend.** `backends/kicad/lengths.py` counts as each major counts, and gives `LengthFacts` through the protocol `LengthSource` of `backends.base`, as `DesignRulesSource` gives the clearance rules (c0029). `analysis` and `checks` reach it through the protocol and add no import edge; the meander resolver, in `backends.kicad`, calls the module directly.
   - Rejected: the total in `analysis`. The check stage could not import it without a new edge `checks → analysis`, and the per-major rules of one tool would live in a backend-free package.
   - Rejected: one tool-free total. Measurements 2 and 3 show that no single rule agrees with both majors on a board with an inner-layer via.

3. **Via heights follow the major the board is judged against.** The facts carry `major`: the argument when given; else the major of the project file, as the copper stage takes it (`copperrules.project_major`); else the board file's own; else the default target. `check` passes none; `analyze` passes the global `--kicad-version` (`Context.kicad_target`, 10 by default), which every command takes, so no option of the same name is added. On 10 a via adds the depth difference of the outermost joined layers; on 9 its own span when both of its ends are joined; depths follow the major's convention (Context).
   - Rejected: a physical via length (one convention for both majors). It agrees with neither: 10.0.6 counts outer copper whole and 9.0.9 counts nothing for a through via that the net does not reach on both ends.

4. **Stack-up from c0101, else KiCad's default.** The depths come from the copper and dielectric entries of `Board.stackup` (c0101) when the model holds one. Without it they come from the default stack-up both majors use (measurements 1 and 2), built from the board thickness, and `stackup` says `default` with one `kicad.length.default-stackup` info. The thickness is the `(general (thickness …))` of the file, an opaque slot the reader keeps, else `pcb.DEFAULT_THICKNESS`, the value the writer writes. It is what KiCad counts, not a value Fenolite assumes, and the reply says so; c0101 keeps it out of the model, and the facts do not put it there.
   - Rejected: no via height without a stack-up. Today every created board has none, so every total with a via would disagree with KiCad.
   - Rejected: writing the default stack-up into the model. What the model holds after a read is c0101's to say; the facts only count.
   - The default is measured for lengths on 2 and 4 copper layers. c0101 found the same formula in the job file for 6 and 8 layers; task 1.3 measures lengths there once c0100 builds such boards, and until then their facts stay `INFERRED`.

5. **Die lengths from the pad's opaque slot.** KiCad adds `(die_length X)` of every pad of the net (measurement 1). The reader keeps the token opaque, so `lengths.die_lengths` reads it from the pad's slot and keys it by pad id; nothing in the model changes.
   - Rejected: `Pad.die_length` in the model. It is a schema change for a value no script can set yet; a later change can lift it together with a DSL setter. Rejected: ignoring die lengths: the total would disagree with KiCad on every board that holds one.
   - `die_delay` (10 only) is a time; it is not read (proposal, Non-goals).

6. **The project switch.** With `use_height_for_length_calcs: false` KiCad counts no via height (measurement 1). The facts read it from the project file of the `ProjectSet` they are given (`count_vias`); without a project file, or without the key, heights count, as both templates and a `{}` project do.
   - Rejected: ignoring the switch. A project that turns heights off would get totals that KiCad does not judge.

7. **Pin-to-pin paths: a graph of item ends.**
   - Nodes are item ends on a layer, vias and pads. An end joins a track, an arc, a via or a pad when it lies within that item's copper on a shared layer (`thick_touch` of the point and the shape). An end inside the body of a track or arc, not at its ends, splits that item at the point of its centre line nearest to the end. A pad whose copper touches the body of an item that has no end inside the pad joins it at the point of the item's centre line nearest to the pad's position (the track through a pad of measurement 1). Items that only cross are not joined.
   - Weights: an item, or a part of it, weighs its length (`segment_length`, `arc_length`, `arc_length_to`); a layer change through a via weighs the depth difference of the two layers (`facts.depths`); a layer change inside a pad weighs 0, as KiCad counts a through-hole pad (measurement 1). A path adds the die lengths of its two end pads.
   - Paths run from a start pad (named by `--from`, else the first pad of the net) to every other pad, by Dijkstra on integers; equal paths are told apart by the sorted ids of their items.
   - With 10 facts, the path of an unbranched net from pad to pad equals its total. With 9 facts a path through a through via that the net does not reach on both ends is longer than the total: KiCad 9 counts no height there. The report states both; the difference is documented, not hidden.
   - Rejected: connectivity by copper polygons, as KiCad builds it. It needs unions of pad and track shapes, which the kernel lacks (`geometry-boolean-backends` holds only the convex fallback). Rejected: lengths from the pad edge. KiCad counts the track inside the pad (measurement 1), and the path must equal the total on an unbranched net.

8. **Reported in `analyze` and in `check`.**
   - `fenolite analyze --kinds length --net GLOB [--from REF]` gives the measures, counted for the global `--kicad-version`: totals with their parts, paths, stubs and pair skews. It judges nothing: the limits are c0104's rules. The kind is opt-in, so `analyze` without `--kinds` behaves as "Analyze command" states.
   - The check stage `length.rules` judges c0104's `length` and `skew` rules on the totals, right after `copper.clearance` (so before `zone.fill` and `drc.kicad`), without a tool, as a default stage. A board without such rules gives an empty stage.
   - The stage is in `STAGE_ORDER` only. It is not added to `checks.documents.DOCUMENT_STAGES`: an Altium document holds no rule of the three kinds (the Altium reader maps none and the writer writes none, c0104), and the Altium backend is no `LengthSource`, so the stage could only ever be empty there. `fenolite check` on Altium input does not name it, and "Document stage order" of c0088 is not modified.
   - Rejected: `[[length]]` rows in the requirements file of c0047. They would be a second place for limits that c0104's rules already hold and KiCad already enforces.
   - Rejected: a separate command `fenolite length`. One read, one envelope, one place to look, as c0047 Decision 14 chose for its kinds.
   - Rejected: no stage, `drc.kicad` alone. It needs `kicad-cli`, which an agent may lack or find slow on a large board, and it reports only nets out of limits.

9. **Rule semantics are KiCad's.** The stage judges `min` and `max` of c0104's `length` rules and ignores `opt` (measurement 4); judges every net with a pad or copper, a net of pads only at length 0; and reports each net whose skew from the longest net of its group exceeds `max`, with KiCad's sign. c0104's `skew` and `diff_pair_skew` are both KiCad's `skew` constraint, so a net's governing skew rule is the last matching rule of either kind in `rule_precedence` order (c0018); a `skew` rule groups every net it governs, a `diff_pair_skew` rule each pair among them (`model.pairs`).
   - Rejected: judging `opt` as a limit, and leaving nets without copper out. KiCad does neither (measurement 4), so the stage would disagree with `drc.kicad`.

10. **Parity is proven by canaries, not at run time.** The canaries run each bench twice, with each net's `max` 1 µm below Fenolite's total (KiCad must report it) and 1 µm above (KiCad must not), and record the printed `actual` in the evidence page.
    - Rejected: comparing Fenolite's totals with KiCad's `actual` inside `check`. The `actual` is English text in a description, and a verdict would then depend on a message format.

11. **Meanders: a separate intent on one segment of a script track.** `Design.meander(key, *, track, segment, amplitude, pitch, target=None, match=None, side="left", margin=None)` names the straight segment `seg[segment]` of a track intent. `resolve_meanders` runs right after `resolve_copper` on the fresh design, replaces that track by the meander, and gives every new track `copper_uuid(key, "m[k]")`, so `merge_layout` carries and regenerates it as script copper on every build. Its codes are `kicad.meander.*` in `MEANDER_ISSUE_CODES` of its own module, so no living table changes, as c0068 did for `kicad.pad.*`.
    - Rejected: a path element `meander_to(…)`. It would modify "Copper intents in the DSL", "Tracks from intents" and "Copper issue codes", three requirements that c0068 modifies too.
    - Rejected: meanders on any copper of a net, router copper included. A router track split by a meander would have to be rejoined on every rebuild before it can be split again; that waits for routed pairs (c0110; Open Questions).
    - Rejected: KiCad's own tuner. It is interactive; no `kicad-cli` command runs it.

12. **Meander geometry.**
    - The run goes from the segment's start `P` to its end `Q`. Legs stand perpendicular to the run on the side `side` (`left` is the side where `orient2d(P, Q, X) < 0`, the left as KiCad displays the board), at the distances `margin + j·pitch` from `P`, `j = 0 … 2N − 1`; `margin` defaults to `pitch`. Bump `i` rises at leg `2i` to the height `h`, runs at that height to leg `2i + 1` and comes back. Every corner is square.
    - The target is the length the intent must have: `target`, or the length of the intent `match`. The length of an intent is the sum of its tracks and arcs, the heights of its via steps as the target major counts a via that only the two segments of the step join, and the die lengths of the pads its ends chose. So when an intent is the only copper of its net, its length is KiCad's total of that net.
    - With `E` the length to add, `N = ⌈E / (2·amplitude)⌉` bumps of height `E / (2N)`. They need `(2N − 1)·pitch + 2·margin` of run; a shorter run is refused, with the most it can add in the message.
    - Points are computed with 64 fractional bits and rounded half to even. The resolver then measures the intent and adds half of what is missing to the last bump's height, at most twice; a length still more than 10 nm from the target is refused. On a run parallel to an axis the first result is exact to 1 nm.
    - `match` uses the matched intent after its own meander; meanders are resolved in that order, and a cycle is refused.
    - Rejected: a fixed bump count with a computed amplitude. The band the script gives is the amplitude, so the count is what may vary. Rejected: rounded corners: they make every length irrational and gain nothing the checks see.

13. **Kernel lengths: one implementation where `dev` has two.** `segment_length`, `arc_length` and `arc_length_to` move into `geometry/lengths.py`, with the fixed-point arithmetic of `views.arc_length` (160 fractional bits). `views.arc_length(arc)` and `views._distance` then call the kernel, and so do `checks.equivalence.routing.arc_length` and its `_distance` (c0089), whose own copy of the arithmetic is removed. One implementation serves `views`, the equivalence level 5, the facts, the paths and the meanders.
    - The two copies of `dev` round the same exact value half to even, at 160 and at 128 fractional bits, so they agree wherever neither sits within 2⁻¹²⁸ nm of a half. Task 2.1 proves the agreement before the routing copy goes: on generated arcs and on every arc of the level-5 fixtures, the kernel equals the routing copy to the nanometre, so no `equiv.route-length` verdict moves.
    - The inputs that form no arc follow the two copies of `dev`: two straight parts for collinear points with `mid` between the ends, the distance of the ends for every input the arc shape refuses. The first draft of this change gave the two straight parts for every degenerate input, which differs from `dev` when `start == end` or when `mid` lies outside the ends; the kernel takes `dev`'s value, so neither `views` nor level 5 changes a number.
    - `NetLength.routed` and the span lengths of `equiv.route-length` are sums of the same per-item kernel lengths: the first over a net, the second over one copper span of one pad set. Neither holds a via height. `docs/analyses.md` and `docs/equivalence.md` say so in one sentence each.
    - Rejected: a second copy in `backends.kicad`, which cannot import `analysis`.
    - Rejected: leaving the routing copy alone. Three implementations of one length would let an arc measure differently in `net`, in `equivalent --level 5` and in `analyze --kinds length`.

14. **Changes in flight.** Every requirement of this change is ADDED and each of the fifteen names is free in the living specs of `9aba2dff`, so no delta is regenerated. Open changes on `dev` hold deltas in the same capabilities but of other requirements: c0088 MODIFIES "Document check pipeline" (`verification-loop`) and "Design rules source" (`backend-protocol`), and c0130 MODIFIES "Design rules source"; none shares a requirement with this change.
    - Rejected: modifying "Analyze command" and "Findings and issue codes" for the new kind and codes. c0115 may modify the same texts, and the second to archive would have to re-base; an ADDED requirement needs none, and "Analyze command" stays true because the kind is opt-in.
    - c0104 (dependency): the stage and the pair rows use its names as its proposal gives them (Context): the kinds `length`, `skew` and `diff_pair_skew`, `RuleSubject.diff_pair`, `model.pairs.PAIR_ROLES`, `pair_nets` and `net_bases`. Task 0.1 checks that they held at archive and adapts the stage and the scenarios if not.
    - c0101 (dependency for depths): `Board.stackup` as its reader projects a node KiCad uses; the depths skip its mask, silkscreen and paste entries, and `Stackup.depth` may compute them. A node its reader does not project leaves the default of Decision 4 (Risks).
    - c0100: inner layer names and boards of 6 and 8 layers; task 1.3 measures the default stack-up there.
    - c0066 is archived: `views.arc_length` calls the kernel and gives the same values; "Board views" holds unchanged.
    - c0089 is archived: `routing.arc_length` calls the kernel (Decision 13); its requirements in `design-equivalence` hold unchanged, and task 2.1 runs its level-5 tests.
    - c0088 (open on `dev`, implemented): its `DOCUMENT_STAGES` does not gain `length.rules` (Decision 8).
    - c0123 (its own branch, several pads per pin): it changes which pads carry a pin's number; the start-pad rule of "Pin-to-pin length" sorts pads by `(ref, number)` and takes the first, which stays defined, and whichever of the two changes lands second adds a scenario with two pads of one number.
    - c0068: meanders read the locators `seg[i]`, `arc[i]` and `via[i]` of its track intents.
    - c0062 and c0072 are archived; they inserted `parity` and renamed `erc.lite` to `erc.kicad`. `length.rules` stands right after `copper.clearance`, which neither moved.
    - c0115 may add analysis kinds and codes; both changes add through ADDED requirements, so neither re-bases.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/geometry/lengths.py` (new) | `segment_length(a, b) -> int`, `arc_length(start, mid, end) -> int`, `arc_length_to(start, mid, end, at) -> int`; re-exported by `fenolite.geometry` |
| `src/fenolite/analysis/views.py` | `arc_length(arc)` and the track lengths call the kernel |
| `src/fenolite/checks/equivalence/routing.py` | `arc_length` and `_distance` call the kernel; the copy of the fixed-point arithmetic goes |
| `src/fenolite/cli/data/explain.toml` | tables for the fifteen new codes (listed below) |
| `src/fenolite/backends/base.py` | `NetLength(net, routed, vias, die, total, via_count)`, `LengthFacts(nets, depths, die, major, stackup, count_vias, evidence)`, protocol `LengthSource.length_facts(design, *, project=None, major=None, nets=None, issues=None) -> LengthFacts` |
| `src/fenolite/backends/kicad/lengths.py` (new) | `layer_depths(board, *, major)`, `joined_layers(design, via, pads)`, `via_height(via, joined, depths, copper, *, major)`, `die_lengths(design)`, `counts_via_heights(project_text)`, `net_lengths(design, *, pads, depths, major, count_vias=True, nets=None)`, `length_facts(design, *, project=None, major=None, nets=None, issues=None)`, `DEFAULT_COPPER_NM`, `DEFAULT_MASKS_NM`, `LENGTH_ISSUE_CODES`, `EVIDENCE` |
| `src/fenolite/backends/kicad/backend.py` | `KicadBackend.length_facts`; `_LENGTHS: LengthSource = KicadBackend()` |
| `src/fenolite/analysis/length.py` (new) | `PathRow`, `LengthRow`, `PairRow`, `LengthReport`, `measure_lengths(design, *, pads, facts=None, nets=(), starts=())`, `EVIDENCE` |
| `src/fenolite/analysis/codes.py` | `analysis.length-open`, `analysis.length-stub` |
| `src/fenolite/cli/cmd_analyze.py` | kind `length` (opt-in), `--net`, `--from`, the major from the global `--kicad-version`; `result.lengths`, `result.pairs` |
| `src/fenolite/checks/length.py` (new) | `length_stage(design, *, project, rules_source, facts_source, evidence) -> StageResult`, `judge_lengths(…)`, `EVIDENCE` |
| `src/fenolite/checks/codes.py`, `checks/stages.py`, `cli/cmd_check.py` | three `length.*` codes; `length.rules` in `STAGE_ORDER` and its runner |
| `src/fenolite/dsl/intents.py`, `dsl/design.py`, `dsl/__init__.py` | `Design.meander`, `MeanderIntent`, `meanders(design)` |
| `src/fenolite/backends/kicad/meander.py` (new) | `MeanderIntentLike`, `resolve_meanders(design, meanders, *, major, issues=None) -> Design`, `LENGTH_TOLERANCE_NM = 10`, `MEANDER_ISSUE_CODES`, `EVIDENCE` |
| `src/fenolite/lens/build.py`, `cli/cmd_build.py` | `meanders=`; `result.copper.meanders` |
| `tests/_lengthbench.py`, `tests/_meanderdesign.py` (new) | the benches of Context, built hermetically for both targets; the meander design scripts |
| `tests/unit/geometry/test_lengths.py`, `tests/unit/backends/kicad/test_lengths.py`, `tests/unit/analysis/test_length.py`, `tests/unit/cli/test_analyze_length.py`, `tests/unit/checks/test_length_stage.py`, `tests/unit/dsl/test_meander_dsl.py`, `tests/unit/backends/kicad/test_meander.py`, `tests/unit/lens/test_build_meander.py` (new) | hermetic tests |
| `tests/kicad/length/test_length_parity.py`, `test_meander_oracle.py` (new); `tests/kicad/_probes.py` | the canaries and their probes |
| `docs/analyses.md`, `docs/formats/kicad/length.md` (new), `docs/evidence/length.md` (new), `docs/dsl.md`, `docs/copper.md`, `docs/cli-contract.md` | the measure, the KiCad facts with their labels, the canary outcomes, the meander, the commands and codes |

`result.copper.meanders` and the stage are additions that "Copper intents in a build" and "Check stages and statuses" allow. No schema, model or FEN code changes, so no model document gains a key and no compatibility sentence is owed. No file is added under `tests/data/`: the benches are built by `tests/_lengthbench.py`.

New names of this change, for the cross-check among the v0.4 proposals:

- Hypothesis ids: `H-K-NETLEN-TOTAL`, `H-K-NETLEN-VIA10`, `H-K-NETLEN-VIA9`, `H-K-NETLEN-STACKUP`, `H-K-NETLEN-RULES`, `H-K-NETLEN-MEANDER`, `H-G-NETLEN-PATH`.
- Issue codes (fifteen): `length.out-of-range`, `length.skew-out-of-range`, `length.input-missing`; `analysis.length-open`, `analysis.length-stub`; `kicad.length.default-stackup`, `kicad.length.bad-die`; `kicad.meander.bad-intent`, `kicad.meander.bad-match`, `kicad.meander.bad-shape`, `kicad.meander.inexact`, `kicad.meander.no-room`, `kicad.meander.no-segment`, `kicad.meander.not-needed`, `kicad.meander.too-long`.
- Stage: `length.rules`. Analysis kind: `length`. CLI flags of `analyze`: `--net GLOB`, `--from REF`.
- Result keys: `result.lengths`, `result.pairs`, `result.summary.length`, `result.inputs.{nets,from,kicad_version}` (analyze); the stage summary keys `rules`, `nets`, `major`, `stackup`; `result.copper.meanders` (build).
- Protocol and records: `LengthSource`, `LengthFacts`, `NetLength`. Kernel: `segment_length`, `arc_length`, `arc_length_to`. DSL: `Design.meander`, `MeanderIntent`, `meanders`.
- Probe ids: `length-total-*`, `length-via-*`, `length-rules-*`, `length-meander-*`.

## Sources registered by this change

None. The KiCad facts rest on S-0020 (`kicad-cli` 10.0.6) and S-0029 (the pinned 9.0.9 image), the two oracles already registered.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-NETLEN-TOTAL | On 9.0.x and 10.0.x, KiCad's DRC length of a net is the sum of the centre-line lengths of all its tracks and arcs, plus one height per via, plus the die length of each of its pads; a through-hole pad adds no height; a zone fill is not copper a via joins; with `use_height_for_length_calcs` false no via adds a height (S-0020, S-0029) | `tests/kicad/length/test_length_parity.py -k total` | every `length-total-<case>` probe `equal` on both majors, the canary firing |
| H-K-NETLEN-VIA10 | On 10.0.x a via adds the depth difference between the outermost two copper layers on which a track, arc or pad of its net touches it, 0 below two, with the depths of Context (outer layers to their outer face, inner layers to their middle) (S-0020) | `test_length_parity.py -k via` | `length-via-<case>` `equal` on 10.0.6 |
| H-K-NETLEN-VIA9 | On 9.0.x a via adds the depth difference between its own two end layers, every layer to its middle, when its net touches it on both, else 0 (S-0029) | `test_length_parity.py -k via` | `length-via-<case>` `equal` on 9.0.9 |
| H-K-NETLEN-STACKUP | For a board file without a stack-up, both majors take copper layers of 35 µm and dielectrics that share equally the board thickness less 20 µm and the copper (S-0020, S-0029) | `test_length_parity.py -k default_stackup` | `equal` for 2 and 4 layers on both majors; 6 and 8 layers by task 1.3 |
| H-K-NETLEN-RULES | A length rule judges `min` and `max`, not `opt`; a net of pads only is judged at length 0; a skew rule groups the nets it governs, each pair apart with `within_diff_pairs`, and reports each net whose length differs from the longest of its group by more than `max` (S-0020, S-0029) | `test_length_parity.py -k rules` | the stage's findings name the same nets as KiCad's violations on both majors |
| H-G-NETLEN-PATH | The shortest path of Decision 7 is the length along copper from one pad to another, and equals KiCad's total on an unbranched net with 10 facts | `tests/unit/analysis/test_length.py` | hand-computed cases equal; the equality holds on every unbranched bench; no oracle exists, so it stays `INFERRED` |
| H-K-NETLEN-MEANDER | A meander resolved by Fenolite loads on both majors, KiCad's length of its net equals the target within 1 µm, and the bench reports no violation that the same bench without the meander lacks (S-0020, S-0029) | `tests/kicad/length/test_meander_oracle.py` | `length-meander-<case>` `equal` on both majors |

All rows start `INFERRED`, with the measurements of Context as their first record. The stems `H-K-NETLEN-` and `H-G-NETLEN-` appear nowhere in `docs/`, `src/`, `tests/` or the living specs of `dev` at `9aba2dff`; `H-K-LENS-*` is another family.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| totals, via heights, die lengths, project switch | KICAD-VERIFIED (9.0.x, 10.0.x) | `length-total-*`, `length-via-*` |
| default stack-up | KICAD-VERIFIED (9.0.x, 10.0.x) for 2 and 4 layers | `length-total-*` default rows |
| stage verdicts | equal to KiCad's on the canary benches | `length-rules-*` |
| paths, stubs, pair skew | INFERRED | unit tests; equality with totals |
| kernel lengths | mechanical | `test_lengths.py` against an independent computation, against `views.arc_length` and against the routing copy of c0089 before it is removed |
| meanders | KICAD-VERIFIED (9.0.x, 10.0.x) on the benches | `length-meander-*` |

`lengths.EVIDENCE`, `analysis.length.EVIDENCE`, `checks.length.EVIDENCE` and `meander.EVIDENCE` stay `INFERRED` when their rows are verified: the rows cover benches, not every board, as `copper.EVIDENCE` does. A reply is `UNVERIFIED` when a fact was missing.

## Risks / Trade-offs

- **The two majors disagree.** A board judged by the other major gets other totals. Mitigation: the facts and every reply name the major; `--kicad-version` chooses; the canaries pin both.
- **A KiCad release changes the counting.** Mitigation: the canaries run in the `kicad-9` and `kicad-10` jobs and fail on drift; the rows name the version.
- **No stack-up beyond 4 layers.** The default is unmeasured for lengths on 6 and 8 layers until c0100. Mitigation: `stackup` says `default`, c0101's job-file probe gives the same formula, and task 1.3 measures lengths.
- **A stack-up node that c0101 does not project.** KiCad may still count such a node for lengths, while the facts fall back to the default. Mitigation: the facts say `default` beside c0101's `kicad.board.stackup-unused` warning; task 1.2 adds an incomplete node to the benches and records what KiCad counts.
- **Graph joins differ from KiCad's connectivity.** Items that cross without an end inside each other are not joined, while KiCad joins any overlap. Totals do not depend on joins, only paths do; the limit is listed in `docs/analyses.md` and in the proposal.
- **Cost on a large board.** The facts compute only the nets asked for, and the stage asks only for nets that rules govern; via joins use one spatial index per layer.
- **A meander runs into other copper.** The resolver does not avoid it. The copper guard of `build` judges the written copper and refuses a clash by default.
- **c0104's names differ from the assumed ones.** Task 0.1 adapts before code starts.
- **Replacing the routing copy moves an equivalence verdict.** Mitigation: task 2.1 compares the two on generated arcs and on the level-5 fixtures before the copy goes, and the level-5 tests run unchanged after it.

## Migration Plan

- Additive. `check` on KiCad input gains the default stage `length.rules`, which gives no issue on a board without length or skew rules; `check` on Altium input keeps its stage list. `analyze` keeps its default kinds. `equivalent --level 5` gives the same verdicts and values.
- A script without meanders builds the same bytes.
- Rollback: remove the modules, the stage, the kind and the codes; nothing else depends on them.

## Budget (9.5 days)

| part | days |
|---|---|
| registers, benches, probes recorded on both majors | 0.75 |
| kernel lengths, `views` calling them | 0.5 |
| KiCad net lengths: depths per major, default stack-up, via joins and heights, die lengths, project switch, protocol | 1.5 |
| paths, stubs, pair skew, report | 1.75 |
| `analyze --kinds length`, codes, contract docs | 0.75 |
| stage `length.rules` and its codes | 1.0 |
| parity canaries on both majors, evidence page | 1.0 |
| meanders: DSL, resolver, build, oracle | 1.75 |
| documentation and closing | 0.5 |

Cut order: (1) meanders (−1.75, to 7.75 days); (2) the stage `length.rules` (−1.0): KiCad's DRC still judges c0104's rules; (3) paths of nets with more than two pads and `--from` (−0.5). Not cut: the totals per major with their canaries, two-pad paths and pair skew.

## Open Questions

- **Meanders on router copper.** Default: script copper only (Decision 11). After c0110, a follow-up can split router tracks and rejoin them on rebuild.
- **Should `fenolite net` print the total?** Default: no; c0066's reply stays as it is, and `analyze --kinds length` gives totals.
- **Die lengths from a script.** Default: none; a later change can add `Pad.die_length` and a DSL setter together.
- **`analyze --kinds length` without `--net`.** Default: no net and one `analysis.input-missing`. Alternative: the nets that the design's pairs name.
- **Rounded meander corners.** Default: square only.
- **A meander target from a rule.** c0104 writes the `opt` of a `length` rule for KiCad's tuners. Should `Design.meander` take `target="rule"` and use it? Default: no; the script passes `target` or `match`.
- **A default stage or an opt-in one.** Default: default, because it costs nothing without length or skew rules.

## Found on 2026-10-08 (integration)

The change was implemented on an older base, returned before its `make check-fast` had ended, and was rebased onto `v04` with c0103 and c0104 on it. What the integration did and found:

- **Every delta of the change is ADDED**, so no requirement text had to be regenerated. The ten conflicts were places where two changes add beside each other (the protocols `ExclusionSource` of c0114 and `LengthSource` in `backends/base.py` and in the KiCad backend, the evidence of board items and of meanders in `lens/build.py`, the probe registry, the test folders of `tests/kicad/conftest.py`, the registers); both sides are kept whole.
- **The 9.0.9 half is measured.** The eleven `length-*` probes ran inside the pinned 9.0.9 image and are recorded in `docs/evidence/kicad/probes/9.0.9.json`: all `equal`, as on 10.0.6. `tests/kicad/length` gives 21 passed on the local 10.0.6 and 21 passed inside the image. Tasks 1.2 and 8.4 are ticked on those runs; the hypothesis rows keep their labels until task 10.3.
- **The guide** (c0080 is on the branch now): one tested command line for `fenolite analyze --kinds length` on the page `rules`, one `design.meander` call in the tested script of the page `routing`, and `MeanderIntent` and `meanders` in `guide.DSL_NOT_TAUGHT` with their reasons (task 9.2).
- **c0104 is on the branch now**, and the parts that waited for it are still not written: the pairs of the length report (task 4.3), the stage `length.rules` with its three codes (task 6.1) and the stage verdicts of the canaries (task 7.1). They are new code, not corrections, and stay open.
