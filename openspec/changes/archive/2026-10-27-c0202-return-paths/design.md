## Context

`net_copper` shapes every item, fills included, per net and layer. `crossings.CutLine` gives the spans of a
segment inside a filled ring, rounded outward to whole nanometres. The stack-up order is the board's copper
layer order.

## Decisions

1. **Reference layers are the neighbours in the layer order.** One for an outer layer, two for an inner
   one. A track is referenced over either. The thickness of the dielectric is not weighed: a stack-up
   may be missing, and the nearest copper layer is where the return flows on the boards this targets.
2. **Reference copper is stored fill.** By default it is every other net with a fill on the reference
   layer, since a plane of a supply also carries return current. `--reference` narrows it. Tracks and pads
   of the reference net are not a plane.
3. **The centre line decides.** A span is measured along the centre line, so a track that grazes a plane
   edge with half its width is still referenced. The width would only move the span ends by half a
   width, and the centre line keeps the result exact.
4. **Split or edge.** A span strictly inside a track has reference copper on both sides along it, so the
   track crosses a gap: a finding. A span that reaches an end is where the track leaves the plane; it is
   listed, because a connector or a part off the plane is normal. A gap exactly at the joint of two tracks
   reads as two edges; the row still lists both spans.
5. **Vias.** Without `--via-distance` the pairing is only reported; with it, a farther or missing
   reference via is a warning. No distance is assumed.
6. **`--net` is shared.** The length kind already takes `--net GLOB`; with `returns` among the kinds it
   selects the nets of both, and `returns` needs it.

## Risks / Trade-offs

- A board whose planes are not refilled is judged on its old fill, as every analysis that reads fills.

## Open Questions

None.
