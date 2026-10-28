## Context

c0175's design, package 5, plans the routing plugin `octilinear`: it tries a few octilinear shapes per
leg (straight; 45° then straight; straight then 45°; L) in clearance, rips up and retries for a few
rounds, and accepts its result only when the copper check finds nothing new; it is for gate loops, sense
pairs and the like, and the capabilities reply lists it with the feature `short`. What exists:

- The router protocol, registry and `RoutingJob` (`routing`, "Router protocol"; c0107, c0109, c0110): a
  job holds the design, the nets with their pads, widths and clearances, the layers, the plane layers, the
  pairs, and `extra` with the board-frame pads (`BoardPad`, with their copper per layer and their holes)
  and the outline rings.
- `fenolite route` (`cli/cmd_route.py`): it selects the open nets, builds the job, merges the result,
  takes the verdict from the board, and with `--gate drc` (c0225) drops each item that brings a new
  KiCad DRC finding.
- `fenolite.routing` may import `core`, `model` and `geometry` only (`package-layering`). The copper check
  (`checks.copper.check_copper`) and the clearance in force (`checks.clearance.ClearanceResolver`) live in
  `checks`; `tidy` (c0208) receives its copper check as a callable from the command, and the plane
  fan-out (c0107) its clearance in force.
- Exact thick shapes, `thick_closer_than` and a spatial index (`geometry`).

## Decisions

1. **Where it lives.** `src/fenolite/routing/octilinear.py`, a built-in router that imports `core`, `model`
   and `geometry` only, registered as `octilinear` in `pyproject.toml`. It runs no process, so it takes no
   budget (`default_budget` absent: the command does not time it) and starts no run.
2. **Feature `short`.** `ROUTER_FEATURES` becomes `{"pairs", "escape", "short"}`; `short` says the router
   routes short connections and is not meant for a whole board. It changes nothing in the command: it is
   shown by `fenolite capabilities` so that an agent picks the router for what it is. The plugin's
   features are `{"pairs", "short"}`; it has no escape step.
3. **The checks come from the command.** The command adds to `RoutingJob.extra` the entries `clearance`
   (a callable `(RuleSubject, RuleSubject) -> Nm`, the clearance in force of the project's rules, as the
   plane fan-out takes it) and `copper_check` (a callable `Design -> findings`, each finding `(code,
   layer, sorted item ids, gap)`, `check_copper` with the project's rules, the board edge and the
   board-frame pads). Zone fills are left out of what `copper_check` judges: routing makes them stale
   (`route.fill-stale`), and `fill` pours them again around the new copper. Without `clearance` the plugin
   takes the larger class clearance of the two nets; without `copper_check` it trusts its own test and
   says so (`route.check-refused` is then never given). Without the board-frame pads it routes nothing
   (`route.tool-failed`), as Freerouting does without them.
4. **Connections.** For each net, the pads of `extra["board_pads"]` on the net are grouped by the net's
   own copper (pad copper, tracks, arcs and vias that touch, `geometry.touch_groups`). The connections are
   the edges of a minimum spanning tree over the pads between groups (Kruskal on the squared distance
   of the pad centres, ties by the two pads' `REF-NUMBER`), routed shortest first. A connection joins the
   two pad centres on a copper layer where both pads have copper, in stack order, that is not a plane
   layer and is allowed for the net (c0107). No via is placed.
5. **Shapes (S-0837).** Between the centres `a` and `b`, with `d = min(|dx|, |dy|)`: the straight segment
   when `dx`, `dy` or `|dx| − |dy|` is 0; the diagonal of `d` from `a` then straight; straight then the
   diagonal of `d` into `b`; the L through `(b.x, a.y)`; the L through `(a.x, b.y)`. Shapes that are equal
   are tried once. Each shape is tried on each layer before the next shape, so a straight route on the
   second layer wins over a bent one on the first. Every corner of these shapes is 90° or 135°.
6. **Acceptance.** A shape is accepted when each of its segments, as a thick shape of the net's width,
   keeps from every item of another net on its layer the clearance in force plus `MARGIN` (2 µm, for the
   pad shapes that KiCad approximates), keeps the board-wide `edge_clearance` (the largest `min` of the
   design's board-wide rules, which the command fills from the project's `min_copper_edge_clearance`)
   from every ring of the outline, and keeps the clearance in force from every hole of another net's pad
   or via. The items are the pads' copper, the tracks, the arcs (their polygon at 1 µm, widened by twice
   that), the vias on every layer of their span, and the copper the job placed before; a zone fill is not
   an obstacle (decision 3). At each end, the angle between the new segment and each track of the net
   that ends at that pad centre must not be acute.
7. **Length.** The length of a shape is the sum of its segments (diagonals by `floor_sqrt`). A shape longer
   than `max-length` is not tried; when every shape of a connection is longer, the connection stays open
   with `route.unrouted` naming its pads and the limit, and is never searched further.
8. **Rounds (S-0838).** A round routes every connection in order against the copper the round placed
   before. The next round starts again from the board without the job's copper, with the connections that
   failed for lack of room first, in their order, then the others. The plugin stops after `rounds` rounds,
   or earlier when nothing failed or the order did not change, and keeps the round that routed the most
   connections (the earliest of equals). Copper the plugin did not place is never removed.
9. **Pairs.** A pair whose nets have two pads each is routed as one: its ends are the matching of the
   positive and the negative pads with the smaller sum of distances, the centre line runs between the
   middles of the two ends through the shapes of decision 5, and each net's track is the centre line
   offset by half the pitch (`(width + gap) / 2 + 1 nm`, with the diagonal offsets rounded up, so the gap is
   never below the class gap), with the joints of the two offset lines at their exact meet rounded to the
   nanometre. The positive net must lie on the same side of the centre line at both ends. The coupled
   part starts and ends where a diagonal from each pad meets it, or at the middle when the pads are no
   wider apart than the pitch, and an entry (the first shape of decision 5 that makes no acute angle)
   joins it to the pad. Both tracks are judged as in decision 6, with the pair width; the two nets of the
   pair against each other with the clearance in force and no margin. A pair that no shape routes, or one
   of other pads, gives `route.pair-not-routed` and its two nets stay open.
10. **The copper check judges the result.** After the last round, `copper_check` runs on the board before
    and after the job's copper; each finding of the second run that the first lacks (a new pair of items,
    or a smaller gap of a known pair) and that names an item of the job removes the copper of that item's
    connection (both nets for a pair), with one `route.check-refused` (warning) naming the net and the
    finding. The check is not run again: removing copper adds no finding.
11. **Identity and determinism.** Each track gets `derived_id("trk", "routing", content_hash(net, geometry))`,
    so a run again gives the same bytes. Nothing random is used, so `--seed` changes nothing: equal inputs
    give equal results.
12. **Codes.** `route.pair-not-routed` (warning) and `route.check-refused` (warning) join `ISSUE_CODES`,
    `explain.toml` and `docs/cli-contract.md`. The router options `max-length` and `rounds` that do not
    parse, and any other option, give `route.option-ignored` (warning) and the default is used.

## Risks / Trade-offs

- **Only five shapes.** A connection with a part in the way stays open; that is the design: the router
  routes what a person would draw straight, and leaves the rest to another router or to the script.
- **Two checks.** The plugin's own test is conservative and the copper check is exact; KiCad's DRC
  (`--gate drc`, the oracle benches) is the proof (`H-K-OCTI-DRC`).
- **Stale fills.** A filled zone of another net is no obstacle; until `fill` runs, KiCad reports the
  stale fill, as it does for every router.

## Evidence

- `H-G-OCTI-CHECK` (`INFERRED`): on the unit benches, the result passes `check_copper` with no new
  finding, every segment angle is a multiple of 45° and no joint is acute.
- `H-K-OCTI-DRC` (`KICAD-VERIFIED` per major when it holds): on the authored benches of
  `tests/_octibench.py`, `kicad-cli pcb drc` reports no violation type more after `route --router
  octilinear --confirm` than before, and the routed nets are connected.
