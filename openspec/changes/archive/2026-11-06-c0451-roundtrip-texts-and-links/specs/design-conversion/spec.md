## MODIFIED Requirements

### Requirement: Project parameters and special strings
A conversion of an Altium project SHALL write its `[Parameter<n>]` entries whose names are variable names as project text variables, report the others, and write a board text that is the special string `.NAME` of a project parameter, or holds it as `'.NAME'` inside other text, with `${NAME}` in its place; a predefined special string of `altium_strings.PREDEFINED` SHALL be written as KiCad's variable of the same meaning, and every other special string whose name is a variable name SHALL be written as `${NAME}`, a variable the project does not define, with a `text` change in the report (change c0451; before, as typed). A conversion of a KiCad project to Altium SHALL write a board text `${NAME}` as `.NAME` and `${NAME}` inside other text as `'.NAME'`, KiCad's `CURRENT_DATE`, `FILENAME`, `FILEPATH` and `LAYER` as `.Print_Date`, `.Pcb_File_Name_No_Path`, `.Pcb_File_Name` and `.Layer_Name`, and the project's text variables as the project file's `[Parameter<n>]` entries (change c0451).

#### Scenario: A parameter on the silkscreen
- **GIVEN** a copy of the blink sample whose project holds `[Parameter1]` `Name=REV_CODE`, `Value=B2` and `[Parameter2]` `Name=Made By`, and whose board holds the texts `.REV_CODE`, `Rev '.REV_CODE' on '.Print_Time'` and `.Comment`
- **WHEN** `uv run pytest tests/unit/convert/test_project_parameters.py -q` converts and imports it
- **THEN** the `.kicad_pro` holds the text variable `REV_CODE` = `B2` alone, `Made By` gives `altium.import.unmapped`, the board texts are `${REV_CODE}`, `Rev ${REV_CODE} on ${Print_Time}` and `${Comment}` with `text` changes in the report, and the imported code declares the variable and keeps `${REV_CODE}`

#### Scenario: Parameters come back
- **GIVEN** the same source converted to KiCad
- **WHEN** `uv run pytest tests/unit/convert/test_project_parameters.py -q -k back` converts that project to Altium
- **THEN** the board texts are `.REV_CODE`, `Rev '.REV_CODE' on '.Print_Time'` and `.Comment`, and the project file holds `[Parameter1]` `Name=REV_CODE`, `Value=B2`

## ADDED Requirements

### Requirement: Altium round trip keeps texts, values and library links
An Altium document converted to KiCad and that project converted back to Altium SHALL keep (change c0451):
each component's footprint link and symbol link as the source holds them, carried by the hidden KiCad
footprint properties `Altium Footprint` and `Altium Symbol` (`convert.altium_links`), which no Altium
parameter receives; each `Value` field, with an empty value too, on its layer and with its shown flag; and
each footprint text, an empty one too. A footprint link comes back only while the KiCad footprint's link
item is the name the conversion derived from the source pattern; otherwise neither property is used.

#### Scenario: Links and values come back
- **GIVEN** the authored `routed` sample whose `D1` has the footprint link `Lib_A:Mini_LED_THT_3mm` and the symbol link `Sym_A:Mini_LED`, whose `R1` has an empty value, and whose `U1` holds an empty text
- **WHEN** `uv run pytest tests/unit/convert/test_round_trip_texts.py -n 0 -q` takes it to KiCad and back
- **THEN** the KiCad footprint of `D1` holds the hidden properties `Altium Footprint` = `Lib_A:Mini_LED_THT_3mm` and `Altium Symbol` = `Sym_A:Mini_LED`; the round trip's `D1` holds those links and no such property; `R1` holds its hidden `Value` field; `U1` holds the empty text

#### Scenario: A swapped footprint drops the link
- **GIVEN** the KiCad project of that conversion with `D1` linked to another footprint
- **WHEN** the same test converts it to Altium
- **THEN** `D1` holds the conversion's own links, as before
