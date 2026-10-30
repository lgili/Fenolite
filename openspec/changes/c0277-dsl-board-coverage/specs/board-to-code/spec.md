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
