# Design: c0431

## Writer

`lower._footprint_items` gets the Altium id of each copper layer of the written stack
(`pcbrecords.copper_stack`). For a footprint with `net_ties`, a graphic on a signal layer that
`pcbdoc.graphic_problem` accepts becomes a `pcbdoc.ComponentGraphic` on that id: the component writer already
writes such items as tracks, arcs and regions with the component's index and no net, as the instance
holds them (no mirror, no layer flip). It is counted written under `footprint-copper`.

The tie's copper carries no net. KiCad holds it without one, and Altium's DRC skips the shorts inside a Net
Tie component (S-1900). Which net Altium itself would give a primitive that touches two pads of different
nets is not read: a kit case settles it.

Not covered, and still a `footprint-copper` loss: a graphic of a footprint without net-tie groups, one on an
internal plane (a plane holds no track), and one that no record holds (a filled circle).

## Equivalence

A new level 3 kind, `net-tie-copper`, field `copper`. For a footprint pair where either side has
`net_ties`, each side's copper graphics become pieces `(role, form, width, points)` in the footprint's frame:

- `role` is the copper layer's position in the board's copper ordinals: `top`, `inner<k>` or `bottom`;
- a line, and each side of a rectangle or polygon outline, is a `segment` of its two sorted ends;
- a filled rectangle or polygon is a `region` of its sorted corners;
- a circle is an `arc` of its centre and radius, and an arc an `arc` of its three points.

Pieces match when role, form, width and every point agree within the length tolerance. Each unmatched piece
is one difference at the reference, `a` or `b` holding its text and the other side `""`. A footprint that is
a net tie on neither side compares no copper, so existing comparisons are unchanged.

`convert.report.EXPLAINS` gains `footprint-copper` → `net-tie-copper` at the reference of the footprint
whose graphic was lost.
