## Context

- **Request.** On 2026-10-25 the maintainer asked for a schematic viewer that looks like Altium Designer, the maintainer's preferred tool. The board viewer of c0176 is its frame: the project tree on the left, a canvas in the middle, a bar along the bottom, live reload and a standalone export.
- **What exists.** These live on the c0176 branch, which is based on `release-0.5.0`:
  - `backends.altium.read.sch.read_schematic` reads a `.SchDoc` in either form into typed records with an owner tree. `SchDocument.shown_children(component)` keeps the children of a component's own part and display mode. Each record keeps its own colours, line width, font id, orientation and justification.
  - `backends.altium.adapter.connectivity.local_nets(document, groups)` gives the nets of one sheet, with their pins and identifiers. `Lines.groups(junctions)` gives the wire groups.
  - `backends.altium.read.sheet` holds the drawing areas of `SHEETSTYLE` 0 to 17, the four line widths of `LINEWIDTH` and the nine justifications of a text.
  - `docs/formats/altium/schematic-ascii.md` records:
    - the units and the Y-up frame;
    - the colours seen in files;
    - the font table;
    - the meanings of `ELECTRICAL`, `PINCONGLOMERATE` and the pin edge codes;
    - the power-port styles and orientations;
    - the sheet-symbol, sheet-entry and port geometry.
- **Gaps.**
  - No source gives the drawn shape of a power port, a port, a sheet entry or a pin mark.
  - No source gives the offsets of a pin's name and number, the margin and zone count of a standard sheet, or the layout of the built-in title block.
  - The view draws each of these its own way and says so in the notes. A text's width is not known without the font, so a box that holds text is an estimate.

## Goals / Non-Goals

**Goals**
- A person who knows Altium reads a sheet in the viewer without having to learn it: the same paper, colours, fonts, symbols and interaction habits.
- The scene is data. An agent reads the summary in the reply: the part, pin, wire and net counts.

**Non-Goals**
- See the proposal.

## Decisions

1. **Module `fenolite.view.schematic`.** It holds `build_schematic_scene(document, *, name, data, evidence) -> dict` and `summary(scene)`. It imports `backends.altium.read.sch`, `backends.altium.read.sheet` (constants only), `backends.altium.adapter.connectivity` and `.parts`, and the standard library. The layering table already allows `view → backends*`.
2. **The scene format, `fenolite.view_schematic.v0`.** `kind` is `"schematic"`, so the page tells it from a board scene.
   - **Units:** integer micrometres. The origin is the sheet's top-left corner and Y grows downwards: `y = H − y_file`. One file unit (10 mil) is 254 µm, and `SchLength.nm()` is rounded to the micrometre.
   - **`sheet`:** `w`, `h`, `color`, `grid` (µm, 0 when not shown), `border`, `margin`, `zones` `[nx, ny]`, `title_block`, `style` (the paper's name).
   - **`fonts`:** one entry per entry of the font table, in `FONTID` order: `name`, `size` (points), `em` (µm), `bold`, `italic`, `underline`. The em is 9 mil per point (Fenolite's choice): a 10-point capital of Times New Roman is then about 63 mil wide. That stays inside the 70 mil per character that the Altium writer reserves (`symbols.CHAR_WIDTH`), so the pin texts of a 100-mil pitch keep a gap, as they do in Altium. A plain `size / 72` inch made neighbouring pin numbers touch.
   - **`prims`:** the drawn primitives, in the file's stream order (template first, then the sheet's records). Each one is an object with a kind `k`, its geometry, `c` (stroke colour `#rrggbb`), `w` (µm), `f` (fill colour or `null`) and `o` (the index of its object, or −1). The kinds are:
     - `l`, a polyline: `p`, with `d` (line style 0 to 3) and the line shapes `s0` and `s1`;
     - `g`, a polygon: `p`;
     - `r`, a rectangle: `b = [x0, y0, x1, y1]`, with `rr = [rx, ry]` for round corners;
     - `e`, an ellipse: `x`, `y`, `rx`, `ry`;
     - `a`, an arc of an ellipse: `x`, `y`, `rx`, `ry`, then `a0` and `a1` in degrees, counter-clockwise in the file's Y-up frame; `pie` when filled;
     - `b`, a Bezier curve: control points `p`;
     - `t`, a text: `x`, `y`, `s` (the string), `font` (index), `rot` (quarter turns counter-clockwise), `h` (`left`, `center`, `right`), `v` (`bottom`, `center`, `top`) and `ol` (the indexes of overlined characters);
     - `x`, a text frame: `b`, `s`, `font`, `tc`, `f`, `bc` (border colour or `null`), `wrap`, `al` and `m`;
     - `i`, an image: `b` and `src` (a `data:` URL of an embedded image, or `null`).
   - **`objects`:** the things a click selects. Each holds `k` (one of `comp`, `pin`, `wire`, `bus`, `entryline`, `harness`, `label`, `power`, `port`, `sheet`, `entry`, `junction`, `noerc`, `text`, `graphic`), `net` (index or −1), `comp` (index or −1), `b` (a box in µm) and `info` (name, value pairs for the Properties panel). A sheet symbol also holds `file`.
   - **`comps`:** `ref` (with the part letter of a multi-part component), `comment`, `lib`, `description`, `footprint`, `params`, `b`.
   - **`nets`:** `name` and `pins` (`REF-number`).
   - **`bounds`:** the sheet box, grown to hold every primitive.
   - **`meta`:** `name`, `sha256`, `bytes`, `backend` `"altium"`, `evidence`, `counts`, `notes`.
3. **Colours and widths come from the file.**
   - A record's `COLOR` and `AREACOLOR` are drawn as they are; Altium writes them on every record it saves.
   - A missing key reads as 0, black, as the reader gives it. The one exception is the sheet's area colour: when `AREACOLOR` is missing it is the off-white `16317695` seen in files, with a note, so a hand-authored sheet is not a black page (c0146, `H-A-SCHDOT-AREACOLOR`).
   - `LINEWIDTH` 0 to 3 is 4, 10, 20 and 40 mil (`read.sheet.LINE_WIDTHS`). Wires and pins are at least 10 mil, buses at least 20 mil, signal harnesses at least 40 mil. The page draws every line at least one pixel wide.
4. **Texts.**
   - **Font:** the record's `FONTID` in the sheet's font table, or the system font. Its em follows the fonts entry above. The page draws it with the browser's font of that name, falling back to a serif font.
   - **Anchor:** `JUSTIFICATION` 0 to 8 sets the anchor of a label: bottom, center and top, each by left, center and right (`read.sheet._JUSTIFY`). Other texts are anchored at their bottom-left corner. `ORIENTATION` turns a text about its location.
   - **Special strings:** a text that starts with `=` names a parameter. A component's parameter names one of that component's parameters. A label or template text names a parameter of the sheet. `DocumentName` is the file name.
   - **Overlines:** a pin name with a `\` after a character draws that character overlined, without the `\`.
5. **Components.**
   - **Children drawn:** those of `SchDocument.shown_children` (the component's own part and display mode), except the model records 44 to 48.
   - **Designator:** a multi-part component (`part_count > 1`) shows its part letter, `A` for part 1.
   - **Left out:** hidden parameters and hidden pins.
   - **IEEE symbols** (record 3) are not drawn, and are counted in a note.
   - **Box:** the union of the boxes of its graphics and pins, without its texts.
6. **Pins.**
   - **Line:** from `LOCATION` (the body end) to `hot_end`.
   - **Edge marks:** outer edge 1 is a dot at the body end, and the line starts after it. Inner edge 3 is a clock wedge inside the body. Outer edge 4 is the active-low input flag and outer edge 17 the active-low output flag.
   - **Texts:** the name sits inside the body, 5 units (50 mil) from the body end, centred on the line. The number sits outside, 1 unit above the line, starting 3 units from the body end. A vertical pin turns both by a quarter turn. `name_shown` and `designator_shown` decide each text.
   - **Font and colour:** the sheet's system font, in the pin's colour.
7. **Connectivity symbols.** These are Fenolite's drawings, in the record's colour and on the 10-unit grid. Each power port and sheet entry is drawn in a local frame turned by its orientation.
   - **Power ports**, by `STYLE`:
     - 0: a circle;
     - 1: an arrow;
     - 2: a bar;
     - 3: a wave;
     - 4: power ground (three bars that shorten);
     - 5: signal ground (a triangle);
     - 6: earth (a bar with three ticks).
     - GOST 7 to 10 are drawn as 1, 4, 6 and 2.

     With `SHOWNETNAME`, the net name sits past the symbol's end.
   - **Ports:** a box `WIDTH` by `HEIGHT` centred on the location's line. `STYLE` 1 to 3 points the left end, the right end, or both. Styles 5 to 7 point the top end, the bottom end, or both, and run along Y. Styles 0 and 4 are square-ended. The name is centred in `TEXTCOLOR` with the port's font.
   - **Sheet entries:** a pentagon of 12 by 6 units inside the symbol, at `side_point`. It points outwards for an output, inwards for an input, both ways for a bidirectional entry, and is square for an unspecified one. Its name sits 3 units past it.
   - **Others:**
     - a junction is a filled dot of radius 1.5 units;
     - a No ERC mark is a cross of 3 units;
     - a bus entry is a line from `LOCATION` to `CORNER`;
     - a harness connector is a filled box with its entries' names inside.
8. **The sheet.**
   - **Size:** `custom_size` when set, else the area of `SHEETSTYLE` in `read.sheet.SHEET_STYLES`, turned for `portrait`. An unknown style is A4, with a note.
   - **Template:** the records owned by a `Template` are drawn as ordinary graphics.
   - **Built-in title block:** with `TITLEBLOCKON`, Fenolite draws its own block of 350 by 80 units in the bottom-right corner, inside the border. It holds `Title`, `Size`, `Number`, `Revision`, `Date`, `File`, `Sheet of` and `Drawn By` from the sheet's parameters.
   - **Border:** with `BORDERON`, the margin is `CUSTOMMARGINWIDTH` for a custom sheet, else 20 units. The zones are `CUSTOMXZONES` by `CUSTOMYZONES`, else `round(w / 287.5)` by `round(h / 190)` (4 by 4 on A4), numbered left to right and lettered top to bottom.
9. **Nets.**
   - **Source:** `local_nets(document, part_groups(document))`.
   - **Wires:** each wire group (`Lines.groups` with the junctions) takes the net of the first pin end or identifier point that lies on it. A group that touches neither is a net of its own with no name.
   - **Name:** the first identifier, in the order label, power port, off-sheet connector, port, sheet entry. A net without one is named `Net<REF>_<pin>` after its first pin. A net of wires only is named `""`.
   - **Objects:** a pin takes the net of its `(component, designator)`. A label, power port, port or entry takes the net of its record. A junction takes the net of the wire it lies on. Buses and harnesses have no net.
10. **The page.** `page.html` keeps one file. `loadScene` turns to the schematic drawing when `scene.kind == "schematic"`.
    - **Hidden in schematic mode:** the board's 3D, flip, other-side and layer-set controls.
    - **Workspace:** grey `#4a4d52`, with the sheet drawn on it in its area colour.
    - **Grid:** lines in the sheet colour darkened by 8 %, at the visible grid size, shown once they are at least 8 px apart.
    - **Drawing:** in sheet order. Texts are set in screen space at the zoomed em, so small sizes stay sharp, and a primitive outside the window is skipped.
    - **Mouse:**
      - wheel zooms about the cursor; drag (left or right button) pans;
      - a click selects the top object under the cursor, preferring pins, then wires and labels, then the part;
      - a click on an object with a net highlights that net: the rest of the sheet dims to 25 %;
      - a double click on a sheet symbol opens the document of its file name;
      - a double click on a part opens the project's first board and selects the part of that designator there. From a board, a double click on a part finds the schematic that holds its designator.
    - **Panels:**
      - **Properties:** the selected object's `info` and its part's parameters.
      - **Navigator:** in the left panel, under the tree, the parts and nets of the sheet. A net of one pin with a made-up name (an unconnected pin) is not listed. A click zooms to a part or highlights a net.
    - **Bottom bar:** the project's viewable schematics as sheet tabs.
    - **Status line:** the cursor in mil, Y upwards from the bottom-left corner as in the file, and the grid.
    - **Keys:** `F` fit, `Esc` clear, `PgUp` and `PgDn` zoom.
11. **Tree and command.**
    - `project.VIEWABLE` becomes `{pcb, schematic}`, with a schematic viewable only when it is an Altium `.SchDoc`.
    - `project.load_tree` accepts a lone `.SchDoc` as a tree of one document.
    - `cmd_view.scene_of` builds a schematic scene for a `.SchDoc`.
    - `--doc` names any viewable document. `first_viewable` still prefers a board.
    - The reply's `summary` is `schematic.summary(scene)` for a schematic: `kind`, `counts`, `bounds_um`.

## Evidence

- **Scene:** `INFERRED`. `tests/unit/view/test_schematic.py` checks it on the test sheets and on an authored ASCII sheet.
  - **Counts:** one object per component, pin shown, wire, bus, net label, power port, port, junction, No ERC, sheet symbol and entry; and primitives of every graphic kind.
  - **Nets:** the nets equal `local_nets`, and each wire takes the net of the label on it.
  - **Positions:** a pin's line runs from its location to its hot end, in the scene's frame.
- **Page:** a person reviews it in a browser on the test project `tests/data/altium/hier/`, and on an Altium project of the maintainer's that saved sheets hold. The date and the browser are recorded.

## Risks / Trade-offs

- **Fonts.** The browser draws a named font only when the machine has it. Without Times New Roman, texts fall back to a serif font and are a little wider.
- **Shapes that are Fenolite's.** A power port, a port, an entry or a title block may not match Altium to the pixel. The notes of every schematic scene say which drawings are Fenolite's.
