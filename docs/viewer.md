# Board viewer

`fenolite view` shows the boards of a project in a web browser, without the tool that made them: an Altium
project on a machine without Altium, a KiCad board in a review, a board an agent just wrote. It reads every
board through the neutral model (change c0176), so Altium `.PcbDoc` and KiCad `.kicad_pcb` files look the
same. It writes no design file and opens no connection beyond the loopback address.

```bash
fenolite view MyProject.PrjPcb --serve              # live: http://127.0.0.1:8765/, reloads when a board is saved
fenolite view board.kicad_pcb --export board.html --confirm    # one standalone page to open or send
fenolite view MyProject.PrjPcb --json               # for an agent: the documents and a scene summary
```

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

## For agents

Use `fenolite view PATH --json` to list a project's documents and to check what a board holds (the counts of
pads, tracks, zones, fills, texts and bodies, and the notes). Use `--export` to hand a person one page to
review. `--serve` keeps running until it is interrupted; it is for a person at a browser.
