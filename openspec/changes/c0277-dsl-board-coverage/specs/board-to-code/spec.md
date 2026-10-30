## ADDED Requirements

### Requirement: Teardrops in an import
`fenolite import --to python` SHALL read the `teardrops` child that the KiCad reader keeps in the slots of a via and SHALL write it as `teardrop=teardrop(...)` of the via's table, vias being grouped by their settings too. A child the import cannot read MUST be counted as the unexpressed kind `teardrop-setting`, the via being written without it. A teardrop zone of the type `padvia` MUST NOT be written and MUST NOT be unexpressed: the import SHALL report the count once as `import.teardrops-regenerated` (info), because KiCad draws it again from the settings the code keeps (the pads' in their vendored footprints). A teardrop zone of another type, and every teardrop zone when a via's settings could not be read or a via or footprint holding settings is left out, MUST be the unexpressed kind `teardrop`.

#### Scenario: Settings kept and zones regenerated
- **GIVEN** the authored two-sheet board with the demo teardrop settings on its via at (110, 133) and one `padvia` teardrop zone (`tests/_importcode.py::teardropped`)
- **WHEN** it is imported with `--confirm` and the code is built
- **THEN** `copper.py` holds `teardrop=teardrop(` in the table of that via, `issues` hold `import.teardrops-regenerated`, `result.unexpressed` holds no teardrop kind, and the built via holds a `teardrops` child of nine children

#### Scenario: Settings lost
- **GIVEN** the same board whose via holds `(teardrops (enabled maybe))`
- **WHEN** it is imported with `--allow-lossy --dry-run`
- **THEN** `result.unexpressed` holds `teardrop` (1) and `teardrop-setting` (1), and no `import.teardrops-regenerated`

### Requirement: Blind vias over the board in an import
A blind via whose two layers are the outer copper layers SHALL be written as a row of a via table with `kind="blind"` and those layers ("Blind vias over the board in via tables"), not left out as `via-span`.

#### Scenario: Demo vias kept
- **GIVEN** the two-sheet board whose via at (130, 133) is `(via blind … (layers "F.Cu" "B.Cu"))`
- **WHEN** it is imported and built
- **THEN** the table `GND/via/1` holds that row with `kind="blind"`, `result.unexpressed` holds no `via-span`, and the built via is blind on both layers

### Requirement: Parts not populated and net ties in an import
The import SHALL write a part whose component is not populated as `Part(..., dnp=True)`, and MUST NOT count it as unexpressed. A footprint's net-tie pad groups SHALL come back with its vendored footprint and MUST NOT be counted as unexpressed.

#### Scenario: One part not populated, one net tie
- **GIVEN** the two-sheet board with R101's attribute `(attr smd dnp)` and R201 holding `(net_tie_pad_groups "1, 2")` (`tests/_importcode.py::unfitted`)
- **WHEN** it is imported with `--confirm` and the code is built
- **THEN** `result.unexpressed` is empty, `design.py` holds one `dnp=True`, and the built board holds `(attr smd dnp)` for R101 and the net-tie groups for R201

### Requirement: Groups in an import
The import SHALL write a group of the board whose members it all writes (parts, drawings, zones, rule areas and groups) as `design.group()` after the drawings, an inner group before the group that holds it, with the source name as name and key when the key pattern takes it and `key="group/<n>"` otherwise, and `locked=True` for a locked group. A group holding an item the code does not write MUST be the unexpressed kind `group`.

#### Scenario: Nested groups
- **GIVEN** the `drawn` board with a locked group `logo` of J1, a text and a dimension, an unnamed group of `logo` and a text, and a group `lost` of the hidden text (`tests/_importcode.py::drawn_grouped`)
- **WHEN** it is imported with `--allow-lossy --confirm` and built
- **THEN** `result.unexpressed` holds `group` (`lost`), `design.py` holds two `design.group()` calls, and the built board holds `logo`, locked, with the uuids of J1's footprint, the text and the dimension, and the unnamed group with the uuids of `logo` and the text

### Requirement: Board-only parts in an import
The import SHALL write each footprint that shares its reference with another, or has one a script cannot name (an empty reference, `REF**`), as `Part(<its reference>, ..., name=<key>, board_only=True)`, the key its reference cut to the name alphabet (`fp` when nothing is left) followed by `_<n>`, the lowest number no other reference or key holds, in placement order; a footprint with KiCad's `board_only` attribute SHALL also be a board-only part. Such a part MUST NOT be counted as unexpressed and holds no lock entry. The import SHALL report them once as `import.board-only` (info), with the count of those that gain the `board_only` attribute. The self-check pairs them by placement ("Level 1 compares components").

#### Scenario: Two footprints of one reference and a REF**
- **GIVEN** the two-sheet board with R201 renamed R101 and J1 renamed `REF**` (`tests/_importcode.py::shared`)
- **WHEN** it is imported with `--confirm` and built
- **THEN** `result.unexpressed` is empty, `import.board-only` names 3 footprints of which 3 gain the attribute, `design.py` holds three `board_only=True`, and the built board holds two footprints `R101` and one `REF**`, each with `board_only`

### Requirement: Board items in an import
The import SHALL write (change c0277): `design.user_layers()` up to the highest `User.<n>` of the source table, with the user names it holds, and the drawings on those layers; a graphic on a copper layer with `net=` of its net, read from its slots (the number of a 9.0 board through its net table); a filled shape whose stroke is −1 nm with `width=None`; a via's `(free yes)` as `free=True` of its table, vias grouped by it; a zone's smoothing as `smoothing=` and `smoothing_radius=`; a dimension in mils or automatic units; and the material of a silkscreen in the stack-up. A graphic whose slots hold a dashed stroke or a net the code does not declare MUST be the unexpressed kind `drawing`.

#### Scenario: Items of change c0277
- **GIVEN** the two-sheet board with user layers `User.1` and `User.2` (`notes`), a copper rectangle of `GND`, a filled polygon of stroke −1 nm, a text on `User.2`, a dimension in automatic units, its via at (110, 133) free and its GND zone smoothed with fillets of 0.5 mm (`tests/_importcode.py::itemized`)
- **WHEN** it is imported with `--confirm` and built
- **THEN** `result.unexpressed` is empty, the code holds each call, and the built board holds the user layers, `(net "GND")` on the rectangle, `(width -0.000001)`, `(units 3)` and one free via at (110, 133)

### Requirement: Texts and dimensions in an import
The import SHALL write a board text on a layer the DSL takes, a copper layer included, as `design.text()` with the style the reader keeps in the text's slots (`knockout`, `bold`, `italic`, `face`), a size of two values as a `(width, height)` pair, several lines and an empty text as they are. A text whose slots hold what `design.text()` cannot say (a hidden text, a mirror that does not follow the layer side) MUST be the unexpressed kind `text`. An aligned or orthogonal dimension on a layer the DSL takes SHALL be written as `design.dimension()` when its `format` and `style` hold the values a created dimension writes, but its line width and its extension offset (`extension_offset=`); another one MUST be `dimension-style`, and a dimension of another kind stays `dimension`.

#### Scenario: Styled texts and an older dimension
- **GIVEN** the two-sheet board with a knocked-out bold text of size 2 × 1.25 mm, a text of two lines, an empty text, a copper text, a text with a face and italic, a hidden text, an aligned dimension with extension offset 0 and one with a prefix (`tests/_importcode.py::drawn`)
- **WHEN** it is imported with `--allow-lossy --confirm` and built
- **THEN** `result.unexpressed` is `text` (1, the hidden one) and `dimension-style` (1), `design.py` holds the five texts and `extension_offset=mm("0")`, and the built board holds `(layer "F.SilkS" knockout)` and `(font (size 2 1.25) (thickness 0.275) (bold yes))`
