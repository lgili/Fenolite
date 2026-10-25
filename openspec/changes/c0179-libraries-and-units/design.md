## Context

- **Request.** The maintainer, 2026-10-25: libraries in the viewer, millimetres and mil switchable as in Altium, and measurement everywhere, so that a person can check the sizes an agent gave pads and parts.
- **What exists** on `c0178-native-themes`:
  - The backends read `.PcbLib`, `.kicad_mod`, `.SchLib` and `.kicad_sym` into a `Library` of `FootprintDef` and `SymbolDef`.
  - `read_schlib` keeps each Altium symbol's records with their owner tree, as `read_schematic` does for a sheet.
  - A one-part board can be built from a `FootprintDef` (a probe of 2026-10-25): placed at the origin, both backends' `board_pads` give its pad copper, and `build_scene` draws it. This holds for a QFP of a `.PcbLib` and one of a `.kicad_mod`.
  - The page measures in millimetres on boards only. The schematic status line shows mil.

## Goals / Non-Goals

**Goals**
- A person opens a footprint, clicks a pad and reads its exact size in either unit. They measure a pitch from centre to centre and a part's extent.
- A person browses the symbols of a library as they look on a sheet.

**Non-Goals**
- See the proposal.

## Decisions

1. **Module `fenolite.view.library`.**
   - `footprint_library_scene(path, *, palette)` and `symbol_library_scene(path, *, palette)` return `fenolite.view_library.v0`:
     - `kind` `library` and `lib` `pcb` or `schematic`;
     - `meta`: name, SHA-256 of the file (of the sorted file list and bytes for a `.pretty` folder), backend, evidence, counts and notes;
     - `items`: `name`, `description`, `info` (rows for the panel) and `scene`.
   - `summary(scene)` gives `kind`, `lib`, `counts` and the first 50 names.
2. **Footprint items.**
   - **Board:** each `FootprintDef` becomes a `FootprintInstance` at (0, 0), angle 0, top side, with its pads, graphics and bodies. It sits on a board whose layers are the layers its pads and graphics name.
   - **Layer kind by name:**
     - `*.Cu` copper;
     - `*.SilkS` or `*.Silkscreen` silkscreen;
     - `*.Mask` soldermask;
     - `*.Paste` solderpaste;
     - `*.CrtYd` courtyard;
     - `*.Fab` fabrication;
     - `Edge.Cuts` edge;
     - `Mech*` mechanical;
     - else user.
   - **Drawing:** the board goes to the reading backend's `board_pads` and to `build_scene`, then to the palette of c0178.
   - **Info:** the pad count, the copper extent and the courtyard extent (when the footprint has one), in nanometres.
   - A footprint that the frame cannot place is an item with no scene and a note.
3. **Symbol items.**
   - **Altium:** each `SchLibComponent` is drawn by the c0177 scene code, through a document view of its records (`_LibraryDocument`, the stream `data`).
     - There is no paper frame. The sheet is the symbol's box, grown by 10 units on each side, and Y is the file's Y negated.
     - A symbol with `PARTCOUNT − 1 > 1` gives one item per part (`Name : Part A`, …), drawn with that part.
   - **KiCad:** each top-level `symbol` of the `.kicad_sym` is drawn by `kicad_schematic.symbol_scene(node, unit, style)` at the origin with the identity placement.
     - Its fields are placed at the library positions (Y up, turned down).
     - A derived symbol (`extends`) draws its parent's units.
     - One item per unit when the symbol has several.
4. **Pads in board scenes.** `build_scene` adds `pads`, one entry per `BoardPad`:
   - `label` (`REF-number`, as the pad primitives are labelled), `x`, `y` (µm), and `w`, `h`, `drill` in nm from the model `Pad` that `footprint_id` and `pad_id` name;
   - `shape`, `rot` (degrees, the board rotation), `kind`, `layers`, `net`, `comp`, `ratio` (the corner ratio in parts per million, or `null`);
   - `slot` (the slot length in nm) when the hole has two ends.
5. **Units on the page.**
   - **State:** `UNIT` is `mm` or `mil`. The Units button in the top bar and `Q` switch it. It is stored in `localStorage` under `fenolite.view.unit`, read and written inside `try`, and the default is `mm`.
   - **Display:** `fmtLen(mm)` gives `"1.200 mm"` (3 decimals) or `"47.24 mil"` (2 decimals). `fmtNm(nm)` does the same from nanometres, so pad sizes keep the model's exactness.
   - **Where it applies:**
     - the cursor (board: X right, Y down from the board's frame; sheet: from the bottom-left corner, Y up, as the file holds it);
     - the grid of a sheet;
     - measurement;
     - the Properties panel: track width, arc radius, via and hole diameter, pad size and drill, part position and extent.
6. **Measurement.**
   - `M` and the Measure button work on boards, sheets and library items.
   - A click sets a point. The point snaps to the nearest candidate within 8 px:
     - a pad centre;
     - a vertex of a line or polygon;
     - a circle or ellipse centre;
     - a text anchor.
   - The readout shows the distance, dx and dy in the current unit. A third click starts again, and `Esc` clears.
7. **The page and libraries.**
   - **Opening a library:** the Navigator becomes the library's item list, with a filter, the item's summary under each name, and the first item opened.
   - **Opening an item:** a click loads its scene into the board or schematic drawing, keeping the list. The bottom bar shows the board's layer tabs for a footprint, or the project's tabs for a symbol.
   - **Live reload:** keeps the selected item by name.

## Evidence

- **Library scenes:** `INFERRED`. `tests/unit/view/test_library.py` checks:
  - **Footprints:** on `tests/data/altium/blink/blink.PcbLib` and a `.pretty` folder of the test data, one item per `FootprintDef`. Each item's `pads` holds every model pad with its exact `w`, `h` and drill, and pad centres equal to the model positions in µm.
  - **Symbols:** on `blink.SchLib` and `tests/data/libs/Mini_v9.kicad_sym`, one item per symbol and part. Each item's pin objects count the symbol's visible pins.
- **Page:** `test_page.py` runs `fmtLen` and `fmtNm` through Node when `node` is on the path, else checks the definitions. A person reviews pads, units and measurement in a browser.

## Risks / Trade-offs

- **Large libraries make large pages.** A library of 500 footprints embeds 500 scenes in an export. The live server serves the library scene once, then caches it by the file's hash as it does for boards.
