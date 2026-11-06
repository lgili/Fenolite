# c0451: an Altium board through KiCad and back keeps its texts, values and library links

## Why

Owner-board evidence (generic, S-2100) of what Altium → KiCad → Altium loses: empty footprint texts; a
footprint's Value (comment) field on a mechanical layer or hidden; the components' footprint and symbol
library names, renamed to the project's; special strings such as `.PCB_CODE` that name no project
parameter, written to KiCad as literal text. Measured on the public rows (S-2101, `origin/cac/lote-26`
e55b7cd5e):

- **Empty value.** BMS holds four comment text records with an empty text (BOOT, L3, R53, RESET; two hidden,
  two shown): Altium saves such a record. The import reads each as the component's Value field, KiCad keeps
  the field, and the Altium writer skips the comment record of an empty comment (`pcbdoc`: "a component of
  a model that was read may have no designator or comment"): 4 Value fields lost. A Value field with a
  text on a mechanical layer (`Mech.2` → `User.1` → `Mech.2`) or hidden comes back on the authored sample.
- **Empty footprint text.** The writer refuses a footprint text without characters (`text_problem_of`: "the
  text is empty"), although a saved document holds empty text records.
- **Library links.** Every row comes back with the project's name as the library of every footprint and
  symbol (BMS: 30 footprint libraries become `BMS`); the symbol is the generated `PART_<ref>`. The KiCad
  project holds one derived footprint library and one generated symbol per component, so the source names
  do not reach the KiCad → Altium conversion.
- **Special strings.** A board text that names a project parameter is written to KiCad as `${NAME}`, but the
  KiCad → Altium conversion writes `${NAME}` as typed and no `[Parameter<n>]`: the blink sample with
  `REV_CODE` comes back with the text `${REV_CODE}` and no parameter. A special string that names no
  parameter (`.PCB_CODE`) is written to KiCad as typed, so KiCad cannot resolve it from a variable.

## What Changes

- The Altium writer writes the comment record of a component whose model holds a placed Value field, also
  when the comment is empty; and a footprint text without characters (`pcbdoc.text_problem_of(...,
  footprint=True)`). A board text without characters stays refused.
- The Altium → KiCad conversion writes the source's footprint link and symbol link of each component as the
  hidden footprint properties `Altium Footprint` and `Altium Symbol` (`convert.altium_links`). The
  KiCad → Altium conversion gives them back to the component while the KiCad footprint is still the one
  derived from the source pattern. The written project ships one derived `.PcbLib` and `.SchLib` per
  source library, named as the source names it, and each component links the file that holds its
  footprint and symbol. The two properties are written to no Altium parameter.
- The Altium → KiCad conversion writes a special string that names no project parameter and no predefined
  string as the KiCad text variable `${NAME}`, which the project does not define (a `text` change).
- The KiCad → Altium conversion writes a board text `${NAME}` as `.NAME`, and `${NAME}` inside other text as
  `'.NAME'`; KiCad's `CURRENT_DATE`, `FILENAME`, `FILEPATH` and `LAYER` as `.Print_Date`,
  `.Pcb_File_Name_No_Path`, `.Pcb_File_Name` and `.Layer_Name`; and the project's text variables as the
  project's `[Parameter<n>]` entries.

## Impact

- `backends/altium/pcbdoc.py`, `lower.py`, `project.py`; `convert/altium_to_kicad.py`, `altium_strings.py`,
  `to_altium.py`, `schematic.py`; a new `convert/altium_links.py`.
- Bytes: the KiCad board of an Altium conversion gains two hidden properties per component and `${NAME}`
  for unmapped special strings; the Altium documents of a KiCad conversion change where the inputs hold
  these. A build is unchanged.
