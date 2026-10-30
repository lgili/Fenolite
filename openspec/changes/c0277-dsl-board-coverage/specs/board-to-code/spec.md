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

### Requirement: Texts and dimensions in an import
The import SHALL write a board text on a layer the DSL takes, a copper layer included, as `design.text()` with the style the reader keeps in the text's slots (`knockout`, `bold`, `italic`, `face`), a size of two values as a `(width, height)` pair, several lines and an empty text as they are. A text whose slots hold what `design.text()` cannot say (a hidden text, a mirror that does not follow the layer side) MUST be the unexpressed kind `text`. An aligned or orthogonal dimension on a layer the DSL takes SHALL be written as `design.dimension()` when its `format` and `style` hold the values a created dimension writes, but its line width and its extension offset (`extension_offset=`); another one MUST be `dimension-style`, and a dimension of another kind stays `dimension`.

#### Scenario: Styled texts and an older dimension
- **GIVEN** the two-sheet board with a knocked-out bold text of size 2 × 1.25 mm, a text of two lines, an empty text, a copper text, a text with a face and italic, a hidden text, an aligned dimension with extension offset 0 and one in automatic units (`tests/_importcode.py::drawn`)
- **WHEN** it is imported with `--allow-lossy --confirm` and built
- **THEN** `result.unexpressed` is `text` (1, the hidden one) and `dimension-style` (1), `design.py` holds the five texts and `extension_offset=mm("0")`, and the built board holds `(layer "F.SilkS" knockout)` and `(font (size 2 1.25) (thickness 0.275) (bold yes))`
