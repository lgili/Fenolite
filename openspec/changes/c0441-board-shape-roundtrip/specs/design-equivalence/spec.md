## ADDED Requirements

### Requirement: Level 7 board shape in the relative frame
With `frame` `relative`, level 7 SHALL move every point of side b's board shape (the outline rings,
cut-outs and slots, and the `Edge.Cuts` drawings and the rings they chain into) by minus the translation
that level 4 removed, before matching (change c0441); the location texts keep each side's own coordinates.
Every other item of level 7 keeps the absolute frame. With `frame` `absolute` the translation is (0, 0) and
nothing moves.

#### Scenario: A board moved whole
- **GIVEN** the authored `routed` sample with one corner rounded, and a copy whose footprints and edges are
  moved by (1.27 mm, -2.54 mm)
- **WHEN** `uv run pytest tests/unit/convert/test_round_trip_shape.py -k level_7` compares them at level 7
- **THEN** in the relative frame the translation is (1.27 mm, -2.54 mm) and no `Edge.Cuts` difference is
  reported; in the absolute frame the ring of the edges is missing on each side

#### Scenario: A flattened arc
- **GIVEN** an Altium document with a rounded corner, taken to KiCad and back with its outline arcs written
  as straight edges
- **WHEN** `equivalent` compares the two documents at level 7 in the relative frame
- **THEN** differences of the `Edge.Cuts` drawings are reported; with the arc written as an arc vertex none is
