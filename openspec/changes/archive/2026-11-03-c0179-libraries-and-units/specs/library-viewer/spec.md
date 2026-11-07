## ADDED Requirements

### Requirement: Footprint library scene
`fenolite.view.library.footprint_library_scene(path, *, palette)` SHALL turn an Altium `.PcbLib`, a KiCad `.pretty` folder or a `.kicad_mod` into a `fenolite.view_library.v0` scene with one item per footprint. Each item SHALL hold a board scene of the footprint placed alone at the origin, in the palette of its tool.

#### Scenario: Footprints of an Altium library
- **GIVEN** `tests/data/altium/blink/blink.PcbLib`
- **WHEN** `uv run pytest tests/unit/view/test_library.py -k footprint` builds its scene
- **THEN** it holds one item per footprint the backend reads, and each item's `pads` holds every pad of that footprint with the model's exact width, height and drill in nanometres and its centre in micrometres

### Requirement: Symbol library scene
`fenolite.view.library.symbol_library_scene(path, *, palette)` SHALL turn an Altium `.SchLib` or a KiCad `.kicad_sym` into a `fenolite.view_library.v0` scene with one item per symbol, and one per part or unit of a symbol that has several. Each item SHALL hold a schematic scene of that part, on a sheet the size of the symbol.

#### Scenario: Symbols of both tools
- **GIVEN** `tests/data/altium/blink/blink.SchLib` and `tests/data/libs/Mini_v9.kicad_sym`
- **WHEN** `uv run pytest tests/unit/view/test_library.py -k symbol` builds their scenes
- **THEN** each holds an item for every symbol the backend reads, and each item's pin objects count the visible pins of that part

### Requirement: Pad data of a board scene
A board scene SHALL list every pad with its label, centre, size, drill, slot length, shape, rotation, corner ratio, kind, layers, net and part. Sizes, drill and slot SHALL be in nanometres, taken from the model pad.

#### Scenario: Pads of a KiCad board
- **WHEN** `uv run pytest tests/unit/view/test_library.py -k board_pads` builds the scene of `tests/data/kicad/board/two_layer.kicad_pcb`
- **THEN** its `pads` count equals the board's pads, and each entry's size equals its model pad's

### Requirement: Units and measurement
The viewer page SHALL show every length in millimetres or in mil, switched by a Units button and the key `Q`, and SHALL measure on boards, sheets and library items, snapping to pad centres and vertices, with the distance, dx and dy in the current unit.

#### Scenario: Unit conversions
- **WHEN** `uv run pytest tests/unit/view/test_page.py -k units` evaluates the page's `fmtLen` and `fmtNm`
- **THEN** 1.2 mm reads `1.200 mm` and `47.24 mil`, and 254 000 nm reads `0.254 mm` and `10.00 mil`

### Requirement: Libraries in the project tree
`fenolite.view.project.load_tree` SHALL mark `.PcbLib`, `.SchLib`, `.kicad_sym` and `.pretty` documents as viewable, and SHALL accept one of them alone as a tree of one document.

#### Scenario: An Altium project with libraries
- **WHEN** `uv run pytest tests/unit/view/test_project.py -k libraries` loads `tests/data/altium/blink/blink.PrjPcb`
- **THEN** `blink.PcbLib` and `blink.SchLib` are viewable
