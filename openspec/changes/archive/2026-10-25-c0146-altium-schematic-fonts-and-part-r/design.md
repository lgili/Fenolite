## Outcome in one paragraph

**Each distinct font once, and a sample of Part R that the schematic writer itself lays out and writes.** The duplicate font came from one place, the drawing sheet's own numbering; a document without a drawing sheet never had it. The sample of Part R is no longer a list of bare records: it is two sheet plans handed to the writer, so its sheet keys, colours, bodies and pins are the writer's and cannot drift from them.

## Context

- **The font table today.** `schdoc.sheet_record` writes one font: `FONTIDCOUNT=1`, `SIZE1=10`, `FONTNAME1=Times New Roman`, `SYSTEMFONT=1`, and every text record of the schematic writer names `FONTID=1` (`TEXTFONTID=1` on entries). `schdot.sheet_frame` (c0087) draws a drawing sheet as labels and polylines and numbers the fonts of its texts from `first_font = 2` in order of first use, one per distinct (points, bold, italic); `SheetFrame.sheet_record` appends them to the base record. The numbering never looks at font 1, so a frame text of 10 points, regular, becomes a second entry equal to the first.
- **Fact rows that bind.** `docs/formats/altium/schematic-ascii.md`: the table is `FONTIDCOUNT`, then `SIZE<i>`, `FONTNAME<i>` and the optional style keys; `FONTID` is 1-based; `SYSTEMFONT` names the default font. `sheet-template.md`: `SYSTEMFONT` is "the default font, normally 1", and the import takes `setup.text_size` from it and uses it for a `FONTID` outside the table. So font 1 stays the system font and stays first; only the appended entries change.
- **The sample of Part R today.** `tests/_altium_channels.py` fills two `_altium_records.Sheet` objects: record texts written by hand (`|RECORD=27|OWNERPARTID=-1|LINEWIDTH=1|…`) behind a sheet record of five keys. That builder exists so that a reader test can state exactly the keys it needs; it serves some forty tests and is not changed.

## Found on 2026-10-08

The task that opened this change expected the duplicate in every written schematic, and with it new bytes for every committed `.SchDoc` and for the pinned builds. Measured on the base `f17b03e9` with Fenolite's own reader:

- **No committed schematic document holds it.** All 25 `.SchDoc` files under `tests/data/altium/` hold one font and name only font 1 (the two of Part R name no font at all). None of them is built with a drawing sheet.
- **No pinned build holds it**: the ten Altium pins of `tests/unit/lens/test_build_bytes_pinned.py` are builds without a drawing sheet.
- **It is in every document with a drawing sheet whose texts include 10 points, regular.** Of the kit's five samples only `flat` names a drawing sheet (`iso5457_generic`): its table is 10, 10, 5, 7 with 25, 19, 9 and 8 records on the four fonts, in both forms. The written template of the same sheet has the same table.
- Both shipped sheet examples (`iso5457_generic`, `letter_generic`) hold texts of 10 points, so every template written from them and every build that draws them changes.
- So the bytes that change are those of a build with such a drawing sheet and of a written template. What moves in the repository for the fonts is two pins of template bytes in `test_schdot_write.py` (the shipped example `iso5457_generic` in both forms; the authored test sheet has texts of 6 and 14 points and keeps its pin). The two sheets of Part R change for the other reason. The changelog says what changes; "every build" would be wrong.
- **The sample of Part R cannot use the writer's layout for its child sheet.** The layout gives every port a wire with a net label of the port's name. With that label on the net of the port `OUT`, the import names the net of `C12` pin 2 `OUT` in the first channel and `OUT#2` in the second, where the sample is there to show the names `OUT1` and `OUT2` that come down from the parent's bus (three tests of `test_repeat.py` failed and said so). The child sheet is therefore placed by hand from the layout's own pieces, with each port on the end of its pin and no label on its net (decision 6). What Altium names such a net when a child sheet does hold a label is not known and not claimed.

## Decisions

1. **Where the rule lives.** In `schdot._Frame.font`: a font equal to `SYSTEM_FONT = (FONT_SIZE, False, False)` is font 1 when the frame is numbered from 2, which is the only numbering the writers use; every other font is appended as before. The font name needs no comparison: both tables are written with the one name `FONT_NAME`.
2. **A guard at the join.** `SheetFrame.sheet_record(base)` reads the fonts of `base` (size, bold, italic of the entries below `first_font`) and raises `ValueError` when the frame holds one of them. A frame built by another route cannot bring the duplicate back unnoticed.
3. **No renumbering pass over finished records.** The table is right when it is built; nothing walks the records afterwards to rewrite a `FONTID`. A pass would have to know every key that names a font (`FONTID`, `TEXTFONTID`) in every record kind.
4. **`first_font` stays** in `sheet_frame` and `SheetFrame`: with a value other than 2 the base is not the writer's sheet record, nothing is known of its fonts at numbering time, and the guard of decision 2 is what holds.
5. **Capability.** The requirement is added to `altium-schematic-writer`, which owns the sheet record and its font table ("Sheet record"). The requirement of c0087 that owns the frame (`sheet-templates`, "Altium sheet template writing", an ADDED delta of an unarchived change) says nothing of the numbering, so it is not modified.
6. **Part R is authored through the writer.** `tests/_altium_channels.py` builds `layout.PartSpec`, `SymbolSpec` and `Crossing` values and `binary.write_schdoc_binary` writes the plans. The top sheet is placed by `layout.layout_sheet`. The child sheet is placed by hand from the same pieces (`PlacedPart`, `part_stubs`, `PlacedPort`), with the ports `VCC` and `OUT` on the ends of `R1` pin 1 and `C12` pin 2 and no wire between them ("Found on 2026-10-08"). What a build cannot produce is stated in three values of the top plan, not in records: the module name of the sheet symbol is the statement `Repeat(CH,1,2)`; the second crossing is named `Repeat(OUT)` and carries the bus members, so the writer draws its bus block; the label of that block is then replaced by `OUT[1..2]` (the writer would label the bus with the crossing's name). Every record, key, colour and font id is therefore the writer's; a change of the writer's sheet record or colours moves the sample's bytes and fails `test_files_equal_what_the_script_writes` until the files are written again.
7. **What the sample keeps.** The same interface (`sheets(statement, entry=, bus=)`, `project_text`, `files`, the constants), the same unique ids (`UTOP0001`, `JTOP0001`, `SYMBOL01`, `RUID0001`, `CUID0001`, the two port ids), the same designators, pin designators, pin names and net names. On the top sheet connectivity is by net labels on pin stubs, as every written sheet has it, where the old sheet ran wires; on the child sheet the old wires from pin to port are gone and the port touches the pin. The unedited tests of `test_repeat.py` are the proof that the import reads the same circuit; a comparison of the two generations field by field found, beyond them, only the component values and library references (empty before, set now) and the digest of the file in each provenance. Whether Altium connects a port that lies on a pin end as the import does is not known; step R1 shows it.
8. **The bare builder stays** for every other reader test. Only the sample that is handed to a person moves to the writer.
9. **Two hypothesis rows.** `H-A-SCHDOT-FONT-MERGE` records the observation (Altium saves a table with two equal entries as one) with its one file; it is not a criterion of the writer. `H-A-SCHDOT-AREACOLOR` is the believed cause of the black page; Part R of session 2 supports or refutes it, and cannot isolate it (the files change in more than the area colour).

## What the returned files showed (as read on 2026-10-07)

- The saved copy of the kit's `flat.SchDoc` holds `FontIdCount=3` where the written file has `FONTIDCOUNT=4`, and the labels of the frame are renumbered to match: the two entries of 10 points are one. The file is the maintainer's own and is outside the repository (S-0610); it was not read again for this change, and nothing of it is copied.
- The maintainer said that the sheet of Part R showed as a page that was all black (S-0611). The files he had are the committed ones of the base: a sheet record `RECORD=31` with `FONTIDCOUNT`, `SIZE1`, `FONTNAME1`, `SYSTEMFONT` and `SHEETSTYLE` and nothing else; no `COLOR`, `AREACOLOR` or `FONTID` on any record; `PINLENGTH=0`; no graphic owned by a component.

## Tests

- `tests/unit/backends/altium/test_schdot_write.py`: `test_distinct_fonts_*` (a sheet with texts of 10, 5 and 14 bold points: three fonts, the label ids, the readback inside the written scope; the guard of `sheet_record`); the pinned template bytes moved with the reason beside them.
- `tests/unit/lens/test_altium_sheet.py`: `test_distinct_fonts_*` (blink without a drawing sheet: one font, every id 1; blink with `iso5457_generic` in both forms: the same table of three distinct fonts, every id inside it).
- `tests/unit/backends/altium/adapter/test_channel_files.py`: the files equal what the script writes; the folder reads as two channels (unedited assertions); new, the sample holds the writer's sheet record but for its size keys, a colour on every drawn record, a rectangle per component and pins of 200 mil.
- `tests/unit/backends/altium/adapter/test_repeat.py`: unedited.
- KiCad's importer on the regenerated sample is not a test of this change: `tests/kicad/altium` reads the samples of the schematic writer, which keep their bytes; the folder is run for the hand-over because the code path of the writer is touched.

## Released output

No module of the KiCad backend, of the model, of the design language or of the layout lens is edited; the one product file is `backends/altium/schdot.py`, which only an Altium build with a drawing sheet and `template build --target altium` reach. Measured in task 3.1.

## Size (design-days)

| group | dd |
|---|---|
| reading, measurement, proposal | 0.25 |
| the font rule, its tests, the pages | 0.25 |
| the sample of Part R, the maintainer's folder | 0.25 |

Total: 0.75. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-schematic-writer`: ADDED "Distinct fonts in the font table". It cites "Sheet record" (living) and `schdot.sheet_frame` (c0087, unarchived). Archive after c0087, c0083 and c0086.

## Author report: Part R, session 2

The steps, the expected answers and the files with their SHA-256 are in `docs/evidence/altium-schematic.md`, "Part R". They are written from Altium's documentation; a menu path or a dialog name may read differently in version 26. Nothing is marked verified by this change.
