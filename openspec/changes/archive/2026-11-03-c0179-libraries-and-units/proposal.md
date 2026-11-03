## Why

On 2026-10-25 the maintainer asked for three things in the viewer of c0176 to c0178:

- **Libraries:** "ver os componentes, a lib de componentes de esquemático e tamanho de PCB", that is, open the schematic symbol libraries and the footprint libraries of a project.
- **Units:** "medir tudo em milímetro e em mil… poder trocar, que nem no Altium".
- **Measurement:** measure everything, "porque daí o usuário consegue ver se, por exemplo, a IA fez o tamanho dos pads, dos componentes, do tamanho que ele queria".

Today the tree lists every library as not viewable, the board shows millimetres only, the schematic shows mil only, and a click on a pad says its net but not its size.

## What Changes

- **Library scenes, `fenolite.view.library`.** One scene per library document, `fenolite.view_library.v0`, with one item per symbol or footprint. Each item holds its name, its description, a summary and the scene the page draws.
  - **Footprints** (Altium `.PcbLib`, a KiCad `.pretty` folder or one `.kicad_mod`): each footprint is placed alone at the origin of a one-part board and drawn by the board scene of c0176, with its pads, graphics, courtyard, fabrication and silkscreen layers. It is coloured by the palette of its tool (c0178).
  - **Symbols** (Altium `.SchLib`, KiCad `.kicad_sym`): each symbol, one item per part of a multi-part symbol, is drawn by the schematic scenes of c0177 and c0178, on a sheet the size of the symbol.
- **Exact pad data in board scenes.** A board scene, a library footprint included, lists every pad: its centre, its size, its shape, its rotation, its drill and slot, its corner ratio, its layers, its net and its part. Lengths are in nanometres, as the model holds them. A click on a pad shows these in the Properties panel.
- **Units: millimetres or mil, everywhere.** A Units button and the key `Q` (as in Altium) switch every length the page shows:
  - the cursor position and the grid;
  - measurements;
  - pad, track, via, hole and part sizes;
  - the Properties panel.

  The choice is kept for the next visit.
- **Measurement on every view.** Measure (`M`) works on boards, sheets and library items. It snaps to the nearest pad centre, line end or vertex, so a pitch reads centre to centre, and it shows the distance with its dx and dy.
- **Tree and command.** The tree marks schematic and PCB libraries as viewable. `fenolite view` replies with a library summary (`kind` `library`, item count and the names), and `--export` embeds library scenes.

## Capabilities

### New Capabilities

- `library-viewer`: the library scenes, the pad data of board scenes, the units and the measurement of the page.

### Modified Capabilities

- `cli-contract`: ADDED "View command shows libraries".

## Non-goals

- Integrated libraries (`.IntLib`) and database libraries: listed, not drawn.
- Editing a symbol or a footprint.
- 3D models of footprints: the 3D view extrudes the bodies the model holds, as on a board.
- Units other than millimetres and mil (inches, µm).

## Evidence level required

- **Library scenes:** `INFERRED`. Tests compare each item with the library the backend reads: the footprint and symbol counts, and each footprint's pad count, pad sizes and pad centres in nanometres.
- **Units and measurement:** a test checks the page's conversions (`fmtLen`) on fixed values. A person's review in a browser is recorded in the tasks.

## Impact

- **New:** `src/fenolite/view/library.py` and `tests/unit/view/test_library.py`.
- **Changed:**
  - `src/fenolite/view/scene.py` (the pad list), `schematic.py` and `kicad_schematic.py` (symbol scenes), `project.py` and `page.html`;
  - `src/fenolite/cli/cmd_view.py`;
  - `docs/viewer.md`, `docs/cli-contract.md`;
  - the view tests.
- **Size:** 4 design-days.
