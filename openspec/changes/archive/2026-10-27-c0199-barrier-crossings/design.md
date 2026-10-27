## Context

c0175's design, decision 3 ("Barrier crossings"), holds the method: intersect the cut with the obstacles of
each copper layer, and count the free intervals. The copper of the board is shaped by
`analysis.copper.net_copper` and `loose_copper`, the outline by `analysis.boundary.board_boundary`, and the
open connections by `analysis.connectivity.connectivity`.

## Decisions

1. **The new track.**
   - `--width` and `--clearance` give it. By default the width is the narrowest `track_width` of the net
     classes, and the clearance is that class's clearance, else that of the class `Default`.
   - Without a width or a clearance no way is counted, and `analysis.input-missing` names what is missing.
     A KiCad board read without its project file holds no class values, so the options are the usual way.
2. **Growth of an obstacle.**
   - An item's copper grows by the larger of the track clearance and the clearance of the item's class, as
     KiCad resolves the clearance between two classes; copper without a net grows by the track clearance.
   - The edge and the cut-outs grow by the largest board-wide `edge_clearance` rule (`all` selector), else
     by the track clearance. The cut outside the outline is blocked.
   - A hole without copper grows by the track clearance. A rule area that forbids tracks (`no_tracks`)
     blocks its layers, matched by name or by KiCad's `*`, `&` and `F&B` patterns, and does not grow.
3. **Exact enough, and never optimistic.**
   - The cut is `P0 + t·d`. A grown segment is a capsule: the hull of the line's parts inside its two end
     discs and its band. A filled ring adds the spans where the line lies inside it, by the non-zero rule
     at the midpoint of each piece.
   - The arithmetic is `Decimal` at 50 digits. The ends of each obstacle are rounded outward to whole
     nanometres along the cut, so a way is never longer than its exact value.
4. **Counting.**
   - A way fits `⌊(L + c) / (w + c)⌋` tracks.
   - The supply of a cut is the sum over its layers.
   - The demand counts each open connection of `connectivity` whose segment meets the cut (touching
     included), and each track or arc whose copper touches the cut.
   - `analysis.crossings-short` is a warning, not an error: the count is an upper bound for a router
     (no turns, no vias), so a short cut is a strong sign, not a proof.
5. **No drawing in `analyze`.** c0175's draft asked `--render FILE.svg` under the mutation protocol, but
   `Command.mutates` is fixed per command and `analyze` is read-only. The reply holds what a drawing needs:
   the cut's ends, each way's ends on the board and each layer's obstacles along the cut.

## Risks / Trade-offs

- A cut drawn along the centres of a row of pads starts and ends inside pads, so the ways are the gaps. A cut
  that runs past the row also counts the ways beyond it; the user draws the cut where the barrier is.
- Arcs are their polylines, within 1 µm; the band is not added.

## Open Questions

None.
