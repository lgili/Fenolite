## MODIFIED Requirements

### Requirement: Layers of a converted Altium board
The board of a conversion to KiCad SHALL have one KiCad layer row per layer it holds: copper rows for an even count from 2 to 32 (an odd count of signal layers gets one empty inner layer, counted `changed` under `stackup`); the non-copper layers by name; `Mech.<n>` onto KiCad's user layers in order of `n`, then `Altium.DrillGuide` and `Altium.DrillDrawing` (change c0428), as many as the target holds; a closed outline on `Altium.KeepOut` as a rule area that keeps out tracks, vias and copper pour on every copper layer. Every other item on a layer without a row MUST be a lost row with its reason.

#### Scenario: Mechanical and keep-out layers
- **GIVEN** the public document `altium-third-party-pcbdoc-06`, whose items lie on `Mech.1`, `Mech.2`, `Altium.KeepOut` and `Altium.74`
- **WHEN** it is converted to KiCad 10
- **THEN** the lines of `Mech.1` and `Mech.2` are on the first two user layers, each closed keep-out outline is a rule area, and the three items of `Altium.74` are lost under their kinds with the reason "a layer outside the stack"

#### Scenario: Drill layers
- **GIVEN** a board with lines on `Mech.3`, `Altium.DrillGuide` and `Altium.DrillDrawing`
- **WHEN** `uv run pytest tests/unit/convert/test_to_kicad.py -q -k drill` converts it
- **THEN** they lie on `User.1`, `User.2` and `User.3`, and no `graphic` is lost

### Requirement: Copies of an embedded board array are placed only where measured
A conversion SHALL place the copies of an Embedded Board Array that is unmirrored and turned by a multiple of 90 degrees, and whose referenced document reads.
- The copy in column `c` and row `r` SHALL take a point `p` of the referenced board to (`X`, `Y`) + R((`c` · `COLSPACING`, `r` · `ROWSPACING`) + `p` − `O`), where R is the array's turn.
- `O` SHALL be the board's origin when the origin lies within 1 µm of its shape's lower-left corner, or when the array links its location to the origin. Otherwise `O` SHALL be that corner.
- What S-1592 measured is the rule for 0 and 90 degrees with the origin at the corner. Each other case (180 or 270 degrees, origin away from the corner) MUST carry its inferred rule in the item's reason.
- A referenced document that is not at its path relative to the panel MUST be looked for in this order: relative to the project's folder, by its file name beside the panel or in the project's folder, then at the absolute path stored. Names MUST match without letter case. The reason MUST say how the document was found.
- A mirrored array, an array turned by another angle, and an array whose document is missing or does not read MUST stay refused `embedded-board` losses that name the cause.
- An absolute path MUST be named by its file name only.

#### Scenario: A measured plain array
- **WHEN** a board holds an unturned, unmirrored array whose placement is recorded and its referenced document reads
- **THEN** the conversion writes each copy's components and copper at the measured places, with each copy's designators and nets kept apart

#### Scenario: A turned array
- **WHEN** a board holds an unmirrored array with `ROTATION` 90, 180 or 270
- **THEN** the conversion turns the whole array about its location by one, two or three counter-clockwise quarter turns and turns each copy's footprints with it, and the reason names the inferred rule for 180 and 270

#### Scenario: An origin away from the corner
- **WHEN** the referenced board's origin lies 1 mil right of its shape's lower-left corner
- **THEN** an array that links its location to the origin places the copies by the origin, any other array places them by the corner, and each reason names the inferred rule

#### Scenario: A document found by its name
- **WHEN** an array stores `C:\Work\x.PcbDoc` and `x.pcbdoc` lies beside the panel
- **THEN** the array is placed, its item names `x.PcbDoc` alone, and its reason says the document was read by its file name

#### Scenario: A mirrored array
- **WHEN** a board holds a mirrored array and no saved output records which copper side a mirrored copy takes
- **THEN** the array stays a refused `embedded-board` loss whose reason names the mirror

#### Scenario: An angle that is not a quarter turn
- **WHEN** a board holds an array turned by 45 degrees
- **THEN** the array stays a refused `embedded-board` loss and the conversion exits 7 without `--allow-lossy`

### Requirement: Project parameters and special strings
A conversion of an Altium project SHALL write its `[Parameter<n>]` entries whose names are variable names as project text variables, and report the others.
- A board text that is the special string `.NAME` of a project parameter, or holds it as `'.NAME'` inside other text, SHALL be written with `${NAME}` in its place (change c0409, B10).
- The predefined special strings `.Layer_Name`, `.Pcb_File_Name`, `.Pcb_File_Name_No_Path` and `.Print_Date` (S-1871), in any letter case, SHALL be written as `${LAYER}`, `${FILEPATH}`, `${FILENAME}` and `${CURRENT_DATE}` (S-1870), each with a `text` change. A project parameter of the same name wins (change c0428).
- Every other special string SHALL be written as typed, with a `text` change in the report.
- A board document converted alone SHALL take the parameters of the one project that lists it, searched from the document's folder up to three folders up, nearest first. The board's own variables win.

#### Scenario: A parameter on the silkscreen
- **GIVEN** a copy of the blink sample whose project holds `[Parameter1]` `Name=REV_CODE`, `Value=B2` and `[Parameter2]` `Name=Made By`, and whose board holds the texts `.REV_CODE`, `Rev '.REV_CODE' on '.Print_Time'` and `.Comment`
- **WHEN** `uv run pytest tests/unit/convert/test_project_parameters.py -q` converts and imports it
- **THEN** the `.kicad_pro` holds the text variable `REV_CODE` = `B2` alone, `Made By` gives `altium.import.unmapped`, the board texts are `${REV_CODE}`, `Rev ${REV_CODE} on '.Print_Time'` and `.Comment` with `text` changes in the report, and the imported code declares the variable and keeps `${REV_CODE}`

#### Scenario: Predefined special strings
- **WHEN** a board text is `'.Pcb_File_Name_No_Path' on '.print_date'`
- **THEN** it is written `${FILENAME} on ${CURRENT_DATE}`, and `.Arc_Count` is written as typed

#### Scenario: A board document converted alone
- **GIVEN** a project that lists `PCB\blink.PcbDoc` and holds `[Parameter1]` `Name=REV_CODE`, `Value=B2`
- **WHEN** `uv run pytest tests/unit/convert/test_new_losses.py -q` reads the board document alone
- **THEN** its title block holds `REV_CODE` = `B2`; a board that no project lists holds no parameter

## ADDED Requirements

### Requirement: Contents of an embedded board array's copies
Each placed copy of an Embedded Board Array SHALL carry what the referenced board holds, moved with the copy:
- each zone with its outline, a zone whose outline has arc vertices taking its record's flattened ring;
- each 3D model, placed in the frame of the original footprint by the referenced document's own model records;
- each board cut-out (a closed `Edge.Cuts` polygon), as a `cutout` change.

The ring check of the written board SHALL explain the copies' cut-outs, and each source cut-out that the written board merged with one of them, by the `cutout` row.

#### Scenario: Copies keep their models
- **GIVEN** an authored 2 × 2 panel whose referenced board is the authored document of change c0423, with its bodies and models
- **WHEN** `uv run pytest tests/unit/convert/test_embedded_arrays.py -q -k models` converts the panel
- **THEN** the report has no `model` and no `body` loss, and each copy's footprint names its models with the offset and rotation of the board converted alone

#### Scenario: Copies carry the cut-outs
- **WHEN** the referenced board holds one cut-out and the array has 4 copies
- **THEN** the converted design holds the cut-out 4 times, each at its copy's place (`uv run pytest tests/unit/convert/test_embedded_arrays.py -q -k cutouts`)

#### Scenario: A cut-out merged with a copy's cut-out
- **WHEN** the written board merged a source cut-out with a cut-out that a copy carries
- **THEN** the ring check explains the source ring and the merged ring by the `cutout` row, and explains neither when no copy carries a cut-out (`uv run pytest tests/unit/convert/test_embedded_arrays.py -q -k rings`)

### Requirement: Zones without an outline of a converted Altium board
A conversion to KiCad SHALL give each Altium zone that the import leaves without an outline, or with an outline of fewer than 3 points, the flattened outline of its `Polygons6` record, on the board and in an array's copies. A zone whose record is missing MUST be a `zone` loss that says so. A zone whose record encloses no area (its vertices coincide) pours no copper: it MUST be left out as a `changed` zone whose reason says so, not a loss.

#### Scenario: Records with arcs, without area and missing
- **WHEN** `uv run pytest tests/unit/convert/test_embedded_arrays.py -q -k arc_outlines` outlines three zones whose records are an arc ring, two vertices at one point, and none
- **THEN** the first takes the ring, the second is left out as enclosing no area, and the third as having no record

#### Scenario: A pour without area needs no consent
- **WHEN** `uv run pytest tests/unit/convert/test_to_kicad.py -q -k without_area` converts a zone whose record encloses no area
- **THEN** the zone is not written and is counted `changed`, and the report loses no zone

### Requirement: Duplicate designators of a converted Altium project
A conversion of an Altium project whose circuit holds one designator on several parts, at most one of them on the board, SHALL write its schematic. The part on the board (or the first, when none is) SHALL keep the designator, and each other part SHALL be written as `<ref>_<n>` on the schematic, with a `schematic` change; the design that the conversion verifies SHALL hold the same designators. When several parts on the board share a designator, the board MUST keep them and the schematic MUST be a `schematic` loss whose reason names them.

#### Scenario: A schematic part shares a placed part's designator
- **GIVEN** the blink project with one more schematic part that shares the designator `<ref>` of a placed part
- **WHEN** `uv run pytest tests/unit/convert/test_new_losses.py -q` converts it
- **THEN** the `schematic` row loses nothing, the schematic holds `<ref>` and `<ref>_2`, the board holds no `<ref>_2`, and the read-back leaves no difference of `<ref>` unexplained

#### Scenario: Two parts on the board share a designator
- **WHEN** the twin part is on the board too
- **THEN** the board keeps both designators and the `schematic` row loses the schematic with the reason that names the shared designator
