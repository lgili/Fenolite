# Design: c0442

## Where the stroke travels

The model's `Keepout` already has a `name`. The KiCad writer writes it as the zone's `(name …)`, the KiCad
reader reads it back, and the DSL emitter writes it as the first argument of `design.rule_area`. Each
step accepts the alphabet `[A-Za-z0-9_.+/-]`. So the name carries the stroke through both flows, with no
new model field and no extension bag. KiCad's DRC does not read a rule area's name unless a custom rule
selects it, and no converted rule names these areas.

Format: `Altium.KeepOut/line/x1/y1/x2/y2/w`, `Altium.KeepOut/arc/x1/y1/xm/ym/x2/y2/w`, and
`Altium.KeepOut/circle/cx/cy/ex/ey/w`. The second ring of a circle adds `/2`. Numbers are nanometres, in
the frame of the area, which is the frame of the drawing it came from.

## Why only plain strokes

The source document tells a plain stroke from a keep-out stroke by its second flag byte. `convert` already
reads every flagged drawing's restrictions by locator (`keepout_restrictions`, c0420). A drawing with no
entry there is plain. Only plain strokes are marked, so a flagged stroke never comes back without its
flag.

## Why the guard

A user may edit the area in KiCad. Writing the stale stroke would silently undo the edit. The writer
therefore recomputes the band of the stroke as the conversion made it (`segment_band`, `arc_band`). It
compares that band vertex by vertex with the area's outline, within 10 nm: a footprint's area is stored in
board coordinates by KiCad and turned back, which rounds. It also checks the four restrictions a plain
stroke gives. A circle is given back only when both of its rings are intact.

## Equivalence

`_drawn_keepouts` gives each ring of a keep-out drawing the value `DRAWN_KEEPOUT` plus `form`. The
comparison drops `form` when only one side is a drawing (a KiCad rule area against an Altium drawing). It
compares `form` when both sides are drawings, which is the case of an Altium-to-Altium round trip.
