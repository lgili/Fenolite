## Context

- **Request.** The maintainer, 2026-10-25: "projetos KiCad, tanto do esquemático e layout, teremos um tema de cores e copiar o KiCad; aí assim cada projeto usa o tema esperado original."
- **Choice.** Asked how, the maintainer chose a palette authored in KiCad's manner, plus the user's own theme file. KiCad's built-in values are in GPL sources, which `LEGAL.md` block A does not let Fenolite transcribe.
- **What exists** on `c0177-schematic-viewer`:
  - the board scene (c0176), with one Fenolite colour per layer;
  - the schematic scene and page of c0177;
  - `backends.kicad.sexpr.parse`;
  - the KiCad schematic facts of `docs/formats/kicad/schematic.md`: symbol placement (turn, then mirror), labels, sheets and pin connection points;
  - the symbol library facts of `docs/formats/kicad/libraries.md`.
- **Theme file facts** (`docs/formats/kicad/color-theme.md`):
  - A theme is a JSON file in the `colors` folder of the user's KiCad settings (S-0813).
  - That settings folder is `%APPDATA%\kicad\<major>.0`, `~/.config/kicad/<major>.0` or `~/Library/Preferences/kicad/<major>.0` (S-0814).
  - The file holds the objects `board`, `fpedit`, `schematic` and `meta`. Colours are `rgb(r, g, b)` or `rgba(r, g, b, a)` strings, and `board.copper` is an object keyed `f`, `b`, `in1` … `in30` (S-0813).

## Goals / Non-Goals

**Goals**
- A KiCad project in the viewer reads as KiCad: dark board, cream schematic, green wires, stroke text. An Altium project reads as Altium.
- With the user's theme, a KiCad project reads as the user's own KiCad.

**Non-Goals**
- See the proposal.

## Decisions

1. **Palettes are authored, not transcribed.**
   - `themes.KICAD` and `themes.ALTIUM` are Fenolite's colours, picked by eye in the manner of each tool. The values are written in the module and in no file of either vendor.
   - A palette is a dict with two parts:
     - `board`: `background`, `board` (the board's own fill) and `layers` (a colour per layer id, or per kind and side for a layer that is not listed);
     - `schematic`: one colour per role.
2. **Theme per document.**
   - `themes.theme_for(backend, kind)` gives `kicad` for the KiCad backend and `altium` for the Altium backend.
   - A board scene gets `scene["theme"]`: the palette's `name` and `board` part. Its layer colours are set from the palette.
   - A KiCad schematic scene resolves every primitive's colour from the palette's `schematic` roles when it is built.
   - An Altium sheet scene keeps its file's colours and gets `theme` `altium` for the workspace only.
3. **The theme file.** `read_kicad_theme(path)` reads the JSON with the standard library.
   - Each known key maps to a palette slot:
     - `board.background` and the board layer keys (`copper.f`, `copper.b`, `copper.inN`, `f_silks`, `b_silks`, `f_mask`, `b_mask`, `f_paste`, `b_paste`, `f_crtyd`, `b_crtyd`, `f_fab`, `b_fab`, `edge_cuts`, `dwgs_user`, `cmts_user`, `eco1_user`, `eco2_user`, `via_through`, `plated_hole`);
     - every key of `schematic`.
   - The alpha of `rgba` is kept as an opacity.
   - An unknown key is ignored. A malformed file is `FEN-3004`.
   - `find_kicad_theme(name)` looks for `<name>.json` in the `colors` folder of each KiCad settings folder from major 10 down to 6, then in the current folder.
4. **KiCad schematic scene, `kicad_schematic.build_kicad_schematic_scene(text, *, name, data, palette)`.** The output is the c0177 format, so the page draws it unchanged. Coordinates are the file's millimetres, Y down, in µm.
   - **Symbols:** the embedded `lib_symbols` definition (`lib_name`, else `lib_id`), with the units `<name>_<unit>_<style>`, where unit 0 and style 0 are common.
     - A library point (x, y), Y up, becomes (x, −y), is turned by the angle, then mirrored (`mirror x` negates y, `mirror y` negates x), then moved by `at`.
     - Graphics: `rectangle`, `polyline`, `circle`, `arc` (start, mid, end), `bezier`, `text`. A body with `fill background` or `outline` takes the body fill colour.
   - **Pins:**
     - the line from the connection point (`at`) inwards by `length`;
     - shapes: `inverted` and `inverted_clock` a circle at the body end, `clock` a wedge, `input_low` and `output_low` a flag;
     - the name inside the body at the symbol's `pin_names offset`, or above the line when the offset is 0;
     - the number above the line, unless the symbol hides names or numbers;
     - hidden pins are left out.
   - **Fields:** a visible `property` is drawn at its `at` and `effects` (size, justification), with its angle combined with the symbol's quarter turns so that it reads upright, as `schematic.md` records.
   - **Labels:** local labels as text; global labels as a flag shaped by `shape`; hierarchical labels as a small arrow. All are in their role colours.
   - **Sheets:** the box with its `fill` and `stroke` colours when the file gives them, else the role colours; the `Sheetname` and `Sheetfile` properties; pins as hierarchical labels on the edge.
   - **Paper:** the size of `paper` (A5 to A0, A to E, or a user size), with a frame of 10 mm margins and a title block drawn from `title_block`. Both are Fenolite's drawings, stated in the notes.
   - **Texts:** `sheet.text` is `stroke`. The page then draws every text with Fenolite's stroke font, at the height of the text's `size` and with a stroke of `size / 8`.
   - **Nets:** wires and buses are kept apart. Points connect when they coincide, and when an end lies on a wire. A junction joins the wires through it. Labels of one text join, and power symbols join by their value. Names come from the label, else the power value, else `Net-(<ref>-Pad<n>)`.
5. **The page.**
   - A board scene with `theme` uses its `background` and `board` colours instead of the fixed ones.
   - A schematic scene whose `sheet.workspace` is set paints that colour around the paper (the KiCad background), else the grey of c0177.
   - `sheet.text == "stroke"` draws texts as strokes.
   - The 3D view keeps its own board colours.
6. **The command.**
   - `--theme FILE|NAME` (`metavar THEME`): a path to a `.json` file, or a name for `find_kicad_theme`. A theme that is not found is `FEN-3001`, a malformed one `FEN-3004`.
   - The reply's `theme` names the palette of the document shown: `kicad`, `altium` or `kicad:<file name>`.
   - `.kicad_sch` documents become viewable. A lone `.kicad_sch` is a tree of one document.

## Evidence

- **Themes:** `INFERRED` (H-K-THEME). `tests/unit/view/test_themes.py` reads an authored theme file of the documented form and checks:
  - its colours land on the board layers and the schematic roles;
  - missing keys keep the `kicad` palette;
  - a malformed file is refused.
- **KiCad schematic scene:** `INFERRED`. `tests/unit/view/test_kicad_schematic.py` checks, on `tests/data/kicad/schematic/flat.kicad_sch` and `units.kicad_sch` and on `tests/data/kicad/parity/agree/blink.kicad_sch`:
  - counts: one comp per placed symbol, a pin object per visible pin, one object per wire, label, junction and no-connect;
  - every pin connection point equals `schematic.md`'s placement rule, so a pin's line ends where the netlist says the pin connects;
  - every wire under a label carries that label's net.

## Risks / Trade-offs

- **The `kicad` palette is only like KiCad.** Users who want KiCad exactly pass their theme. The notes say which palette was used.
- **Stroke text is Fenolite's font, not KiCad's.** Widths differ slightly, so a long field may end a little earlier or later than in KiCad.
