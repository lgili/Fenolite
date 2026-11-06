# Design: c0441

## Outline arcs

The model's arc of a ring is three points: start (vertex k), mid, end (vertex k+1). The writer takes the
circle through them in the document's frame (Y up), and the counter-clockwise sweep from start to end that
holds the mid, or from end to start when the arc runs clockwise: `SA` is always where the
counter-clockwise sweep begins (`pcb-document.md`, "Outline arcs"; the public documents write it so).
Vertex k gets `KIND=1` with `CX`, `CY`, `R` (units), `SA`, `EA` (degrees); the mid is no vertex. Three
collinear points give no circle: the edge stays straight. The closing vertex repeats vertex 0 with
`KIND=0`.

## Full drill

`full_drill` is a separate argument and not `rewrite`: `rewrite` also means "the reading of an Altium
document" and is refused for any other board. A conversion's via may come from such a document through
KiCad, and KiCad keeps it. A build keeps refusing it (`altium.copper-invalid`).

## Whole units

An Altium unit is 1/10 000 mil, 2.54 nm. A read coordinate is `round(2.54 u)`. Moving it by a multiple of
254 nm (100 units) gives `round(2.54 (u - 100 k))` again, so the read-back is the source moved by exactly
that. The frame of a conversion floors the outline's lowest X and ceils its highest Y to that grid; the
board then lies less than 254 nm from (1000 mil, 1000 mil). A build keeps `Frame.of` (its bytes are
unchanged); a rewrite keeps the document's frame.

## Level 7 in the relative frame

Level 4 finds the translation of side b (the lower median of the footprint moves). Level 7 subtracts it
from every point of side b's board shape keys before matching; the location texts keep each side's own
coordinates. Other board items (zones, graphics of other layers, texts, holes) keep the absolute frame, as
before.
