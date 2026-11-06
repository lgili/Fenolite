# Design: c0447

## Recognising a converted free pad

A KiCad footprint always has a link, so the free-pad form of the import (no reference, no link, one pad)
cannot survive a KiCad file. The conversion already marks the footprint: its link item is
`FREE_<footprint id>` (sanitised by `library_name`, perhaps with a `_2` suffix). The prefix becomes a
shared constant, `fenolite.core.libnames.FREE_PAD_PREFIX`: `core` is the one package both `convert` and
`backends` may import. The writer tests the item part of the link (after the last `:`), with no reference
and exactly one pad, as `generated_hole` tests the hole library (change c0435). A footprint with a
reference stays a component whatever its link says.

The alternatives were a field or attribute on the KiCad footprint (a new KiCad fact, and a script's
footprint would not carry it) or the library name (the project's name, which a user may rename).

## The edge rule with a text matrix

Three readings of the source's priority-1 rule agree with the measured 0 hits: the text row exempts text
only and the silk tracks lie outside 10 mil of a rule that does not govern them; it exempts every overlay
primitive; or a non-empty matrix checks only its own cells. The round trip's 24 hits do not tell them
apart. Mapping the record onto KiCad (`edge_clearance` with a condition) needs the answer, so it waits for
an Altium measurement: DM6010 with the matrix cleared, and an authored board with a copper track and a silk
track near the edge under a text-only matrix.
