## ADDED Requirements

### Requirement: Distinct fonts in the font table
The font table of the sheet record of every schematic document and sheet template that Fenolite writes SHALL hold each distinct font once. A font is its name, its size, bold and italic.
- Font 1 MUST stay the system font of "Sheet record" (`SIZE1=10`, `FONTNAME1=Times New Roman`, `SYSTEMFONT=1`), and every text record of the schematic writer MUST keep `FONTID=1` (`TEXTFONTID=1` on a sheet entry and a harness entry).
- A text of a drawing sheet (`schdot.sheet_frame`) whose font equals font 1 MUST be written with `FONTID=1` and MUST NOT add an entry. Every other font of the drawing sheet MUST be appended once, in order of first use, numbered from 2, and each label MUST carry the number of its own font.
- `FONTIDCOUNT` MUST be the number of entries, and no two entries may be equal in name, size, bold and italic. `SheetFrame.sheet_record(base)` MUST raise `ValueError` for a frame one of whose fonts is already in `base`.
- The rule MUST hold in the binary and in the ASCII form, which share their records, and for a sheet template written by `schdot.write_template`.
- A document without a drawing sheet MUST keep the bytes it had before this change: its table holds font 1 alone.
- This is a property of what is written. That Altium Designer merges equal entries when it saves is an observation on one file (`docs/formats/altium/sheet-template.md`) and is not required of any reader.

#### Scenario: One sheet with labels in the default font
- **WHEN** `uv run pytest tests/unit/lens/test_altium_sheet.py -k distinct_fonts` builds the blink design for Altium without a drawing sheet and reads the schematic back
- **THEN** the font table holds one font, and every `FONTID` and `TEXTFONTID` of the document is 1

#### Scenario: A drawing sheet whose title block uses another size
- **GIVEN** a drawing sheet with a text of 10 points, a text of 5 points and a title text of 14 points, bold
- **WHEN** `uv run pytest tests/unit/backends/altium/test_schdot_write.py -k distinct_fonts` writes it as a template
- **THEN** the table holds three fonts (10 regular, 5 regular, 14 bold), the label of 10 points names font 1, the other two name fonts 2 and 3, and the drawing sheet read back equals the one written inside the written scope

#### Scenario: Binary and ASCII
- **WHEN** `uv run pytest tests/unit/lens/test_altium_sheet.py -k distinct_fonts` builds the blink design with the shipped sheet `iso5457_generic` in the binary and in the ASCII form
- **THEN** both documents hold the same font table of three distinct fonts (10, 5 and 7 points), no two entries are equal, and every `FONTID` names an entry of the table

#### Scenario: A frame that repeats a font of the sheet record
- **WHEN** `SheetFrame(…, fonts=((10, False, False),)).sheet_record(base)` is called with the schematic writer's sheet record as `base`
- **THEN** `ValueError` is raised and names the font
