## ADDED Requirements

### Requirement: Interface tokens and themes
The page SHALL style its interface from CSS custom properties for spacing, type sizes, radii, surface, text, accent, focus and severity colours, with a dark and a light set. Without a stored choice it SHALL follow `prefers-color-scheme`; a choice SHALL be kept in `localStorage`. Text tokens MUST reach a contrast of 4.5:1 on their surfaces. A document's own colours MUST NOT change with the theme.

#### Scenario: Tokens and contrast
- **WHEN** `uv run pytest tests/unit/view/test_page.py -k tokens` parses the page's token blocks
- **THEN** every token is defined in both themes, each text and surface pair reaches 4.5:1, and no chrome rule outside the token blocks holds a colour literal

#### Scenario: The light shell keeps the board's colours
- **GIVEN** the exported page of `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/visual/test_shell.py -k theme` switches to the light theme and reloads
- **THEN** the toolbar uses the light surface, the canvas background still equals the scene's theme background, and the choice survives the reload

### Requirement: Grouped toolbar
The toolbar SHALL group its controls as View (2D/3D, Fit, Top/Bottom), Tools (Measure with point and edge modes, Mark, units) and Share (Copy link, Export with SVG and Print and its scale). Each control MUST have an inline SVG icon, an accessible name and a tooltip naming its shortcut. No two controls of the toolbar MAY share a label, and a control that does not apply to the current view MUST be hidden.

#### Scenario: No duplicate labels
- **GIVEN** the exported page of `two_layer.kicad_pcb` at 1440 by 900 pixels
- **WHEN** `uv run pytest tests/visual/test_shell.py -k toolbar` reads the toolbar
- **THEN** it holds the three groups in order, every button has an icon and an accessible name, no label occurs twice, and the print scale is reached from the Export menu

### Requirement: Command palette
`Ctrl+K`, or `Cmd+K` on macOS, SHALL open a command palette that searches the shell's commands and the parts, nets and documents of the open project, and runs or opens the chosen entry with the keyboard. The toolbar, the palette and the shortcut sheet MUST be built from one command registry, so a command reachable in one is reachable in all.

#### Scenario: Jump to a part from a text field
- **GIVEN** the exported page of `two_layer.kicad_pcb` with the filter field focused
- **WHEN** `uv run pytest tests/visual/test_shell.py -k palette` presses `Ctrl+K`, types `r1` and presses Enter
- **THEN** the palette closes, `R1` is selected and framed, and focus returns to the page

#### Scenario: Ranking under Node
- **WHEN** `uv run pytest tests/unit/view/test_page.py -k palette_match` runs `paletteMatch` under Node on authored entries
- **THEN** prefix matches rank before word-start matches, those before other subsequence matches, and a query of `>` lists commands only

### Requirement: Side bar sections
Each side bar section SHALL be a disclosure with its title and a count, its open state remembered in `localStorage`. Components SHALL sort by reference in natural order, value or footprint, and Nets by name, pad count or routed length. Finding groups with a count of 0 SHALL be listed together under one collapsed line that names how many there are.

#### Scenario: Zero groups fold but remain
- **GIVEN** the exported page of `two_layer.kicad_pcb` with its review findings
- **WHEN** `uv run pytest tests/visual/test_shell.py -k sections` reads the Findings section and opens its zero line
- **THEN** only groups with items are listed at first, the zero line names the others, and opening it lists each with its count of 0

### Requirement: Status bar and document details
The status bar SHALL show the cursor position in the page unit, the grid when drawn, the unit, the zoom, the current layer, the selection and the live state, and SHALL NOT show the file's digest. An "About this document" popover SHALL show the file name and path, size, full SHA-256 with a copy control, backend, evidence level and, when live, the scene version.

#### Scenario: The digest moves to the popover
- **GIVEN** the exported page of `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/visual/test_shell.py -k about` reads the status bar, then opens the popover
- **THEN** the status bar holds no hexadecimal digest, and the popover holds the 64 hexadecimal digits of the scene's `meta.sha256` and its evidence level

### Requirement: Loading, empty and error states
While a document loads the page SHALL show its name and a progress indicator; a list with no entries SHALL say why it is empty; a failed read SHALL show its error with a Retry control bound to the current navigation; a project without a viewable document SHALL say so and name the kinds that open.

#### Scenario: A failed read can be retried
- **GIVEN** the exported page with a stubbed scene request that fails once
- **WHEN** `uv run pytest tests/visual/test_shell.py -k retry` opens the document and presses Retry
- **THEN** the error card names the failure, and after Retry the scene is displayed under the same navigation

## MODIFIED Requirements

### Requirement: Context-aware viewer shortcuts

Viewer shortcuts SHALL NOT run while an input, select, textarea or editable descendant has focus, during composition, after default prevention, or with Ctrl, Meta or Alt pressed. Existing plain and Shift shortcuts SHALL continue to work outside those contexts. The one exception SHALL be `Ctrl+K`, or `Cmd+K` on macOS, which SHALL open the command palette also from a focused field, but not during composition or after default prevention.

#### Scenario: Selecting a highlight mode

- **WHEN** M is pressed with the highlight select focused
- **THEN** the viewer does not enter Measure, and an ordinary M outside form controls still toggles Measure

#### Scenario: The palette chord in a text field

- **GIVEN** the search field is focused
- **WHEN** `Ctrl+K` is pressed outside composition
- **THEN** the command palette opens, and a plain `K` typed in the field is text, not a shortcut
