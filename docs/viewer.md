# Board and schematic viewer

`fenolite view` shows the boards and the sheets of a project in a web browser, without the tool that made
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
(parts, pins, wires, labels, ports, sheet symbols and nets). Use `--export` to hand a person one page to
review. `--serve` keeps running until it is interrupted; it is for a person at a browser.
