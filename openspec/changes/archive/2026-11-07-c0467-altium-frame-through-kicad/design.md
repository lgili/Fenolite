# Design: c0467

## Context

Change c0090 gave a board read from a PCB document its own frame (`Frame.document()`) and origin (the
`origin` pair of its `altium` bag). A board read from KiCad has neither: `lower` anchors it at its corner
(`Frame.on_units` when the outline lies on whole units, as a converted board's does, else `Frame.of`), and
`board_record` writes the origin at (1000 mil, 1000 mil). The conversion to KiCad does not move the board:
its KiCad coordinates are the document's, Y negated (S-2261).

## D1. The carrier

`convert/altium_frame.py` writes the board property `Fenolite.Altium.Frame` (`backends.kicad.boardcarrier`)
as canonical JSON, schema `fenolite.altium-frame.v0`:

- `origin`: the source's `ORIGINX`, `ORIGINY` in the frame of the design, nanometres, `[x, -y]`;
- `corner`: the low corner of the board's edge in the written KiCad board (`altium_planes.edge_corner`),
  or `null` for a board without an edge.

The conversion writes it for every Altium source whose board's `altium` bag holds an `origin` pair that
reads as two lengths. The Python import keeps it as a `design.verbatim` property and the build writes it
again, as it does every carried property (S-2261).

## D2. The way back

`to_altium` reads the carrier and passes the origin to `lower.write_design(frame_origin=…)`:

- the origin moves by the translation of the edge's corner, current minus carried (`(0, 0)` without a
  corner on either side), as change c0466 moves the planes' splits;
- `lower` writes the board in `Frame.document()` and writes the origin at the moved point, in the
  document's frame (`(x, -y)`).

A board read from a PCB document keeps its own frame and origin; `frame_origin` changes only a board that
was not.

## D3. The guard

The document frame writes a point at its absolute coordinates. A board moved in KiCad to a negative
Altium X or Y (a KiCad Y above 0) would be written at a negative coordinate, which no public document holds
(S-2260; `INFERRED`). Then `lower` writes the board as before, anchored at its corner, and records a change
of kind `outline` with the reason `FRAME_ANCHORED`.

## D4. Tests

- `tests/unit/convert/test_altium_frame_c0467.py`:
  - the carrier reads what it writes and refuses another schema;
  - an authored document with its origin 30 mil above the outline's corner comes back with the same
    absolute origin and outline;
  - the same board moved in KiCad comes back with the origin moved with it;
  - a board moved to a negative coordinate is anchored and reported;
  - the public rows `-01` to `-07` come back with their source's origin and outline box (corpus);
  - flow A on row `-04`: `import --to python`, `build`, `convert --to altium`; the origin, the outline
    vertices and each component's X and Y equal the source's (corpus).

## D5. Not done

The outline's start vertex and winding, and the frame-bound storages of change c0459 (proposal).
