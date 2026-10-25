# Board and schematic viewer

`fenolite view` shows the boards, the sheets, the libraries and the Altium Draftsman drawings of a project in a web browser, without the tool that made
them: an Altium project on a machine without Altium, a KiCad board in a review, a board or a sheet an agent
just wrote. It reads every board through the neutral model (change c0176), draws every Altium `.SchDoc` in
the manner of Altium Designer (change c0177) and every KiCad `.kicad_sch` in the manner of KiCad (change
c0178). Each document keeps the look of its own tool (see "Colours"). It writes no design file and opens no
connection beyond the loopback address.

```bash
fenolite view MyProject.PrjPcb --serve              # live: http://127.0.0.1:8765/, reloads when a board is saved
fenolite view board.kicad_pcb --export board.html --confirm    # one standalone page to open or send
fenolite view MyProject.PrjPcb --json               # for an agent: the documents and a scene summary
fenolite view MyProject.PrjPcb --doc Power.SchDoc --json        # the parts, pins, wires and nets of one sheet
fenolite view Assembly.PCBDwf --export assembly.html --confirm  # an Altium Draftsman drawing, sheet by sheet
fenolite view board.kicad_pro --serve --theme my-theme          # a KiCad project in your own KiCad colours
```

## Colours

Each document is drawn in the colours of the tool that made it (change c0178):

| document | colours |
|---|---|
| KiCad board, KiCad sheet | Fenolite's palette in the manner of KiCad: a dark navy board with red front and blue back copper, a cream sheet with a dotted grid, green wires, dark red symbols on a pale yellow body, stroke text. With `--theme`, your own KiCad colour theme |
| Altium board | Fenolite's palette in the manner of Altium Designer: black background, red top and blue bottom layers, yellow overlay |
| Altium sheet | the colours its records hold, as Altium draws them (c0177) |

`--theme NAME` takes a KiCad colour theme: a `.json` file, or the name of a theme in the `colors` folder of
your KiCad settings (`~/.config/kicad/<version>/colors` on Linux, `%APPDATA%\kicad\<version>\colors` on
Windows, `~/Library/Preferences/kicad/<version>/colors` on macOS). With it, a KiCad project looks colour for
colour as in your KiCad. The palettes are Fenolite's own: no value of KiCad's or Altium's built-in themes is
copied (`docs/formats/kicad/color-theme.md`).

## The page

- **Projects panel** (left). The project's documents, grouped as the native tools group them: Source
  Documents (schematics, boards, harnesses), Libraries, Settings (output jobs, rules, stack-ups, library
  tables), Documentation (drawings, annotations) and Other. A board opens on click; any other document
  shows its kind, path and size. A document listed by the project but missing from the folder is grey.
- **Layer tabs** (bottom). One tab per layer with its colour.
  - A click on a tab makes that layer current: it is drawn last, above the others.
  - A click on the swatch, or a right click, shows or hides the layer.
  - `Shift+S` shows the current layer alone; `+` and `-` step through the visible layers.
  - **LS** offers layer sets: all layers, signal layers, the top side, the bottom side, the defaults.
- **Board view.** Wheel to zoom, drag to pan, click a pad or track to highlight its net (or a part's own
  drawing to highlight the part). **View: Top / Bottom** (`B`) turns the board over: the other side is drawn
  under the visible one at the opacity of the **Other side** slider. **Measure** (`M`) gives the distance
  between two clicks. **Search** finds a part by reference or a net by name.
- **3D** (`D`). The board as a slab of its stack-up's thickness (1.6 mm, stated, when the file has none),
  its faces textured with the copper, mask, silkscreen and drills of each side, and every part body that the
  model holds, extruded from its outline between its standoff and its height. No 3D model file is read.
- **Findings and notes** (left). With `--overlay REPLY.json`, the clearance (red) and creepage (blue) paths of
  a `fenolite analyze` reply are drawn; a pair that an error or a warning names is marked as a finding.
  The notes say what the scene had to assume.

## What the scene shows, and what it states

| item | drawn from | stated when |
|---|---|---|
| pads | the backend's board frame: the copper of each pad on each layer | — |
| mask and paste openings | the pad's own mask and paste layers | derived from the pad kind, with no expansion, when the board holds no mask layer (Altium boards today) |
| tracks, arcs, vias, holes | the model | — |
| zones | the fills saved in the file | a zone without a fill is drawn as a dashed outline and counted; refill it in its tool |
| graphics and texts | the model, footprint items placed by the footprint's position and angle | texts use Fenolite's own single-stroke font; a text on a back layer is drawn mirrored |
| bodies | the model's body outlines and heights | — |

The palette is Fenolite's own. Coordinates are in the board frame of the model: millimetres from the
outline's top-left corner, with Y growing downward.

## Nets across sheets and the board

In an Altium project a net crosses sheets through ports, sheet entries, power ports, net labels and harnesses
(change c0185). The viewer names every net of a sheet by its project net, as the project compiles (`build` and
`check` see the same nets):
- **The Navigator** lists each net with its pin count on the sheet and the number of sheets it reaches; a
  local net whose label differs shows its project net (`N1 → RESET_N`).
- **A click on a net** shows its pins on the sheet and in the whole project, and links to the other sheets it
  reaches.
- **The selection follows you**: a net chosen on a sheet is selected on the next sheet or board you open, and a
  net clicked on the board is selected on the sheets. With `--serve`, the pages of other tabs follow too. `Esc`
  clears it.
- A project that does not compile keeps each sheet's own nets, with a note.

## Assembly variants

An Altium project's variants (`[ProjectVariant<n>]` of the `.PrjPcb`, change c0186) get a selector in the
toolbar, `[No Variations]` first; the choice applies to every sheet and to the board:
- a part the variant does not fit is crossed out in red on its sheet and on the board, where it is also dimmed,
  and its body is left out of the 3D view;
- a part's Properties show its state in the variant and the variant's values of varied parameters;
- `fenolite view PROJECT --variant NAME --json` opens with that variant and counts the fitted and not-fitted
  parts of the document shown; an unknown name is `FEN-2001`.

A variation names its part by the part's unique id, so a part annotated after the variant was made is still
found. The kinds (not fitted, alternate part, fitted with other values) are read as `INFERRED`
(`H-A-PRJ-VARIANT`).

## Reviewing a board: filter, panels and parameters

The side bar of a board holds, as Altium's PCB panel does (change c0187):
- **Filter.** A query selects primitives and parts and highlights them: `key:value` terms joined by spaces
  (and), `|` (or), a leading `-` (not), `*` and `?` wildcards and quoted values. The keys are `net`, `ref`,
  `footprint`, `value`, `layer` (its id or the board's own name, such as `"Top Layer"`) and `side`; any other key
  names a part parameter (`tolerance:1%`), and a bare word matches a reference or a net. For example
  `footprint:*0402* side:bottom`, `net:GND layer:"Bottom Layer"`, `ref:R* -value:10k`, `ref:U1 | ref:J?`.
  Enter applies it and zooms to what it found. The grammar is Fenolite's, not Altium's query language.
- **Find similar** fills the filter from the selection: the same footprint and value for a part, the same net
  and layer for a primitive of a net, the same layer otherwise.
- **Highlight.** `Dim` (the default) dims the rest of the board, `Mask` nearly hides it and `Normal` leaves it;
  the choice is remembered. `Shift+C` clears the filter and the selection.
- **Components** and **Nets** list every part (reference, value, footprint, side) and every net with its pad
  count and its routed length, the centre lines of its tracks and arcs (Fenolite's computation, vias not
  counted). With a filter they list what it found; each has its own text filter, and a click selects and zooms.
- **Parameters.** The Properties of a part show every parameter the file holds: a KiCad footprint's fields, and an
  Altium part's description, footprint description, library keys, hierarchical path, height and lock (its
  `Components6` record). On a board of an Altium project the parameters of the schematic part are added,
  matched by unique id. A parameter that is a web address is a link.

## Check findings

`fenolite view PATH --check FILE` draws the findings of a `fenolite check --json` reply over the document
shown; `--check run` runs `check` first, in the same process and read-only (change c0188):
- **Markers.** A finding with a position gets a ring in the colour of its severity (red error, orange warning,
  blue info); errors are drawn on top. `E` shows or hides them. A marker on a hidden layer is hidden too.
- **Messages.** The panel lists every finding grouped by code, errors first; a click zooms to the finding,
  makes its layer current, frames what it names, and shows its message, its `where`, its stage and that
  stage's evidence (`KICAD-VERIFIED(kicad-cli 10.0.7)` for KiCad's DRC and ERC). Findings without a position on
  the document are listed with "(no position)".
- **Positions.** A finding is placed by the position KiCad reports (`@x,y` in `where`), by the point of
  Fenolite's copper check (`on F.Cu at (x, y) mm` in its message), or by what it names: a pad (`R1-2`), a part, a
  track, arc, via or zone by its KiCad locator (`/kicad_pcb/zone[0]`), or a net. When it names a zone and a pad
  inside it, the marker goes on the pad. ERC findings are placed on sheets (on the root sheet for the path `/`,
  else on the sheet whose file stem is the last segment of the path), and findings of the board stages on
  boards.
- A DRC that `summary.limits` capped is a lower bound; the panel says so.

## Review tools

Change c0189 adds what a review in Altium relies on:
- **Edge measure.** `Shift+M` (or Edge) measures the shortest distance between the edges of two clicked
  objects: pads (all of a pad's copper on the layer clicked), tracks, arcs, vias, zone fills, board edges. A
  line joins the two closest points and the gap reads in the page's unit; overlapping objects read 0. Arcs are
  sampled every 2°, the rest is exact; on the authored test pair and against the gap `fenolite analyze` reports
  for a pad and a track the two agree within 1 µm. Objects on two layers are measured in the plane.
- **Links.** The address of the page keeps the document, the selection, the zoom, the centre, the unit and the
  current layer (`#doc=doc1&sel=U5&z=23.438&c=106.045,68.575&u=mm&l=F.Cu`); Link copies it, and opening it
  restores the view. `fenolite view PATH --select U12` opens at a part or a net.
- **Review marks.** `N` (or Mark) drops a mark with a note where you click; the Marks panel lists them, a click
  zooms, `×` deletes. With `fenolite view PATH --serve --marks review.json` the server saves them to that
  file (`fenolite.review.v0`, positions in nanometres); an exported page keeps them in the browser and
  Download marks saves the file. `fenolite view PATH --marks review.json --json` lists them for an agent.
- **SVG and print.** SVG saves the view as a vector file: the page draws it again into a recorder of its own
  drawing calls, so the file shows what the screen shows (layers, selection, markers). Print prints that SVG,
  fitted to the page or at 1:1, 2:1, 5:1 or 10:1 on paper; the print dialog's Save as PDF gives a PDF. Both
  need the 2D view.

## Comparing two revisions

`fenolite view NEW --compare OLD` shows what changed between two revisions of a board or a sheet (change
c0184), the fastest way to check a change an agent made:
- **On the board** the primitives NEW adds are green and those it removes magenta, over a dimmed board; a moved,
  turned or flipped part gets an arrow from its old place. `X` shows or hides the changes.
- **The Changes panel** lists one line per change: a part added, removed, moved (with the distance and the
  angle) or with a new value or footprint; a part whose own pads or graphics changed; a track, via or graphic
  added or removed; a zone whose filled area changed (with both areas). A click zooms to it.
- **On a sheet** the parts added, removed, moved or with changed parameters are framed, and the nets whose pins
  changed are listed.
- Parts match by reference and the rest by geometry, net and part, not by numbered labels, so a renumbered file
  still matches; a refilled zone is one change. Two documents of different tools, or a board and a sheet, are
  refused (`FEN-2001`).

## Keep-outs, dimensions and placement marks

The board view also draws what a reviewer checks first (change c0183):
- **Keep-outs.** A rule area is drawn hatched on its layers (on every copper layer for one of all copper),
  and a click names what it forbids (tracks, vias, pads, copper pours, footprints). The regions of Altium's
  Keep-Out Layer are drawn hatched too, and that layer is shown by default; its free board cut-outs are drawn
  as the board's outline.
- **Dimensions.** A linear dimension of the board is drawn with its extension lines, its line and its value,
  on its own layer, which is then shown by default. An orthogonal dimension follows KiCad's side for its
  offset; an aligned one puts its line on the same side (INFERRED).
- **Placement marks.** Parts whose courtyards overlap, and parts inside a keep-out that forbids footprints, are
  marked hatched on the `Checks` layer, judged as `fenolite place` judges them. Overlaps of parts without a
  courtyard (their extent taken from their pads, as for every Altium board read today) are counted in the
  notes, not marked, as they are often no conflict.
- Altium rooms and Altium dimensions are not drawn: no public board shows their records (`H-A-ROOM`).

## Speed and size

Large boards open fast the second time (change c0182):
- **Cache.** Each scene is cached by the SHA-256 of its file, the theme and Fenolite's own code, in your user
  cache folder (`--cache user`, the default; `FENOLITE_CACHE_DIR` moves it), under `.fenolite/view-cache/` of
  the project with `--cache project`, or not at all with `--cache off`. A changed file, theme or Fenolite
  rebuilds the scene; the cache is safe to delete.
- **Compact scenes.** Board scenes leave Fenolite in a compact form (`fenolite.view_scene.v1`), and an
  exported page holds each scene gzipped and decodes it only when its document is opened. On the largest public
  board of the corpus (544 parts, 8 355 tracks) the page went from 5.9 MB to 0.5 MB.
- **`--docs ID,...`** with `--export` embeds only those documents, for a page to send; a page above 20 MB gets a
  warning in `result.export`.

## Altium boards

An Altium board is shown as Altium shows it (change c0181):
- **Layer names.** Each layer has the name the board's layer stack gives it (`Top Layer`, `GND 1`, `Top Mask`,
  `Mechanical 1`, or the designer's own names); the outline is `Board Outline`. The tabs follow Altium's order:
  signal layers, planes, overlays, pastes, solders, mechanical layers, then the drill and keep-out layers.
- **Mask and paste openings.** Each pad's solder-mask and paste opening is its copper grown by its expansion:
  the pad's manual value, else the `SolderMaskExpansion` or `PasteMaskExpansion` rule that governs it (by
  priority; scopes that Fenolite does not evaluate are skipped and counted in the notes), else 4 mil of mask and
  no paste expansion. A negative expansion shrinks the opening.
- **Properties.** A click on a pad shows its expansions, where each comes from (manual, the rule's name, or
  default) and the size of its mask opening.

## Units and measurement

Every length the page shows can be read in millimetres or in mil (change c0179). The **mm / mil** button in
the top bar and the key `Q` switch it, as in Altium. The choice is kept for the next visit of the page. It
applies to:
- the cursor position and the grid;
- measurements;
- the Properties panel: track width and length, arc radius, via and hole diameter, pad size, corner radius,
  drill and slot, part position and extent, a footprint's copper and courtyard extent.

**Measure** (`M`) works on boards, sheets and library items. Each click snaps to the nearest pad centre, line
end, vertex, circle centre or text anchor within 8 px. A pitch therefore reads centre to centre, and the
readout gives the distance with Δx and Δy. A third click starts a new measurement, and `Esc` ends it.

A click on a pad shows its exact size from the model:
- width × height, shape and corner radius;
- drill, and slot length;
- centre, rotation and layers.

This is the place to check that an agent gave a pad, a pitch or a part the size that was asked for.

## Libraries

Schematic and footprint libraries open from the tree like any document (change c0179):
- Altium `.SchLib` and `.PcbLib`;
- KiCad `.kicad_sym`, a `.pretty` folder or one `.kicad_mod`.

The left panel lists the library's symbols or footprints, with a filter and a short summary of each: pins, or
pads and copper extent. A click opens the item:
- **A footprint** is drawn alone at its origin, as on a board: layer tabs, pads with their exact sizes,
  silkscreen, courtyard, fabrication and mechanical layers, and the 3D view of its bodies. Its colours are
  those of its tool.
- **A symbol** is drawn as on a sheet, one item per part or unit, with its pins, names, numbers and fields.
  The status line reads library coordinates from the symbol's origin.

Integrated libraries (`.IntLib`) are listed, not drawn.

## Draftsman drawings

Altium Draftsman documents (`.PCBDwf`) open from the tree like a library whose items are the sheets (change
c0180). A Draftsman document holds its own copy of the board, so a sheet is drawn from the document alone, as
Altium shows it before a refresh; Altium is not needed:
- **Views.** An assembly view draws the board outline and the parts of its side, each with its assembly
  strokes (else its silkscreen) and its designator; a fabrication view draws the outline and the copper of
  its layer; a drill view draws one symbol per hole size. Bottom views are mirrored.
- **Tables.** The drill table (symbol, count, size, plating), the layer stack legend (layer, material,
  thickness) and the bill of materials (comment, designators, quantity) are drawn from the document's data.
- **Sheet items.** Lines, rectangles, texts with their `=Parameter` values, pictures, notes and linear
  dimensions; the dimensions are measured on the board copy.
- A click on a part shows its designator, comment, side and size on the board; `M` measures on the sheet,
  in millimetres or mil. The status line reads sheet coordinates from the lower-left corner.

Side views (`Front`, `Right`), callouts and transmission line tables are left out and named in the notes.
Drill symbols, table cells, zone marks, dimension texts and the place of view titles are Fenolite's drawings;
texts use the font family the document names, in the browser's font, and break only at their own line breaks.
The view placement is `INFERRED` (`docs/formats/altium/draftsman.md`, "Drawing geometry").

**Panels.** An Altium board whose `EmbeddedBoards6` holds an Embedded Board Array, and a drawing whose
`IsPanel` is true, get a note: the array is not drawn until its records are measured (`H-A-PANEL-RECORD`,
Part Q of `docs/evidence/altium-pcb.md`). The board itself is drawn once.

## Schematics

An Altium sheet opens like a board: from the project tree, from the sheet tabs along the bottom, or with
`--doc`. The page then turns into a schematic view.

- **The sheet as Altium draws it.** The paper of the sheet's style or custom size, in its own colour, on a grey
  workspace, with the visible grid as lines, the border and its zones, and the title block. Every record keeps
  the colour, line width and font that the file gives it: pale yellow part bodies, navy wires and labels, red
  directive flags when the file says so. Texts use the font the sheet names (Times New Roman by default; the
  browser falls back to a serif font when the machine does not have it).
- **What is drawn.**
  - Parts in their own part and display mode, with their designator (and part letter), comment and visible
    parameters; a parameter `=Value` shows the value it names.
  - Pins with their names (overbars included), numbers, dots, clock wedges and active-low flags.
  - Wires, buses, bus entries, junctions, net labels, power ports in their style (bar, arrow, circle, wave,
    power ground, signal ground, earth), off-sheet connectors, ports, No ERC marks.
  - Sheet symbols with their entries and file names, harness connectors and signal harnesses.
  - Lines, polylines with their line styles and end shapes, polygons, rectangles, round rectangles, ellipses,
    arcs, pies, Bezier curves, notes, text frames, embedded images, and the template's own graphics.
  - Hidden pins and parameters are left out. IEEE symbols are counted in the notes, not drawn.
- **Navigation.** Wheel or `PgUp`/`PgDn` to zoom, drag (left or right button) to pan, `F` to fit.
- **Selection.**
  - A click on a part selects it: a green dashed box, and its properties (designator, comment, design item,
    footprint, parameters) in the Properties panel.
  - A click on a wire, a pin, a label, a port or a power port highlights its net: the rest of the sheet dims,
    and the panel lists the net's pins.
  - `Esc` clears.
- **Navigator** (left). The parts and the named nets of the sheet, with a filter; a click zooms to a part or
  highlights a net. **Search** finds a designator (`U1` or `U1A`) or a net name.
- **Double click.** On a sheet symbol, it opens the child sheet. On a part, it cross-probes: it opens the
  project's board and selects the part of that designator. On a board, a double click on a part opens the
  sheet that holds it.

What the schematic view states:

| item | drawn from | stated when |
|---|---|---|
| sheet, records, colours, widths | the file's records | a sheet without an area colour is drawn off-white, as saved sheets are |
| text size | the font table, at 9 mil per point | always: a Fenolite choice that keeps the pin texts of a 100-mil pitch apart |
| power ports, ports, sheet entries, pin marks, pin text offsets | the documented styles | always: these drawings are Fenolite's and may differ from Altium's by a few mil |
| title block of a sheet without a template | the sheet's parameters | always: the block is Fenolite's drawing |
| nets | the connectivity of one sheet (`altium-import`) | a net that crosses sheets is highlighted on each sheet under its own name |

### KiCad sheets

A KiCad sheet is drawn the same way, with KiCad's habits:
- the paper of its `paper` size with a frame and a title block from its `title_block`;
- the embedded symbols turned and mirrored as KiCad places them, with their pins (names, numbers, overbars,
  dots, clock wedges) and visible fields;
- wires, buses, bus entries, junctions, local, global and hierarchical labels, no-connect flags, power symbols,
  sheets with their pins, and free texts and graphics.

Every text is a stroke text in Fenolite's own stroke font, so a long field may end a little earlier or later
than in KiCad. The nets come from wires, junctions, labels, power symbols and hidden power pins. Images, text
boxes, tables and rule areas are counted in the notes, not drawn.

## For agents

Use `fenolite view PATH --json` to list a project's documents and to check what a board holds (the counts of
pads, tracks, zones, fills, texts and bodies, and the notes), or `--doc SHEET` for what an Altium sheet holds
(parts, pins, wires, labels, ports, sheet symbols and nets), or `--doc LIBRARY` for the names of a library's
symbols or footprints, or `--doc DRAWING` for the sheets and item counts of a Draftsman document. Use `--export` to hand a person one page to
review. `--serve` keeps running until it is interrupted; it is for a person at a browser.
