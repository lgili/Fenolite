## ADDED Requirements

### Requirement: Footprint items projected on request
`backends.kicad.fpitems.with_footprint_items(design) -> Projection` SHALL return a copy of a design that was read from a KiCad board in which every footprint holds, as read-only projections of its opaque children, the graphics, the texts and the corner ratios of `design-model`, "Graphics and texts of a footprint instance" and "Corner ratio of a rounded-rectangle pad". No reader and no writer calls it by itself.
- One `Graphic` per opaque `fp_line`, `fp_arc`, `fp_circle`, `fp_rect` and `fp_poly` child, with the mapping that `mod.read_footprint` uses for a library footprint (`_fpmap.read_graphic`), in child order. The points are the file's own: a board footprint stores its children in the pad frame, mirrored on the bottom side.
- One `Text` per opaque `fp_text` child that holds a font size and a thickness: the string as written, the layer, and the angle taken from the board angle of the file to the footprint (`pad_angle_from_board`).
- `Pad.corner_ratio` from the pad's opaque `roundrect_rratio`, in ppm.
- A child that `Graphic` or `Text` cannot hold (a stroke that is not solid, a polygon with an arc, `fp_text_box`, `dimension`, a curve, an inexact number) MUST be left out and counted by head in `Projection.skipped`; `Projection.projected` counts what was projected per kind.
- A footprint that holds no `kicad` bag was not read from a KiCad board (the stored board of an Altium build holds its own graphics): it MUST be returned as it is, neither projected nor marked.
- Every slot MUST stay as it was, so `write_board` of the projected design gives the text of `write_board` of the design. Each projected footprint MUST carry the pair `("fenolite.projected", "footprint-items")` in its `kicad` bag.
- On a write, a footprint that carries the pair is checked as "Projected fields on write" says: the writer projects again and compares `graphics`, `texts` and the pads' `corner_ratio`; a difference MUST give `kicad.board.projection-read-only` naming the field and the footprint's locator. A footprint without the pair is written without a look at the three fields.
- Ids follow "Placed copies of library definitions" and the scoped ids of a board footprint's pads: with a uuid `derived_id(prefix, "kicad", "<footprint uuid>:<uuid>")`, without one a content id scoped to the footprint.
- The module MUST declare its evidence (`H-K-PCB-FPGFX`, `INFERRED`), and no module of `backends.kicad` on the read or write path of a board may import it.

#### Scenario: Projection equals the library reading
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_fpitems.py -k library` places each footprint of the mini library with `embed.place_footprint` on the top side at angle 0 and projects the result
- **THEN** the projected graphics have the kinds, layers, points, widths and fill flags of `FootprintDef.graphics` of the same definition, in order, and every rounded pad has the ppm of its `roundrect_rratio`

#### Scenario: The projection changes no byte
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_fpitems.py -k no_byte` writes every board under `tests/data/kicad/board/` with and without the projection
- **THEN** the two texts are equal for each board, on targets 9 and 10

#### Scenario: An edited projection is refused
- **GIVEN** a projected design in which one footprint graphic is moved by 1 mm
- **WHEN** `write_board` runs
- **THEN** `LossyWriteError` is raised with one `kicad.board.projection-read-only` issue that names `graphics`

#### Scenario: Builds are pinned
- **WHEN** `uv run pytest tests/unit/lens/test_build_bytes_pinned.py tests/unit/lens/test_build_determinism.py` runs after this change
- **THEN** every entry of the `KICAD` table of change c0123 holds without an edit
