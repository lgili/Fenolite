## Context

c0175's decision 4 plans `fenolite reuse TARGET --from REFERENCE --parts ...`: a rigid fit on the anchor's
pads, each part fitted on its own pads, the copper of the block copied, pruned and checked, and group
moves of `place`. The board frame (`BoardFrame.board_pads`) gives the pads of any backend's board in one
frame; `replace.move_footprint` re-places a footprint from its library definition for a turn or a side
change; `place` has the legality check; `tidy` (c0208) has the copper groups and `prune`; `checks.copper`
has the copper check. A new package may import `model`, `geometry` and `backends.base` only.

## Decisions

1. **A strategy of `place`, not a command.** `fenolite place TARGET --from REFERENCE --only REFS` (with
   `--strategy reuse`, which `--from` implies) shares the mutation protocol, the legality check, the
   placement rules, the measures and `result.moved` of the other strategies. A separate command added 17
   lines to the generated command page, which then broke its 600-line budget; the strategy adds six. The
   parts are `--only`, the first the anchor; `--force` is refused, as for `constrained`.
2. **Pairs by unique numbers.** A pad pairs with the pad of the same number of the reference part only
   when the number occurs once in each footprint (`""` never): several `GND` pads cannot be told apart by
   their number. Matching them by the nets of their pads is a non-goal (c0175, task 8.5).
3. **Least squares over eight linear parts.** For pairs `(source, goal)` and a linear part `L` (four
   quarter turns, with or without the mirror `y ↦ −y`), the translation that minimises the squared
   distances is `c_goal − L·c_source`. The fit tries the eight, with exact fractions, and keeps, among
   those whose farthest pair lies within the tolerance, the one with the preferred mirror, then the
   smallest farthest distance, then the smallest turn; with none within, the smallest farthest distance.
   Distances are rounded up to a nanometre, the translation to 2**-128 nm (`geometry.Transform`).
4. **The block transform and the anchor.** The block transform maps the reference board onto the board.
   It is fitted on the anchor's pairs, preferring the mirror that the anchor's two sides give: a
   two-pad anchor cannot tell a mirror, and its sides decide; a chiral anchor decides by its pads, so a
   reference read with the Y axis up gives a mirrored transform. The anchor keeps its placement: the
   user placed it. `flipped` is the anchor lying on the other side than its reference part.
5. **Each part by its own pads.** A part's pads as they lie now are fitted onto the block transform of
   its reference part's pads; the new placement is that fit composed with the part's placement
   transform `at + R(θ)·M^bottom·p` (`H-G-ROT-DIR`, `H-G-BOTTOM-PLACE`). The preferred side is the
   reference part's side, flipped with the anchor. A part placed on the other side is
   `reuse.mirror-suspected`: a mirrored footprint, usually. A part with no pair, or whose fit leaves a
   pad beyond the tolerance, is not placed (`reuse.no-fit`), and the write is refused.
6. **Measure, then check.** The command moves the parts with `move_footprint` (a turn or a side change
   needs the definition through the project's `fp-lib-table`, as `--move`), then measures every moved pad
   on the board frame against its goal (`reuse.check-failed` beyond the tolerance). The copper check with
   the project's rules runs on the board before and after the moves; a new finding (a part moved onto
   copper) is `reuse.check-failed`. The legality check of `place` judges the layout.
7. **The copper of the block.** The reference copper of the block is what joins a paired pad through
   tracks, arcs, vias and paired pads only: through a fill or another pad a plane would bring the whole
   net in. Each reference net maps to the board net of the pads paired with its pads; a net that two
   board nets claim is left out (`net-ambiguous`). Layers keep their names, or mirror in the stack when
   `flipped`; a layer without an image is `layer-unknown`. Copies get ids derived from the anchor's
   footprint id and the reference item, so a second channel gets other ids.
8. **Settle by passes.** `reuse` may not import `tidy`, so the glue settles the copy: `tidy.prune` with
   every item of the board kept removes copies with a free end and vias joined on fewer than two layers
   (`free-end`, `via-under-two-layers`); a net it cannot shape drops its copies (`net-skipped`); the copies
   of a group of the net (fills included, as the copper check joins copper) are an `island` unless the
   group holds two pads, or one pad and a fill or copper of the board; then each copy that a new copper-check
   finding names goes with the finding's code. Passes repeat until one drops nothing; a new finding that
   names no copy is `reuse.check-failed`. The copies that stay are locked, so `route --rip` and `tidy`
   leave them.
9. **DRC on request.** `--drc` runs `kicad-cli` DRC (the tool that `check` finds) on copies of the board
   before and as it would be written, with the project files; a violation type that grows writes nothing
   (`reuse.drc-new`). It is opt-in so that the unit suites stay without a tool. c0175's "MUST be judged by
   `kicad-cli` DRC when it is present" becomes "with `--drc`", as c0208 did for `tidy`.
10. **Evidence.** The fit is `INFERRED` (`H-G-REUSE-FIT`), combined with the evidence of the reference
    board read, the placement rows and, with `--copper`, the copper-check rows. After `--drc` found
    nothing new the reply cites `H-K-REUSE-DRC` at `KICAD-VERIFIED`, still combined with the reference
    read: DRC judges the written board, not whether the reference was read right.

## Risks / Trade-offs

- A footprint whose pads all share a few numbers (a connector with `MP` mounting pads besides numbered
  pins is fine; a part of `GND` pads only is not) gives `reuse.no-fit` until task 8.5 of c0175.
- Each pass of the settling runs `prune` and the copper check on the whole board; blocks are small and
  the passes few (two on the bench).
- The tolerance is a hard limit per pad: a reference footprint of a slightly other land pattern needs a
  larger `--tolerance`, which the reply's `residual` sizes.

## Open Questions

None.
