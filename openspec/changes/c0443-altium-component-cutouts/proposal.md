# c0443: board cut-outs of an Altium component

## Why

An Altium component can own a board cut-out: a region with `KIND=0` and `ISBOARDCUTOUT=TRUE` on the
Keep-Out layer, with the component's index. The public row `-06` holds two, in one connector (S-2020).

The import knew a board cut-out only as a free region (c0168). A component's cut-out stayed a drawing of
the Keep-Out layer, which a conversion to KiCad turns into a rule area forbidding everything. KiCad's board
therefore lacked those two edges, and the round trip wrote them back as flagged keep-out regions of the
component. Altium's checks then treat them as keep-outs.

## What

- **Import.** `adapter.copper.footprint_items` reads a component's board cut-out as a closed `Edge.Cuts`
  polygon of width 0 of its footprint, in the pad frame. KiCad holds a footprint's edge as an edge of the
  board.
- **Writer.** `lower._footprint_items` writes a footprint's closed `Edge.Cuts` outline (a polygon, or a
  rectangle with an area) as a board cut-out region of its component (`pcbdoc.ComponentGraphic.cutout`).
  A line, an arc or a circle of a footprint's edge is still not written.
- **One region, not two.** KiCad counts a footprint's edges among the board's, so a converted outline
  holds the same ring as a board cut-out. `_cutouts` leaves out a ring that is a footprint's cut-out
  (`footprint_cutout_rings`), within 10 nm.
- **Edges.** `frame.board_edges` of an Altium design adds the footprints' closed `Edge.Cuts` outlines,
  placed, so a conversion's edge rings compare as KiCad's do.

## Not in this change

- Un-routed and antennae findings (c0444).
- A footprint edge drawn with lines or arcs.

## Impact

- Code: `backends/altium/adapter/copper.py`, `frame.py`, `lower.py`, `pcbdoc.py`.
- Docs: `docs/formats/altium/pcb-records.md`, `docs/evidence/sources.md` (S-2020), `CHANGELOG.md`.
