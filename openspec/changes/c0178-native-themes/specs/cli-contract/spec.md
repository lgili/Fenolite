## ADDED Requirements

### Requirement: View command takes a theme
`fenolite view --theme THEME` SHALL draw the KiCad documents of a project in a KiCad colour theme (`native-themes`). `THEME` is a path to a theme JSON file, or the name of a theme in the `colors` folder of the user's KiCad settings. The reply SHALL name the palette of the document shown in `result.theme`. A theme that is not found SHALL be `FEN-3001`, and a malformed one `FEN-3004`.

#### Scenario: A theme file on a KiCad board
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k theme` runs `fenolite view tests/data/kicad/board/two_layer.kicad_pcb --theme <authored>.json --json`
- **THEN** the exit code is 0 and `result.theme` is `kicad:<authored>.json`; a missing theme name exits 3 with `FEN-3001`
