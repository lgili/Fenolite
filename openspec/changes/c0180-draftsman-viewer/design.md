## Context

- **Request.** The maintainer, 2026-10-25: "conseguir visualizar o painel e draftman do altium".
- **What exists:**
  - `read.draftsman` (c0172) decodes the chunked LZ4 container to one XML document and summarises it.
  - The view of c0176 to c0179 draws boards, sheets and libraries, with units and measurement.
  - `pcb-document.md` records the Embedded Board Array's records as `UNKNOWN`.
- **The census of 2026-10-25.** It ran on the four public documents (S-0785, S-0786), read from the corpus cache and never committed, and on the two boards they were made from (S-0174, S-0187). Counts and value forms only. The facts below are written to `draftsman.md`, "Drawing geometry".
  1. **Units and frame:** every length of the board copy and of the sheets is in 1/96 inch. The board copy is in the board's own frame, Y up, so a pad's centre equals the PCB document's pad centre times 96/25.4 mm.
  2. **Bounds:** `BoardOutlineBounds` gives the outline's lower-left corner (`X`, `Y`) and its `Width` and `Height`.
  3. **Contours:** a contour is a closed run of `Segment`s.
     - A `Line` runs from its `Point` to the next segment's `Point`.
     - An `Arc` runs from its `Point` to the next segment's `Point` on the circle (`Center`, `Radius`). `Angle1 < Angle2` in degrees, and its `Point` is the end at `Angle1` (counter-clockwise) or at `Angle2` (clockwise). Measured on 60 segments.
  4. **Primitives:** a layer's primitive holds `CopperItems/PrimitiveItem` with `Unis`, `Arcs` and `Polygons`.
     - A `Uni` is a stadium: `Location` is the centre, `Size.Width` the length along `Direction` (a unit vector), `Size.Height` the width, and `Radius` the corner radius. A track of width w and length L has `Width` L + w, `Height` w and `Radius` w/2.
     - An `Arc` holds `Center`, `Radius`, `StartAngle`, `EndAngle` and `Thickness`.
     - Region, polygon and fill primitives hold no items in these documents.
  5. **Parts:** a part type's local geometry (pads, assembly and silkscreen contours) is placed by each of its `Component`s.
     - A top part: p = `Location` + R(`Rotation`)·l.
     - A bottom part: l is mirrored in Y first, p = `Location` + R(`Rotation`)·(lx, −ly).
     - Every one of the 586 parts of the four documents lands its pads on the board's pads within 0.05 unit.
  6. **Sheets:** `Size` and `Margin` hold the sheet in 1/96 inch, and `ShowZones` with `HorizontalZoneCount` and `VerticalZoneCount` the zones. Sheet coordinates are Y up from the sheet's lower-left corner: in both repositories the title block reads from the top only so, and the one note of S-0786 lies on its sheet only so. (A first reading of the census took Y down; corrected on 2026-10-25 during task 2.3.)
  7. **Items:**
     - `Line` has `StartPoint`, `EndPoint` and `StyleId`.
     - `Rectangle` has `Rect` (`X`, `Y` the lower-left corner, `Width`, `Height`), `LineStyleId` and `FillStyleId`.
     - `Text` has `Rect`, `Text`, `FontStyleId`, `Color`, `HorizontalAlignment` (`Left`, `Center`, `Right`), `VerticalAlignment` (`Top`, `Center`, `Bottom`) and `Rotation` (`Ccw0`, and so on).
     - `Picture` has `Rect` and `Bitmap`, a base64 PNG in the six measured pictures.
     - `Note` has `StartPoint` (its top-left corner), `Width`, its title in `ElementItems`, and `Elements`.
     - `LinearDimension` has `StartAnchor` and `EndAnchor`, whose `SnapId` names board geometry in the frame of the view `SnapTargetItemId`, and `DimensionReferencePoint`, relative to the first anchor in that frame. A stored `PointOnPage` can be stale.
     - A part type's `AssemblyDrawing` and `Silkscreen` hold many open strokes (`Contour` with `Thickness`).
  8. **Styles:**
     - `FontStyles` entries hold `Id`, `FamilyName` and `Size` in 1/96 inch.
     - `LineStyles` entries hold `Id`, `Color` (`A`, `R`, `G`, `B`) and `Thickness` (1/96 inch).
     - `FillStyles` entries hold `Id`, `Color` and `Pattern`.
  9. **Views:**
     - Each view holds `Location`, `Scale` (`Denominator`, `Numenator`), `CustomScale`, `UseCustomScale`, `Rotation`, `ViewSide` and `Anchor` (`Top Left` in every view measured).
     - A fabrication view names its layer by `LayerV7Id`, which matches a layer's `V7LayerId`.
     - The 12 top and bottom views of the measured sheets lie on their sheets when `Location` is the lower-left corner of the board's bounds on the sheet (Y up) and the scale is `CustomScale` when `UseCustomScale` is true, else `Numenator`/`Denominator`. Tables are placed by their lower-left corner too. This is `INFERRED`.

## Goals / Non-Goals

**Goals**
- A person opens a project's `.PCBDwf` and sees each sheet with its views, tables and title block, as a check of what the drawing will print.

**Non-Goals**
- See the proposal.

## Decisions

1. **`read.dwfdraw.read_drawing(file: DraftsmanFile) -> Drawing`.** Its plain dataclasses are:
   - `Drawing`: `pages`, `fonts`, `lines`, `fills`, `parameters`, `board`, `is_panel`;
   - `Page`: `width`, `height`, `margin`, `zones`, `items`;
   - `Item`: `kind`, `fields` (a dict of the members the scene uses);
   - `BoardCopy`: `outline` (a list of points, arcs sampled at 5° at most), `bounds`, `layers` (`name`, `v7`, `color`, `stadiums`, `arcs`), `holes` (`x`, `y`, `size`, `plated`) and `parts` (`ref`, `comment`, `side`, `contours`, `box`).

   Lengths stay in 1/96 inch as floats inside the reader. The scene rounds them to integer micrometres (`× 25400 / 96`).
2. **View transform.** For a board point (x, y), with the scale s, the view location (Lx, Ly) and the bounds (bx, by, bw, bh):
   - top view: sheet X = Lx + (x − bx)·s, sheet Y = Ly + (y − by)·s, both Y up;
   - bottom view: sheet X = Lx + (bx + bw − x)·s.

   A view rotation other than `Ccw0` turns the view a quarter turn counter-clockwise per step inside its box. The scene flips the sheet once: scene Y = sheet height − sheet Y. A drill view draws one symbol per hole size: a circle, a cross, a triangle, a square and so on, by size order. These are Fenolite's drawings.
3. **Assembly views.** For each part on the view's side, the scene draws its assembly contour, else its silkscreen contour, else its box, with its designator at the box's centre. The outline is drawn with the view's line style, and holes as circles.
4. **Tables.** Each table is a grid at its `Location`, with the title above it.
   - **Drill table:** symbol, count, hole size (in the document's `MeasurementSystem`) and plated, one row per size and plating.
   - **Layer stack legend:** layer name, kind and thickness, one row per stack layer.
   - **BOM:** comment, designators and quantity, from the parts grouped by comment.

   Cell sizes are Fenolite's: text of 8 units, rows of 14 units. A table's `Location` is its lower-left corner.
5. **Texts.** Each `=Name` of a text that names a parameter (the document's, then the project and PCB parameters of `ParametersData`) shows its value; other text stays. Alignment places the text in its `Rect`; it breaks only at its own line breaks (no member asks for word wrap). A note's elements are wrapped to its `Width` by an estimate of 0.55 of the font size per character. The font is the style's family and size, in the browser's font.
5a. **Dimensions.** A dimension whose two snaps name a line or points of a drawn view is drawn from them: the extension lines from the snapped points along `ExtensionsDirection` to the line through the reference point, the value measured on the board in the dimension's `Units` (Fenolite's number format: two decimals of a millimetre, one of a mil). Other dimensions are left out with a note.
6. **Scene.** It is the library form of c0179, with `lib` `drawing`. Each item is a page's schematic-form scene:
   - `sheet.color` white, `sheet.workspace` grey;
   - no grid;
   - `sheet.origin` at the sheet's lower-left corner (the page's default), so the status line reads sheet coordinates as Altium writes them.

   The page needs no change beyond the item list's title (Sheets).
7. **Panels.**
   - The Altium read of a board does not open `EmbeddedBoards6`. `cmd_view` reads the stream size through `read.cfb` when the document is a compound file, and adds the note when it holds more than its empty form.
   - A drawing with `IsPanel` true gets the same note.

## Evidence

- `tests/unit/backends/altium/test_dwfdraw.py` builds an authored document: XML written in the test, stored in one chunk of flag 0. It checks the reader on that document: a top and a bottom part, an arc outline, a text with a parameter, a view and a page.
- `tests/corpus/test_draftsman_draw.py` checks, when the corpus is cached:
  - the placement facts 1 and 5 on S-0785, S-0786, S-0174 and S-0187;
  - that each public document gives one scene item per page.

## Risks / Trade-offs

- **Two repositories, one tool generation.** Format versions 21 and 22 are covered, and a later Altium may move members. The reader skips what it does not find and counts it in the notes.
