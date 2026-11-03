## ADDED Requirements

### Requirement: Script editing tool
The tool `fenolite_edit` SHALL take `path` and exactly one of `content` (a string) and `edits` (a list of `{old, new}` strings), write the value to a file in the server's state folder, and run `fenolite edit` with `--content-file` or `--edits-file`; the input file SHALL be removed when the call ends.
- The tool MUST follow "Writes through a reviewed plan".
- A confirmation with a content different from its dry run's MUST be refused by the command line (`FEN-4002`).

#### Scenario: Edit through the server
- **WHEN** `uv run pytest tests/unit/mcp/test_writes.py -k edit` calls `fenolite_edit` with one pair on a starter script, then confirms the returned plan
- **THEN** the dry run returns the diff and writes nothing, the confirmation writes the script, and no input file is left in the state folder

### Requirement: Images in replies
When a tool's reply plans or writes PNG files, the result SHALL hold each one as an image content item (`image/png`, base64) after the envelope's text, from the staged plan of a dry run or from the written file of a confirmed run, at most 4 images and 6 MB of image bytes, with a text item naming what was left out.

#### Scenario: A dry run of a render is seen
- **GIVEN** `kicad-cli` and a committed board
- **WHEN** `uv run pytest tests/kicad/mcp/test_render_images.py` calls `fenolite_render` with `png`, `width` 400 and `height` 300 and no `confirm`
- **THEN** the content holds the envelope's text and two PNG images whose bytes have the sha256 of the plan's rows, and nothing is written

## MODIFIED Requirements

### Requirement: Commands not exposed
The server SHALL NOT list `mcp`, `skill` or a hidden command as a tool, SHALL NOT list `fenolite_edit` unless it was started with `--allow-edit` and without `--read-only`, and the schema of `fenolite_view` SHALL NOT hold `serve`, `port` or `no_browser`.

#### Scenario: Excluded commands
- **WHEN** `uv run pytest tests/unit/mcp/test_tools.py -k excluded` lists the tools
- **THEN** no tool is named `fenolite_mcp`, `fenolite_skill` or `fenolite__echo`, and `fenolite_view` has no property `serve`

#### Scenario: Edit not listed by default
- **WHEN** the test lists the tools of a catalog made without `allow_edit`
- **THEN** no tool is named `fenolite_edit`
