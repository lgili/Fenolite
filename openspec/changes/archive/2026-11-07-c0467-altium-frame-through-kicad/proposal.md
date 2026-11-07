# c0467: Altium frame and origin survive the KiCad round trip

## Why

The round trip of public row `-04` through KiCad moves every Y by +29.528 mil (S-2191): the outline's box,
relative to the origin, is 0, −29.528 … 1023.622, 423.228 mil in the source and 0, 0 … 1023.622, 452.756
mil in the document written back.

- **The way to KiCad.** The conversion keeps the document's absolute coordinates, Y negated (`import.md`:
  no origin is subtracted). The import keeps the origin (`ORIGINX`, `ORIGINY`) in the board's `altium` bag,
  but no carrier takes it into the KiCad board (S-2261).
- **The way back.** `lower` writes a board read from KiCad in `Frame.on_units`: the outline's lowest X and
  Y move to (1000 mil, 1000 mil), and the origin is written at that corner (change c0090,
  `pcb-document.md`, "Frame").

Six of the seven public rows hold an origin away from the outline's low corner (S-2260): `-01` −100, 0
mil; `-02` −0.656, 0.119; `-03` −890, −885; `-04` 0, 29.528; `-06` 629.921, 472.441; `-07` 452.756,
197.835. Only `-05` holds it at the corner. Every round trip therefore moves the absolute coordinates of
all seven rows, and the coordinates relative to the origin of six.

Flow A (`import --to python`, `build`, `convert --to altium`) does the same (S-2261): the Python import
keeps the board's carried properties as `design.verbatim` items, the build writes them and keeps the
absolute coordinates, and the way back re-anchors.

## What

- **To KiCad.** The conversion carries in the board property `Fenolite.Altium.Frame` the source's origin,
  in the frame of the design, and the low corner of the board's edge.
- **Back to Altium.** A board that carries it is written in the document frame (`Frame.document()`: the
  KiCad coordinates are the document's, Y negated), with the origin at the carried origin moved by the
  translation of the edge's corner. A board moved in KiCad keeps its origin where it was relative to the
  board.
- **Guard.** When the document frame would put a point of the outline at a negative coordinate, the board
  is written as before, anchored at its corner, and the report counts the change under `outline`.
- **Flow A.** A test runs flow A on row `-04` and compares the absolute coordinates of the origin, the
  outline and the components with the source's.

## Not in this change

- The outline's start vertex and winding (S-2191 notes a reversed winding): the shape is the same.
- The storages change c0459 counts frame-bound (`SmartUnions`, …) stay lost. A follow-up may carry them
  now that the frame survives.

## Impact

- New `src/fenolite/convert/altium_frame.py`; `to_kicad.py` writes the carrier, `to_altium.py` reads it.
- `backends/altium/lower.py`: `write_design(frame_origin=…)`.
- `tools/schema_formats.py` and `schemas/README.md`: the `fenolite.altium-frame.v0` format.
- Docs: `pcb-document.md` ("Frame"), `import.md`, `docs/evidence/sources.md` (S-2260 to S-2263), CHANGELOG.
