# Design: c0437

## Where the time goes

`fenolite check` on the KiCad conversion of public row `altium-third-party-pcbdoc-08` (544 parts, many
silkscreen and copper arcs), copper stage alone under cProfile: 305 s, of which `thick._curved_distance`
240 s. Each arc pair that passes the box test is measured exactly: `_curved.closest` takes every segment
of the other core in the inflated box, widens the box until a candidate is within it, and evaluates every
segment with `_arc_segment`, whose candidates are sums of square roots compared by guarded squaring. A
fill or zone ring near an arc gives hundreds of segments per pair; the copper check asks only whether the
gap is below a clearance, and `thick_gap_floor` and `thick_witness` ask for the distance of a finding.

## Pruning with float bounds

For one arc, `_Gauge` holds its exact box, its centre and radius as floats, and float points along it: the
three stored points and `SAMPLES - 1 = 7` points at equal angles. For a segment, `bounds` gives

- lower: the larger of the gap between the arc's box and the segment's box, and the distance from the
  segment to the arc's whole circle (outside: nearest distance to the centre less the radius; inside: the
  radius less the farthest end's distance; crossing: 0);
- upper: the nearest of the arc points to the segment;
- slack: 1 nm plus 10⁻⁹ of the largest magnitude involved. The bounds take a handful of float operations,
  each rounding by about 10⁻¹⁶ of that magnitude, so the slack exceeds their rounding by about six orders.

`closest` evaluates exactly only the segments whose lower bound less slack is at most the smallest upper
bound plus slack, in the order it evaluated them before. A segment left out is strictly farther than the
nearest segment, so it can neither be the closest nor tie with it: the returned pair is unchanged.

`within(a, b, reach, strict)` answers `2·distance < reach` (or `≤`) without the distance: it queries the
index with the arc's box grown by `reach / 2 + 1`, skips a segment whose lower bound less slack is above
`reach / 2`, accepts on an upper bound plus slack below `reach / 2`, and evaluates the rest exactly,
stopping at the first one within. Filled-ring containment and arc/arc pairs keep their exact paths.

A sample point is used only when the radius is at most 10¹² nm and every sample lies in the arc's exact box
grown by the slack: a sweep computed the wrong way round would put points outside it. The test checks with
exact arithmetic that every sample lies within the slack of its arc.

## What is not changed

The decisions stay exact: floats only remove segments that the exact order already decides, and decide a
test only with the slack on the safe side. The rows timed in the proposal give the same findings (codes,
messages and locations) with and without the pruning.
