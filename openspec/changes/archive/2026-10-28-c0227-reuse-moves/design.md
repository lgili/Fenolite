## Context

c0210 built `place --strategy reuse`: `reuse.fit_block` pairs pads by numbers found once in both
footprints, `reuse.copy_copper` maps tracks, arcs and vias, and `cli.reuse_copper.settle_copper` prunes,
drops islands and drops what the copper check names, pass after pass. c0175 kept three requirements of
its package 4: pads matched by net partition, zones of a copied block, and group moves. `reuse` may import
`model`, `geometry` and `backends.base` only; the glue in `cli` may use `tidy` and `checks`.

## Decisions

1. **Nets from the numbered pairs.** The pairs by number of every part of the block give a net map:
   reference net → the target nets of the pads paired with its pads. A net with two images maps to none.
   The map comes before any transform, so the anchor's partition pairs use the same map.
2. **Partition within a part.** The pads of a part that numbers do not pair are grouped by net, the
   reference pads under their mapped net. A net with one pad on each side pairs them. A net with more pairs
   by geometry: the fit by number (for the anchor, the block transform of its numbered pairs; for another
   part, its own numbered fit) maps a target pad to an image, and the pad pairs with the reference pad whose
   goal lies nearest that image when that pad's nearest image is this one and the distance is within the
   tolerance. A net with more pads and no fit by number stays unpaired: the partition cannot tell them
   apart. The fit is then made again on all pairs, so a part of `GND` pads only and one numbered pin fits.
3. **Pad ids, not numbers.** `PadMatch` gains `pad_id`, `reference_pad_id` and `by` (`number` or `net`).
   The net map of the copper, the measure of the moved pads and the block's copper look pads up by id,
   since numbers repeat now.
4. **Zones of the block, judged by their fill.** The glue groups the reference copper of each net with
   fills (as the copper check joins it) and gives `copy_copper` the pads that each zone's fill joins. A zone
   whose pads are all paired is copied: outline, fills and layers mapped as tracks; under a mirror the rings
   are reversed to keep their winding. A zone that also joins an unpaired pad is `zone-beyond-block` (a
   plane of the whole board), a zone of a block net without a fill whose outline box holds a paired pad is
   `zone-unfilled`, and a zone joining no paired pad is not of the block. The settling holds zones beside
   tracks: a copied fill does not anchor copies as a board fill does, and a zone whose group lost one of the
   images of its pads goes as `pad-lost`.
5. **What moves with a group.** The joined groups of each net, built without fills from the board-frame
   pads: a group that holds a pad of the group and no other pad moves whole (tracks, arcs, vias); a zone
   moves when its stored fill joins pads of the group only. Copper that joins a pad of the group and
   another pad stays, and `place.copper-left` names the part, as for `--move`. c0175's "locked or scripted
   copper that the group's parts own" is dropped: the model has no owner of copper.
6. **One transform for a group.** `--turn` is `p ↦ R(angle)·(p − about) + about`, `--shift` a translation
   (`geometry.Transform`). A part's placement is `reuse.moved_placement(move, placement)`: its angle comes
   from the composition, so a bottom part turns the right way (`H-G-ROT-DIR`, `H-G-BOTTOM-PLACE`). The pads
   are measured after the move against the moved pads before, within 1 µm (a turn of any angle rounds each
   point once). The copper check with the project's rules compares the board before and after.
7. **Pose search.** Poses are the four quarter turns about `--about` composed with shifts `(i·pitch,
   j·pitch)` within `--within` on each axis (`--pitch`, default 0.5 mm; at most 10 000 poses). The demand of a
   pose is, per net with a pad in the group and one outside, the shortest distance between a moved pad of the
   group and a pad outside, rounded up; its sum and the count of such nets. The reply lists the ten poses of
   least demand (ties: smaller turn, then smaller shift) and the demand of the current pose. Nothing is
   written; the user applies a pose with `--turn` and `--shift`.
8. **A strategy of `place`.** `group` joins the strategies; `--turn` or `--shift` implies it and refuses
   another. `--force` moves locked parts and writes an illegal layout, as for `manual`.
9. **Evidence.** `H-G-GROUP-MOVE` (`INFERRED`) for a group move and `H-G-REUSE-ZONE` (`INFERRED`) for a
   copied zone; `H-G-REUSE-FIT` covers the partition. `H-K-GROUP-DRC` records a KiCad case where a group
   turned by 90° gives no DRC violation type more entries; it stays `INFERRED` until both majors pass.

## Risks / Trade-offs

- A copied fill is the reference fill moved: it may not match what KiCad's filler would make on the
  target, so `reuse.fill-stale` asks for `fenolite fill`; the copper check judges the moved fill meanwhile.
- The partition by nearest goal needs a fit by number of the part; a footprint of `GND` pads only pairs
  them only when each net has one pad.
- The pose demand is a lower bound of the routing: one link per net, centre to centre.

## Open Questions

None.
