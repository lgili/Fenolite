## Why

A user of Altium Designer has a sheet template (`.SchDot`): a page size, a border and a title block
drawn with lines and texts. Fenolite's drawing sheets (c0012) are built only from `*.sheet.toml`
files, so that user must redraw the sheet by hand. The v0.3 "read" phase lists this import.

## What Changes

- **Importer.** `fenolite.backends.altium.read.sheet.import_sheet(data)` turns the records that
  c0040's `read_schematic` returns into a neutral `DrawingSheet`. It writes nothing.
- **What a `.SchDot` is.** Public sources say it is a schematic document saved under another file
  type (S-0261). The importer therefore takes its form from the content, never from the extension,
  and also accepts a `.SchDoc` whose template graphics are owned by a template record (S-0130).
- **Size.** The 18 sheet styles, the custom size and the orientation give the paper and the margins.
- **Graphics.** Lines, rectangles, polylines, polygons and text labels become `SheetShape` and
  `SheetText` items, each anchored to the nearest corner.
- **Border and zones.** They are drawn from the sheet flags when the file gives their numbers (a
  custom sheet). Otherwise they are reported.
- **Special strings.** `=Title`, `=DocumentNumber`, `=Revision`, `=SheetNumber`, `=SheetTotal`,
  `=Date`, `=Organization`, `=DrawnBy`, `=ApprovedBy` and `=DocumentName` map to neutral tokens.
  Other parameter names become `{param:NAME}`. Dynamic and malformed strings are reported.
- **Images.** An embedded PNG is kept as a `SheetBitmap`. Any other image is reported.
- **Report.** Every template record is imported or named in an issue with its record index. Twelve
  codes `altium.sheet.*`. A warning is a loss: the command refuses it without `--allow-lossy`.
- **Command.** `fenolite template import SRC --target kicad --out OUT` writes a `.kicad_wks` through
  the mutation protocol, beside `template build`.
- **Fixtures.** Tests build authored templates in memory. Three public, MIT-licensed, Altium-saved
  files are fetched for a census and never committed.

## Capabilities

### Modified Capabilities (no new capability)

- `sheet-templates`: nine ADDED requirements (reading, size, border, graphics, special strings,
  images, report, command, fixtures and corpus); MODIFIED "Template build command" (living text),
  whose `action` gains the choice `import`.

## Non-goals

- **No SchDot writer.** Writing a `.SchDot` from a `SheetSpec` or a `DrawingSheet` is the v0.4
  roadmap item "Sheet templates for the second backend, from the same sheet spec as c0012".
- No `*.sheet.toml` output: the closed grid format cannot hold free lines.
- No arcs, ellipses, Béziers, rounded rectangles, text frames or notes: the neutral model has lines,
  rectangles, texts and bitmaps. They are reported.
- No colours, font names, fills or dash styles.
- No drawing of the built-in title block, nor of the border of a standard style: no public source
  gives their geometry.
- No shipped template, and no committed file of any organisation.
- No compound-file or record parsing (c0039, c0040), no `Design` import (c0043).

## Evidence level required

- `.SchDot` container and records equal a schematic document's: `INFERRED`; the three fetched
  files (S-0264, S-0265) are supporting data, and a third repository gives `CORPUS-VERIFIED`.
- Sheet styles, record keys, text anchors, line widths, special strings: `INFERRED` (S-0130,
  S-0131, S-0261 to S-0263), one hypothesis `H-A-RD-SHT-*` each.
- Centring the drawing area on the paper, corner anchoring, font size: Fenolite's own rules.
- The written `.kicad_wks` draws what `layout` predicts: `ORACLE-VERIFIED(kicad-cli)` on an
  authored template, with the oracle of c0012.
- No `kicad-cli` path reads an Altium schematic, so the reading has no oracle. The command's
  envelope stays `INFERRED`.

## Impact

- Code: `src/fenolite/backends/altium/read/sheet.py`, `src/fenolite/cli/cmd_template.py`; tests;
  a new format page `docs/formats/altium/sheet-template.md`.
- Depends on c0040 (and through it c0039). Archived after c0040.
- Size: 5.5 design-days.
