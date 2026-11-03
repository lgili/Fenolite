## ADDED Requirements

### Requirement: Palettes of the native tools
`fenolite.view.themes` SHALL hold two palettes authored for Fenolite, `kicad` and `altium`, each with board colours (background, board fill, a colour per layer) and schematic role colours. It SHALL give a document the palette of its backend: `kicad` for a KiCad board or schematic, `altium` for an Altium board. An Altium sheet SHALL keep the colours of its records.

#### Scenario: Each backend gets its palette
- **WHEN** `uv run pytest tests/unit/view/test_themes.py -k backend` builds the scenes of `tests/data/kicad/board/two_layer.kicad_pcb` and `tests/data/altium/board6/board6.PcbDoc`
- **THEN** the first scene's `theme.name` is `kicad` and its `F.Cu` colour is the `kicad` palette's; the second's is `altium` with the `altium` palette's colour

### Requirement: KiCad colour theme file
`fenolite.view.themes.read_kicad_theme(path)` SHALL read a KiCad colour theme JSON file into a palette: each documented board and schematic key replaces the colour of its slot, an `rgba` alpha is kept as an opacity, and a key the file leaves out keeps the `kicad` palette's colour. A file that is not a JSON object of that form SHALL raise `FormatError`.

#### Scenario: An authored theme file
- **GIVEN** a theme file authored in the test with `board.background`, `board.copper.f`, `schematic.wire` and `schematic.component_body`
- **WHEN** `uv run pytest tests/unit/view/test_themes.py -k file` reads it
- **THEN** those four slots hold the file's colours, every other slot holds the `kicad` palette's, and a file whose `schematic` is a list raises `FormatError`

### Requirement: KiCad schematic scene
`fenolite.view.kicad_schematic.build_kicad_schematic_scene(text, *, name, data, palette)` SHALL turn a `.kicad_sch` into a `fenolite.view_schematic.v0` scene with stroke texts, in the palette's colours. Symbols SHALL be placed by the turn-then-mirror rule of `docs/formats/kicad/schematic.md`, and the scene SHALL hold the sheet's nets from wires, junctions, labels, power symbols and pin ends.

#### Scenario: Counts and pin points of a KiCad sheet
- **GIVEN** `tests/data/kicad/schematic/flat.kicad_sch`
- **WHEN** `uv run pytest tests/unit/view/test_kicad_schematic.py -k counts` builds its scene
- **THEN** it holds one comp per placed symbol, one object per wire, label, junction and no-connect, and every visible pin's line ends at the connection point the placement rule gives

#### Scenario: Wires carry their label's net
- **GIVEN** `tests/data/kicad/schematic/flat.kicad_sch`
- **WHEN** its scene is built
- **THEN** every wire under a label carries the net of that label's text

### Requirement: KiCad schematics in the project tree
`fenolite.view.project.load_tree` SHALL mark `.kicad_sch` documents as viewable and SHALL accept a lone `.kicad_sch` as a tree of one document.

#### Scenario: A lone KiCad sheet
- **WHEN** `uv run pytest tests/unit/view/test_project.py -k kicad_sheet` loads `tests/data/kicad/schematic/flat.kicad_sch`
- **THEN** the tree holds one viewable schematic

### Requirement: Themed page
The viewer page SHALL paint a board with its scene's theme background and board colours, a schematic's surroundings with its sheet's workspace colour, and the texts of a stroke-text schematic with Fenolite's stroke font.

#### Scenario: The page reads the theme
- **WHEN** `uv run pytest tests/unit/view/test_page.py -k theme` reads the packaged page
- **THEN** its script reads `S.theme`, `sheet.workspace` and `sheet.text`
