## Why

On 2026-10-25 the maintainer asked for the viewer to show Altium's panels and Draftsman drawings. The two stand on different footing.

- **Draftsman (`.PCBDwf`).** Change c0172 reads the container and summarises the sheets. A census of the four public documents of S-0785 and S-0786, compared with the boards of S-0174 and S-0187 (2026-10-25), shows that a document holds its own copy of the board geometry, the units of that copy and the placement of every part. A sheet can therefore be drawn from the document alone.
- **The native panel (Embedded Board Array).** Its records are `UNKNOWN`: no public page describes them and no public file holds one (`pcb-document.md`, `H-A-PANEL-RECORD`). Part Q of `docs/evidence/altium-pcb.md` measures them by observation. The kit of phase A was handed to the maintainer on 2026-10-25. This change draws no array; it states when a board holds one.

## What Changes

- **Draftsman geometry reader, `fenolite.backends.altium.read.dwfdraw`.** From a decoded document it reads:
  - the font, line and fill styles;
  - the document parameters;
  - the pages with their size, margins, zones and items. The items are lines, rectangles, texts, pictures, notes, linear dimensions, the four views and the drill, layer stack and BOM tables.
  - the document's copy of the board:
    - the outline as a closed contour of lines and arcs;
    - the layers with their primitives (stadium shapes and arcs);
    - the holes;
    - the parts, with their assembly, silkscreen and bounding geometry placed on the board.

  It runs no tool and opens no other file.
- **Drawing scenes, `fenolite.view.drawing`.** A `.PCBDwf` becomes a library-form scene (`lib` `drawing`) with one item per sheet. Each sheet is a schematic-form scene (c0177) in micrometres, Y down from the sheet's top-left corner.
  - **Assembly views:** the board outline, the parts of the view's side with their designators, and the holes.
  - **Fabrication views:** the outline and the primitives of the view's layer.
  - **Drill views:** the outline and one symbol per hole size.
  - **Tables:** the drill table, the layer stack legend and the bill of materials, drawn from the document's own data.
  - **Other items:** texts (with `=Parameter` filled in), lines, rectangles, pictures, notes and linear dimensions.
- **The page.** A drawing opens like a library: its sheets in the left panel, units and measurement as in c0179.
- **Panels.** A board whose `EmbeddedBoards6` holds data, and a drawing whose `IsPanel` is true, get a note: they hold an Embedded Board Array that Fenolite does not draw until Part Q is measured.
- **Tree and command.** `.PCBDwf` documents become viewable, and `fenolite view` replies with a drawing summary (`kind` `drawing`, sheets, items per kind).

## Capabilities

### New Capabilities

- `draftsman-viewer`: the geometry reader, the drawing scenes and the panel note.

### Modified Capabilities

- `cli-contract`: ADDED "View command shows Draftsman drawings".

## Non-goals

- Drawing an Embedded Board Array (waits on Part Q phase A, the maintainer's kit).
- Writing Draftsman documents, Import Changes, or recomputing views from the PCB document. The document's own copy is drawn, as Altium shows it before a refresh.
- Callouts, transmission line tables, wiring diagrams and 3D projections. They are counted in a note.
- Exact text metrics. Texts use the font family the document names, in the browser's font.

## Evidence level required

- **Geometry and placement:** `CORPUS-VERIFIED` where both public repositories show a fact, `INFERRED` where one does. The facts are recorded in `docs/formats/altium/draftsman.md`, "Drawing geometry".
  - The pad centres of the copy equal those of the boards of S-0174 and S-0187.
  - Every part's pads land on the board's pads by the placement rule: 586 parts of the four documents.
- **The page's view placement** (top-left anchor, scale) is `INFERRED`. The maintainer's kit round F0.5 confirms it.

## Impact

- **New:**
  - `src/fenolite/backends/altium/read/dwfdraw.py` and `src/fenolite/view/drawing.py`;
  - `tests/unit/backends/altium/test_dwfdraw.py` (an authored document) and `tests/corpus/test_draftsman_draw.py` (the public documents, when cached).
- **Changed:**
  - `docs/formats/altium/draftsman.md`, `docs/hypotheses.md` and `docs/evidence/altium-draftsman.md`;
  - the view package and page, `cmd_view`, `docs/viewer.md`, `docs/cli-contract.md`.
- **Size:** 5 design-days.
