## Why

The maintainer opened Fenolite's files in Altium Designer 26 on 2026-10-07 and returned the folders. Two things in them are corrected here.

1. **Two equal fonts.** A schematic document with a drawing sheet holds a font table whose fonts 1 and 2 are both Times New Roman 10: font 1 is the sheet's system font, and the drawing sheet declares the fonts of its texts from font 2 on without looking at font 1. The kit sample `flat` shows it (`FONTIDCOUNT=4`, `SIZE1=SIZE2=10`). The copy of that sheet that Altium saved holds three fonts, and the labels of the frame are renumbered (as read on 2026-10-07; one file).
2. **Part R shows a black page.** The two sheets of Part R (`tests/data/altium/channels/two/`) were authored record by record for the reader's tests: the sheet record has five keys and no area colour, no record has a colour or a font, pins have length 0 and components no graphics. The maintainer saw a page that was all black. The likely cause, which nobody has confirmed, is that an absent area colour reads as 0, black, with black objects on it.

## Outcome in one paragraph

**The font table of a written schematic document or sheet template holds each distinct font once; the sample of Part R is written by the schematic writer's own functions, so it carries the sheet keys, the colours, the bodies and the pin lengths of an ordinary written sheet.** A build without a drawing sheet keeps its bytes: its table has one font. A build with a drawing sheet that holds a text of 10 points, regular, changes: one font less, and the `FONTID` of the frame's labels renumbered. The import of the Part R sample gives the same circuit as before (channels, designators, nets, component and pin ids): the tests that say so are not edited.

## What Changes

- **`schdot` (the drawing sheet's fonts).** A text of the frame whose font is the system font of the sheet record (10 points, not bold, not italic, the writer's one font name) uses `FONTID=1`; only the other fonts are appended, in order of first use. `SheetFrame.sheet_record` refuses a frame whose fonts repeat one of the base record. Both forms (binary and ASCII) and the sheet template take the same path.
- **Bytes that change.** A written sheet template and the schematic documents of a build that draws a sheet, when the sheet holds a text of 10 points, regular: both shipped examples do (`iso5457_generic`, pinned in `tests/unit/backends/altium/test_schdot_write.py`, and `letter_generic`), and so does the kit sample `flat`. No committed file under `tests/data/` holds a drawing sheet, so none changes for this reason, and no pin of `tests/unit/lens/test_build_bytes_pinned.py` moves (measured; design, "Found on 2026-10-08").
- **Part R, the sample.** `tests/_altium_channels.py` builds the two sheets as `layout.SheetPlan` values written by `binary.write_schdoc_binary`: the writer's sheet record, generic bodies, pins of 200 mil, labelled wires, ports, the sheet symbol with its entries, and the bus. The top sheet is placed by `layout.layout_sheet`; the child sheet is placed by hand from the same pieces, with its two ports on the pin ends, because the layout's labelled wire beside a port would name the net of a repeated port in every channel (design, "Found on 2026-10-08"). The `Repeat(…)` statement is the name given to the writer's sheet symbol, `Repeat(OUT)` the name of its second sheet entry, and the bus beside that entry is labelled `OUT[1..2]`: the three places where the plan differs from what a build can produce. The committed files are written again by `author.py`; `two.SchDoc` and `two_ch.SchDoc` change, `two.PrjPcb` does not.
- **Part R, the maintainer's files.** Rebuilt into `~/fenolite-altium-checks/session-2/R-repeated-sheet/` with a guide in Brazilian Portuguese (steps R1 to R4, expected answers, a line to fill per step, SHA-256 per file). The older folder `~/fenolite-altium-checks/c0083-part-r/` is not touched.
- **Pages.** `docs/formats/altium/sheet-template.md` (two fact rows, the choice "Fonts"), `docs/evidence/altium-schematic.md` (Part R: the new folder, the new digests, the black page and why it is believed; Part W: the template's digest), `docs/evidence/sources.md` (S-0610, S-0611), `docs/hypotheses.md` (two rows), `tests/data/MANIFEST.toml` (the notes of the sample's files).

Size: 0.75 design-day (a size, not time).

## What is not known

- That Altium merges equal fonts on a save is an observation on one returned file. Whether the merged table is what Altium wants is not claimed: the requirement is only that each distinct font is written once.
- Why the page of Part R was black is a hypothesis (`H-A-SCHDOT-AREACOLOR`). The new files change the sheet keys, the colours, the bodies and the pins at once, so a page that shows as it should supports the hypothesis and does not isolate the area colour.
- Whether Altium Designer 26 compiles the `Repeat` statement of the new files (steps R1 to R4) is as open as it was.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-schematic-writer`: ADDED "Distinct fonts in the font table".

## Non-goals

- No change of the product for Part R: no build writes a `Repeat` statement, as before; only the test sample and its builder change.
- No change of the font, its size or its name, and no font read from the model.
- No change of the import, of any reader, of the schematic library writer (its table has one font) or of the PCB writers.
- No change of KiCad output: no module of the KiCad backend, of the model or of the design language is edited (the only product file that changes is `src/fenolite/backends/altium/schdot.py`).
- No file that Altium wrote is committed or copied; no code or constant from any private project or organisation.

## Evidence level required

Unchanged, `INFERRED`: own readback and KiCad's import are supporting data; what Altium shows waits for the author reports of Part W and Part R.

## Impact

- Changed: `src/fenolite/backends/altium/schdot.py`; `tests/_altium_channels.py`, `tests/data/altium/channels/two/` (two of three files, and the text of the script); tests of the template writer and of the Altium build.
- Behaviour: **the schematic documents of an Altium build with a drawing sheet, and a written sheet template, change their bytes when the sheet holds a text of 10 points, regular** (`FONTIDCOUNT` one lower, the labels of the frame renumbered). A build without a drawing sheet is byte-identical.
- Depends on: c0087 (the drawing sheet), c0083 (the sample), c0086 (the bus records). Archive after them.
