# Design: c0435

## Straight arcs

`rec.arc_from_points` refuses collinear points: an Altium arc record is a centre, a radius and two angles.
When the middle point lies on the closed segment between distinct ends, the arc draws that segment, so the
track of the same width, layer, net and lock is the same copper. An arc whose middle lies beyond an end, or
whose ends coincide, stays refused. The arc is counted written under `arc` (the report's row agrees with
the source) and changed with `ARC_STRAIGHT`; an arc kept from a read document keeps its own record first.

## Generated holes

A free hole of an Altium document becomes, in its KiCad conversion, a reference-less board-only footprint
of `Fenolite_Holes` with one unplated pad (c0170). Written back through the footprint path, the pad, having
no number, became a free pad while its footprint became a component without a reference and without pads.
The lowering's free-pad branch, which already took a reference-less one-pad footprint without a library,
now also takes a generated hole footprint (`generated_hole`). `equivalent` then compares the holes of both
sides as holes, and no component without a reference is left to pair.

## Footprint names

`library_name` is the conversion's `_name`, moved to `core.libnames`. `norm.same_footprint_name` is true
for equal names or names equal after `library_name(…, allow_space=True)` on both sides. The difference
still reports the raw names.
