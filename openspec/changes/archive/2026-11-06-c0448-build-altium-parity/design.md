# Design: c0448

## One lowering, two front doors

`convert --to altium` and `build --target altium` both reach `lower.write_design` / `lower.from_design`.
The build adds its own checks in `lens.altium` before the lowering: the library check
(`pcblib.check_footprint` with `pad_extras`) and the document planning (`lowered_pcb`). The three gaps are
in those checks and in the one branch of the lowering that only a build takes (`options` set).

## Net-tie copper

`check_footprint` refused any graphic on a copper layer. A footprint with net-tie groups now passes it: the
library writes a graphic on `F.Cu` or `B.Cu` like any other graphic (`LAYER_MAP` 1 and 32), and
`_graphic_drop` names one on an inner layer. The document takes the footprint instance's graphics through
`_footprint_items`, which writes net-tie copper as component items of the kind-4 component (c0431).

## Pad margins

The KiCad reader projects `solder_mask_margin` and `solder_paste_margin` into `Pad.mask_margin` and
`Pad.paste_margin` and keeps the child as an opaque slot (`_fpmap.MARGIN_HEADS`). `pad_extras` read the
slot and listed the margin dropped, though `pcblib.pad_bytes` writes the field as a manual expansion
(c0440). It now skips a margin child whose field the model holds.

## Outline arcs

c0441 writes an arc of the board ring as one arc vertex. The build kept c0102's refusal of such an outline,
and its branch of the lowering wrote `Board.outline.points` without the arcs. The lens now plans the
document, and the branch uses `_arc_ring(_open(points), arcs)`, as the conversion's `_outline` does. DSL
outlines are open, so a build without arcs keeps its bytes. A ring with fewer than three vertices (a round
board of two arcs) is still not written: `docboard.board_records` needs three, and a mid is no vertex.
