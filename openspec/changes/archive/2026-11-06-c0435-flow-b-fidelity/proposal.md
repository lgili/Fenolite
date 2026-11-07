# c0435: flow-b-fidelity

## Why

Flow B, an Altium PCB document converted to KiCad and back to Altium (S-1940..S-1949), reported three
differences that the round trip itself made: an arc whose three points lie on one line was left out (lossy),
so its net lost 185 nm of route length; a footprint name holding `/` came back with `_` and was a
`footprint-name` difference; and two free holes came back as components without a reference, which
`equivalent` reports as `ref-ambiguous`.

## What changes

- The Altium lowering writes an arc whose middle point lies on the segment from its start to its end as the
  track from start to end (`lower.straight_arc`), counted `changed` under `arc` (`ARC_STRAIGHT`).
- The Altium lowering writes a generated hole footprint (`model.holes.HOLE_LIBRARY`, one unplated pad, no
  reference) as a free pad, the form a free hole has in the document, counted `changed` under `footprint`.
- `equivalent` compares footprint names after the library-entry rewrite of the Altium to KiCad conversion,
  which moves to `core.libnames.library_name` so both use one function.

## Not in this change

- A name the conversion made unique with a suffix (`R_0603_2`, when two source names rewrite to one) is
  still a `footprint-name` difference: the suffix says another library entry.
