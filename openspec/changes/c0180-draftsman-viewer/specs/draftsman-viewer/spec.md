## ADDED Requirements

### Requirement: Draftsman geometry reader
`fenolite.backends.altium.read.dwfdraw.read_drawing(file)` SHALL read a decoded Draftsman document into its pages (size, margins, zones and items), its styles, its parameters and its copy of the board: outline, layers with their primitives, holes and parts. A part's local geometry SHALL be placed by its location and rotation, mirrored in Y first for a bottom part.

#### Scenario: An authored document
- **GIVEN** a document authored in the test with one page, a text with a parameter, a top part and a bottom part, an outline with an arc and an assembly view
- **WHEN** `uv run pytest tests/unit/backends/altium/test_dwfdraw.py` reads it
- **THEN** the page, the text, the view and both parts are read, the bottom part's pads land where the mirror-then-turn rule puts them, and the arc of the outline is sampled between its two ends

### Requirement: Drawing scene
`fenolite.view.drawing.drawing_scene(path)` SHALL turn a `.PCBDwf` into a library-form scene with `lib` `drawing` and one item per sheet. Each item SHALL be a schematic-form scene of that sheet in micrometres, Y down from its top-left corner (the sheet's own Y up, flipped): its items, its views drawn from the document's board copy, and its tables.

#### Scenario: Public drawings
- **GIVEN** the four public documents of S-0785 and S-0786 in the corpus cache
- **WHEN** `uv run pytest tests/corpus/test_draftsman_draw.py` builds their scenes
- **THEN** each scene has one item per page and each view draws the board outline, and the board copy's pad centres equal those of the boards of S-0174 and S-0187

### Requirement: Panel note
A board whose `EmbeddedBoards6` stream holds data, and a drawing whose `IsPanel` is true, SHALL carry a note that the document holds an Embedded Board Array that Fenolite does not draw.

#### Scenario: A drawing of a panel
- **GIVEN** an authored document whose `IsPanel` is `true`
- **WHEN** its scene is built
- **THEN** its notes name the Embedded Board Array
