## ADDED Requirements

### Requirement: Schematic scene
`fenolite.view.schematic.build_schematic_scene(document, *, name, data, evidence)` SHALL turn an Altium `SchDocument` into plain JSON (`fenolite.view_schematic.v0`, `kind` `"schematic"`) in integer micrometres from the sheet's top-left corner, Y downwards: sheet, fonts, primitives in stream order, objects, components and nets. It SHALL run no tool and use the standard library only.

#### Scenario: Counts of an Altium sheet
- **GIVEN** `tests/data/altium/tree/tree_io.SchDoc`
- **WHEN** `uv run pytest tests/unit/view/test_schematic.py -k counts` builds its scene
- **THEN** the scene holds one object per component, wire, bus, bus entry, net label, power port, port, sheet symbol and sheet entry of the document, and one pin object per pin shown
- **AND** `meta` holds the file name, its SHA-256, the backend `altium`, the evidence level, the counts and notes that say which drawings are Fenolite's

### Requirement: Drawn records
Every component, shown pin, wire, bus, bus entry, net label, power port, port, junction, No ERC directive, sheet symbol, sheet entry, harness connector, text, text frame and graphic of the document SHALL appear in the schematic scene, in the colour and line width of its record.
- Hidden pins and parameters, the children of another part or display mode, and the model records MUST be left out.
- IEEE symbols that are not drawn MUST be counted in a note.

#### Scenario: Every graphic kind
- **GIVEN** an ASCII sheet authored in the test with a line, a polyline, a polygon, a rectangle, a round rectangle, an ellipse, an arc, an elliptical arc, a pie, a Bezier curve, a label, a text frame and a hidden parameter
- **WHEN** its scene is built
- **THEN** each record is one or more primitives of the kind of its shape, and the hidden parameter is not drawn

### Requirement: Sheet frame and special strings
The schematic scene SHALL size the sheet from the custom size or from `SHEETSTYLE`, turned for portrait, and SHALL colour it with the sheet's area colour. When the area colour is missing, the colour seen in files SHALL be used, with a note.
- A text that starts with `=` MUST show the parameter it names: the owner's for a component parameter, the sheet's for any other text. When no parameter of that name exists, the text MUST be shown as written.

#### Scenario: A parameter that names another
- **GIVEN** an ASCII sheet authored in the test with a component whose `Comment` is `=Value` and whose `Value` is `10k`, and a label `=Title` on a sheet whose parameter `Title` is `Main`
- **WHEN** its scene is built
- **THEN** the scene holds the texts `10k` and `Main`, and the sheet is the A4 drawing area, 292 100 by 193 040 µm

### Requirement: Nets of a sheet
The nets of the schematic scene SHALL be the local nets of the sheet. Every wire SHALL carry the net of the pin end or identifier that lies on its wire group, and every pin, label, power port, port and sheet entry SHALL carry the net of its record.

#### Scenario: Wires carry their nets
- **GIVEN** `tests/data/altium/sample/altium_sample.SchDoc`
- **WHEN** its scene is built
- **THEN** the scene's nets have the pins of `local_nets`, and every wire under a net label carries the net of that label's name

### Requirement: Schematic documents in the project tree
`fenolite.view.project.load_tree` SHALL mark every Altium `.SchDoc` of a tree as viewable, and SHALL accept a single `.SchDoc` as a tree of one document. Other schematic formats MUST stay listed as not viewable.

#### Scenario: An Altium project with sheets
- **GIVEN** `tests/data/altium/hier/altium_hier.PrjPcb` and `tests/data/altium/blink/blink.PrjPcb`
- **WHEN** `uv run pytest tests/unit/view/test_project.py -k schematic` loads their trees
- **THEN** the three `.SchDoc` documents of the first are viewable and the first is opened, and the board of the second is still opened before its schematic

### Requirement: Schematic page
`page.html` SHALL draw a schematic scene in the manner of Altium Designer: the sheet and its grid on a grey workspace, in the file's colours and in the fonts the sheet names. A standalone page SHALL embed the schematic scenes as it embeds board scenes.

#### Scenario: A schematic scene round-trips through the export
- **GIVEN** the tree and the scene of `tests/data/altium/hier/altium_hier.SchDoc`
- **WHEN** `uv run pytest tests/unit/view/test_page.py -k schematic` exports the page and reads the embedded JSON back
- **THEN** the JSON equals the scene, the page holds no `http://` or `https://` URL, and its script holds the schematic drawing (`drawSch`)

### Requirement: Schematic interaction
The schematic page SHALL offer:
- wheel zoom and drag to pan;
- a click that selects a part, or that highlights a net while the rest dims;
- a Properties panel and a Navigator panel of parts and nets;
- search by designator or net name;
- the project's schematics as tabs along the bottom;
- a double click that opens a sheet symbol's child sheet, or cross-probes a part to the board and back.

#### Scenario: The page holds the interaction
- **WHEN** `uv run pytest tests/unit/view/test_page.py -k schematic` reads the packaged page
- **THEN** its script names the Navigator (`navList`), the sheet tabs (`sheetTabs`), the net highlight (`selNet`) and the cross-probe (`crossProbe`)
