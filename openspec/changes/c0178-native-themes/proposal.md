## Why

On 2026-10-25, after the Altium schematic view of c0177, the maintainer asked for each project to look like its own tool: a KiCad project, schematic and board, in KiCad's colours, and an Altium project in Altium's. Today the views disagree with that:

- A board of either tool uses one Fenolite palette, chosen in c0176 so that no vendor's scheme is copied.
- A KiCad schematic is not drawn at all.

The maintainer chose (2026-10-25) how to get KiCad's colours:

- **Default:** a palette Fenolite authors in the manner of KiCad. KiCad's built-in values sit in GPL source, which `ip-hygiene` forbids transcribing.
- **The user's own theme:** a KiCad colour theme file of the user (`--theme`). When it is given, the view is the user's KiCad, colour for colour.

## What Changes

- **Themes, `fenolite.view.themes`.** Two palettes authored for Fenolite: `kicad`, in the manner of KiCad's default look, and `altium`, in the manner of Altium Designer's. Each holds the board layer colours, the board background and the schematic roles: background, wire, bus, junction, body outline and fill, pin, pin name and number, reference, value, fields, the three label kinds, no-connect, sheet, sheet name and file, note and grid. `read_kicad_theme(path)` reads a KiCad colour theme JSON file into a palette; a key the file leaves out keeps the `kicad` palette's colour.
- **Each document takes the theme of its tool.**
  - A KiCad board and a KiCad schematic use `kicad`, or the user's theme.
  - An Altium board uses `altium`.
  - An Altium sheet keeps the colours its file holds (c0177).
- **KiCad schematics are drawn.** `fenolite.view.kicad_schematic` turns a `.kicad_sch` into the `fenolite.view_schematic.v0` scene of c0177. It draws:
  - the embedded symbols, turned and mirrored as KiCad places them, with their graphics, pins (names, numbers, shapes) and visible fields;
  - wires, buses, bus entries and junctions;
  - local, global and hierarchical labels, no-connect flags and power symbols;
  - sheets with their pins, texts and graphics, and the paper with a frame and title block.

  Texts use Fenolite's single-stroke font, as KiCad draws its own stroke font. The nets of the sheet come from wires, junctions, labels and pin ends, so a click highlights a net as on an Altium sheet.
- **`fenolite view --theme FILE|NAME`.** It names a KiCad colour theme: a JSON file, or the name of a theme in the `colors` folder of the user's KiCad settings. It applies to the KiCad documents of the project.
- **Docs.** `docs/formats/kicad/color-theme.md` (the theme file, with its sources), `docs/viewer.md`, the `view` section of `docs/cli-contract.md`.

## Capabilities

### New Capabilities

- `native-themes`: the palettes, the theme file reader, the choice of theme per document, and the KiCad schematic scene.

### Modified Capabilities

- `cli-contract`: ADDED "View command takes a theme".

## Non-goals

- Transcribing KiCad's or Altium's built-in colour values (`ip-hygiene`).
- Finding which theme a KiCad installation has selected. That setting is not documented by a public source; the user names the theme.
- Altium's per-layer board colours stored in a saved board: not documented by a source yet. The `altium` palette is used.
- Bitmap images, text boxes, tables and rule areas of KiCad schematics. They are counted in a note.

## Evidence level required

- **Theme file:** `INFERRED`, from public theme files (S-0813) and KiCad's documentation of its settings folders (S-0814). A test reads an authored theme file.
- **KiCad schematic scene:** `INFERRED`. Tests compare its counts with the file: symbols, pins, wires, labels, junctions, no-connects and sheets. They also check that its nets put the label of a wire and the pins at the wire's ends on one net, as `kicad-cli` would.
- **Page:** a person's review in a browser, recorded in the tasks.

## Impact

- **New:**
  - `src/fenolite/view/themes.py` and `src/fenolite/view/kicad_schematic.py`;
  - `docs/formats/kicad/color-theme.md`;
  - `tests/unit/view/test_themes.py` and `tests/unit/view/test_kicad_schematic.py`.
- **Changed:**
  - `src/fenolite/view/page.html` and `project.py`;
  - `src/fenolite/cli/cmd_view.py`;
  - `docs/viewer.md`, `docs/cli-contract.md`, `docs/evidence/sources.md` and `docs/hypotheses.md`;
  - the view tests.
- **Size:** 4 design-days.
