## Context

c0175's decision 5 plans a `fenolite tidy` with four steps (prune, straighten, chamfer, report) and an
octilinear router. Connectivity (`analysis.connectivity`: pieces joined where they touch on one layer),
the copper check (`checks.copper.check_copper`, with the project's rules through
`KicadBackend.design_rules`) and a tree-preserving board write (`write_board`, as `route` uses it) exist.
The package layering lets a new package import `model`, `geometry` and `backends.base`, not `analysis` or
`checks`.

## Decisions

1. **Scope: prune and right-angle chamfers.** These two are local edits whose safety can be proved item by
   item; prune is the most useful. Straightening needs a lattice search with turn costs, and the report
   and the router are separate features: they stay in c0175, as do T-joint and zone-outline chamfers.
2. **The groups decide connectivity.** Each net's copper is cut into pieces shaped as the copper check
   shapes them, and joined with `geometry.touch_groups`, as `analysis.connectivity` does. An edit is kept
   only when the pieces present before and after are grouped alike, and a new piece joins an old group.
   Comparing all pieces, not only pads, also forbids an edit that cuts a via or a track off its net.
3. **Shapes are built in `tidy.graph`.** `tidy` may not import `analysis`, so it shapes tracks, arcs, vias,
   pads and fills itself with the same rules as `analysis.copper`. A net with an item that cannot be shaped
   is left alone (`tidy.net-skipped`): a pad without copper entries would make every track end on it look
   free.
4. **A free end is a disc that touches nothing.** The disc of the track width at an end must touch another
   piece of the net on the layer, or the outline of a zone of the net. Outlines count although their fill
   may be stale or missing, so a stitching via in an unfilled plane is never pruned; the groups use fills
   only. A track lying along another of its net is never free: conservative, it stays.
5. **Prune in passes, by id.** Each pass takes the dangling items of a net in kind and id order and
   removes one when the groups allow it; passes repeat until one removes nothing, so a dead branch goes
   segment by segment and the result does not depend on the board's order. An item that dangles but
   would split its net stays with `tidy.kept`; trimming it past its last joint is a non-goal.
6. **Chamfer only what is exact.** Only horizontal and vertical tracks: their legs move by whole
   nanometres, so the new corner is exactly 45°. The leg is at most half of the shorter track, so two
   chamfers of one track never overlap; a track cut to nothing by two is removed, which keeps the groups
   since the two diagonals meet there. The 45° track's id derives from its net and geometry.
7. **The copper check is passed in.** `chamfer` takes `check: Design -> Clash` values. A finding is new
   when its pair of items is new or its gap smaller. The check runs on the board with every chamfer; a
   chamfer whose tracks a new finding names is undone, until nothing new is found; a new finding that
   names no chamfer undoes them all. Usually one or two checks of the whole board suffice.
8. **The CLI is the glue.** `cmd_tidy` reads the board, its pads and the rules of the project beside it,
   keeps script copper (copper uuids) and locked items, runs the steps, and checks the tidied board against
   the board as read once more (`tidy.check-failed`: nothing written). The written board is the read
   design with the edits, so `write_board` changes only the edited items.
9. **DRC on request.** `--drc` runs `kicad-cli` DRC on copies of the board as read and as planned, with the
   project files; a violation type that grows writes nothing (`tidy.drc-new`). It is opt-in so that the
   examples stay hermetic; c0175's "MUST pass DRC when kicad-cli is present" becomes "with `--drc`", and
   the reply's evidence says which was done.

## Risks / Trade-offs

- Each candidate of prune recomputes the groups of its net: quadratic in the worst case on a net with many
  dangling items. The boards Fenolite routes keep nets small; a large plane net is mostly fills.
- A chamfer and a finding of the board before that already names its tracks: a finding with the same pair
  and an equal or larger gap is not new, so an old violation does not block a chamfer that does not worsen
  it.

## Open Questions

None.
