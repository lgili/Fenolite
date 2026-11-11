# Design: c0494

## D1 The comparison

A helper in the test reads a PcbDoc with Fenolite's reader and gives, per component (by designator), the
sorted tuple of its overlay primitives. A track is `(layer, sorted ends)` and an arc is `(layer, centre,
radius, start angle, end angle)`, all in file units in the document frame. Source and written are equal
when the tuples have the same length and each item matches within one unit. The comparison is the same one
`backends.altium.roundtrip` runs for other primitives, so the helper goes there if no equivalent exists.

## D2 The authored document

Written by Fenolite's own writer from a design script:

- one footprint with an outline of four overlay tracks with a gap at one corner, a 90° arc at one end and a
  pin-1 dot (a full circle);
- placed at 0°, 90°, 180° and 270° on the top side and on the bottom side, so eight instances;
- a text 0.2 mm from the open end, so a stroke added there is also a DRC finding.

The build is the c0480 path: `fenolite build` of the imported design to `.PcbDoc`, then read back.

## D3 Deciding

- **H1:** an arc's sweep or ends differ, or a track appears where an arc was. Fix in `lower.kept_arc` or
  in the bottom mirroring of `_library_graphic` for arcs.
- **H2:** an extra track joins two ends of the open outline. Fix where the outline is closed.
- **H3:** the extra item has a derived provenance (`derived` or `clip` in its bag, or a KiCad layer source).
  Fix by skipping it in the writer, as c0489 does for a derived courtyard.

The test of D1 stays whichever it is.
