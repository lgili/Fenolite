## Why

The maintainer asked on 2026-10-25 for a schematic viewer next to the board viewer of c0176, and asked that it look like Altium Designer, the tool the maintainer prefers. `fenolite view` lists every schematic of a project but shows only a card for it ("no viewer yet"). Fenolite already reads an Altium `.SchDoc` record by record (`altium-schematic-reader`), with its colours, fonts, owners and parts, and it already finds the nets of one sheet (`altium-import`, "Connectivity within a sheet"). It cannot yet put any of it on a screen. A person reviewing a sheet, or checking what an agent wrote, has to open Altium.

## What Changes

- **A schematic scene, `fenolite.view.schematic`.** It turns a `SchDocument` into plain JSON in integer micrometres, Y downwards from the sheet's top-left corner. The scene holds:
  - the sheet: its size from `SHEETSTYLE` or the custom size, the area colour, the grid, the border and zones, the title block, and the template's own records;
  - the fonts of the sheet's font table;
  - every drawn record, in the colour and line width the file gives: graphics, pins with their names, numbers and edge marks, designators, parameters, wires, buses and bus entries, junctions, net labels, power ports in their style, ports, No ERC marks, sheet symbols and their entries, harnesses, text frames, notes and embedded images;
  - the components (designator with its part letter, comment, library reference, description, parameters, footprint, box);
  - the nets of the sheet, with the wires, pins and identifiers of each.

  Hidden pins and parameters are left out. Each multi-part component shows its own part and display mode.
- **The page draws a schematic as Altium does.** It uses the file's own colours and fonts: an off-white sheet on a grey workspace, a line grid, navy wires and a pale yellow body fill when the file says so, and text in the font the sheet names (Times New Roman by default). It adds:
  - **Interaction:** wheel zoom, drag to pan, click a part to select it, click a wire or a pin to highlight its net (the rest of the sheet dims).
  - **Panels:** a Properties panel for the selection, and a Navigator panel that lists the sheet's parts and nets.
  - **Navigation:** search by designator or net name; a double click on a sheet symbol opens its child sheet; a double click on a part cross-probes to the project's board.
  - **Sheet tabs:** the schematic documents of the project as tabs along the bottom.
- **The project tree marks Altium schematics as viewable**, so `fenolite view`, `--serve` (live reload when a sheet is saved) and `--export` show them like boards.
- **Docs.** `docs/viewer.md` (the schematic view), the `view` section of `docs/cli-contract.md`, and the line of the guide page `files`.

## Capabilities

### New Capabilities

- `schematic-viewer`: the schematic scene, the schematic documents of the tree, and the schematic drawing of the page.

### Modified Capabilities

- `cli-contract`: ADDED "View command shows schematics".

## Non-goals

- KiCad schematics (`.kicad_sch`). They stay listed as not viewable; a follow-up change draws them through the same scene format.
- Schematic libraries (`.SchLib`) and harness documents.
- Editing, compiling the project, or ERC. The nets are the nets of one sheet. A net that crosses sheets is highlighted on each sheet under its own name.
- Altium's application colour scheme. The colours are the ones the file holds. Where a record has none, the defaults are the values the format pages record as seen in files. The sheet's workspace grey and the selection colours are Fenolite's.
- Pixel equality with Altium. The shapes of power ports, ports, sheet entries and pin marks, the pin text offsets, the built-in title block and the zone count of a standard sheet are Fenolite's drawings of documented styles.

## Evidence level required

- **Scene:** `INFERRED`. Tests compare the scene's count of each drawn record kind with the document's, on the Altium sheets of the test data and on an authored ASCII sheet that holds every graphic kind. They also check that the nets of the scene are the `local_nets` of the document.
- **Page:** a test checks the page's structure and that a schematic scene round-trips through the export. A person's review in a browser is recorded in the tasks, not automated.

## Impact

- **New:** `src/fenolite/view/schematic.py`, `tests/unit/view/test_schematic.py`.
- **Changed:**
  - `src/fenolite/view/page.html`, `project.py` and `__init__.py`;
  - `src/fenolite/cli/cmd_view.py`;
  - `docs/viewer.md`, `docs/cli-contract.md`, the guide page `files`;
  - the view tests.
- **Size:** 4 design-days.
