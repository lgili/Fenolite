# Design: c0454

## Where the net travels

The model already has `Graphic.net_id`; free copper shapes use it (c0376, c0412). A component's copper now
uses it too, so every leg sees the net without reading a backend pair:

1. **Altium → model.** `footprint_items` sets `net_id` beside the pair `net`.
2. **Model → KiCad.** The `fp_*` node writes `(net …)` in the place where KiCad 10.0.6 saves it: after
   `layer`, before `uuid`.
3. **KiCad → model.** A footprint read from a board keeps its drawn children as opaque slots. Its graphics
   are projections without slots (`drawn_children`, `ext={}`). So the net is read from the child node of
   each projection, by the projection's id.
4. **Model → Altium.** The writer maps `net_id` to the net's name and gives every record of the item that
   net's index.

## Which copper is written

- A footprint with net-tie groups keeps c0431's rule: its copper is written without a net, as KiCad holds
  it.
- Any other footprint's copper graphic is written only when it holds a net of the written board. Copper
  without a net, on a part's pad, would short the pad in Altium's checks; it stays a `footprint-copper`
  loss.

## Evidence

- KiCad 10.0.6: `pcb upgrade --force` keeps a `(net "…")` on a footprint `fp_poly`, and its DRC names that
  net on the item (S-2131).
- KiCad 9.0.9 is not checked here; task 2.3 leaves that to the maintainer's run.
