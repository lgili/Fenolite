## MODIFIED Requirements

### Requirement: Viewer page
`src/fenolite/view/page.html` SHALL be one HTML file with inline styles and scripts and no external URL, assembled by `fenolite.view.export.page(tree, scenes)` from `src/fenolite/view/ui/` in a fixed order, that draws a scene in 2D (canvas) and 3D (WebGL) inside the workbench of "Workbench shell" and embeds a tree and its scenes.
- The page MUST read a scene either embedded (export) or from the server routes of "Live server".
- Texts MUST be drawn with Fenolite's own single-stroke font.

#### Scenario: Standalone page round-trips
- **GIVEN** the tree and the scene of `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/unit/view/test_page.py` exports the page and reads the embedded JSON back
- **THEN** the JSON equals the scene, and the page holds no `http://` or `https://` URL

#### Scenario: Assembly from the UI sources
- **WHEN** `uv run pytest tests/unit/view/test_ui_sources.py -k assembly` assembles the page twice
- **THEN** both pages are byte-identical, and every file under `src/fenolite/view/ui/` is included exactly once

### Requirement: Context-aware viewer shortcuts

Viewer shortcuts, resolved through the active keymap of "Keymaps", SHALL NOT run while an input, select, textarea or editable descendant has focus, during composition, or after default prevention. A Ctrl, Meta or Alt combination SHALL run only when the active keymap binds it. The plain and Shift shortcuts of the `fenolite` keymap SHALL keep today's meaning outside those contexts.

#### Scenario: Selecting a highlight mode

- **WHEN** M is pressed with the highlight select focused
- **THEN** the viewer does not enter Measure, and an ordinary M outside form controls still toggles Measure

#### Scenario: An unbound combination passes through

- **WHEN** Alt+M is pressed with the `fenolite` keymap, which does not bind it
- **THEN** no viewer command runs and the event is not prevented

### Requirement: Review in narrow windows

At viewport widths of 760 CSS pixels or below the viewer SHALL collapse every dock into one drawer behind a labelled, keyboard-operable Panels toggle, start with it closed, and adapt the toolbar so the canvas keeps the viewport width. The open drawer SHALL fit the viewport and remain dismissible. Above the breakpoint the docked layout of "Docked panels and layouts" SHALL apply.

#### Scenario: A 390-pixel window

- **WHEN** the viewer opens at 390 CSS pixels and the drawer is toggled open and closed
- **THEN** the canvas uses the full available width, controls remain reachable, and the toggle exposes its expanded state

#### Scenario: Desktop remains unchanged

- **WHEN** the viewer opens at 1100 CSS pixels with the default layout
- **THEN** the left dock keeps the former sidebar's 260 pixels, the right and bottom docks are shown, and the narrow-screen Panels toggle is hidden

#### Scenario: Sidebar dismissal does not require a CAD scene

- **GIVEN** a narrow window with the drawer open and focus outside a form field
- **WHEN** Escape is pressed while a table document is open or no scene is loaded
- **THEN** the drawer closes and focus returns to its toggle

## ADDED Requirements

### Requirement: Workbench shell
Every document SHALL open in one workbench:
- a title line;
- a menu bar (File, Edit, View, Place, Design, Roles, Route, Tools, Reports, Window, Help);
- an icon toolbar with grid, unit, view and net drop-downs;
- left, right and bottom docks;
- the canvas with a dot grid and a crosshair;
- layer tabs;
- a status bar with x/y, dx/dy, grid, net and role, layer, tool version and evidence.

Today's panels and tools MUST remain reachable.

#### Scenario: The frame of a board
- **WHEN** `uv run pytest tests/visual/test_workbench.py -k shell` opens the KiCad board fixture
- **THEN** the menu bar holds the eleven menus, the status bar holds its seven fields, and Projects, Findings, Filter, Components, Nets and Notes are panels in the docks

### Requirement: Docked panels and layouts
Panels SHALL live in tabbed groups in the left, right and bottom docks, with title bars, pin, close and keyboard-operable splitters. A panel MAY move by drag or by its panel menu, and in served mode MAY float into its own window that shares the selection. The layout of each workspace SHALL be kept in the browser, saved and read as `fenolite.view_layout.v0`, and restored by Window ▸ Reset Layout.

#### Scenario: A layout survives a reload
- **WHEN** `uv run pytest tests/visual/test_workbench.py -k layout` moves Messages to the right dock, reloads, then resets the layout
- **THEN** Messages is in the right dock after the reload and back in the bottom dock after the reset

### Requirement: Keymaps
Every command SHALL be registered with an id, a label, a menu place and its keys, and menus, toolbar, command search and the Keyboard panel MUST be generated from that registry. The keymaps `fenolite` (default), `altium` (with accelerator sequences) and `kicad`, and a `fenolite.view_keymap.v0` file over one of them, SHALL be offered. A binding of a key that the browser reserves MUST be refused.

#### Scenario: An accelerator sequence
- **WHEN** `uv run pytest tests/visual/test_workbench.py -k keymap` presses V then F in the `altium` keymap
- **THEN** the view fits the board, the status bar showed the pending `V` in between, and binding `Ctrl+W` in the Keyboard panel is refused with a message

### Requirement: Workbench themes
The workbench chrome SHALL offer the themes `dark` (default), `light` and `contrast`, chosen in View ▸ Theme and kept in the browser. Each document MUST keep its tool's palette (c0178), with a light variant for `light`. Role colours MUST come from the role palette, and every role MUST also show its glyph and name. Theme text tokens MUST reach 4.5:1, and control tokens 3:1.

#### Scenario: Contrast and colour separation
- **WHEN** `uv run pytest tests/unit/view/test_themes.py -k "contrast or cvd"` runs
- **THEN** every token pair meets its ratio in the three themes, and the role colours meet the criterion of `H-G-WB-CVD`

### Requirement: One selection model
The canvas, every panel, the layer tabs, the Messages panel, the status bar, the page address and served windows SHALL read and write one selection store, so that a selection made anywhere is shown everywhere and `Esc` clears it everywhere.

#### Scenario: Five ways to one net
- **WHEN** `uv run pytest tests/visual/test_workbench.py -k selection` selects net `SW` from the canvas, the Nets panel, the Net drop-down, a Messages row and the address
- **THEN** the five state hashes are equal, and after `Esc` nothing is selected in any panel

### Requirement: Linked messages
The Messages panel SHALL list the findings shown with severity, code, object, message, source and layer. A click on a row MUST frame its copper and make its layer current. A click on its canvas marker MUST select and reveal the row. Each row MUST show its `fenolite explain` text on demand. A finding without a position MUST say so.

#### Scenario: Both directions
- **WHEN** `uv run pytest tests/visual/test_workbench.py -k linked` clicks the row of an authored finding, then its marker
- **THEN** the view frames the finding's copper on its layer, and the marker click selects the same row

### Requirement: Provenance of displayed values
Every value shown in Properties, Measures, Limits, Messages and on-canvas measure labels SHALL carry its source (analysis, S-id, hypothesis, rule, `default` or `override`) and its evidence level, shown on the line or on hover. The status bar MUST show the lowest evidence level of what is on screen.

#### Scenario: No value without a source
- **WHEN** `uv run pytest tests/visual/test_workbench.py -k "provenance or evidence"` opens the roles workspace of the `bad` buck board
- **THEN** every `[data-value]` element has a non-empty `data-source` and `data-evidence`, and the status bar reads `INFERRED`

### Requirement: Viewer frame budget
On the authored stress board, the page SHALL keep pan and zoom frames, crosshair moves and the first draw within the budgets of `H-G-WB-FRAME`, `H-G-WB-CURSOR` and `H-G-WB-OPEN`. A crosshair or hover move MUST NOT redraw a board layer.

#### Scenario: The budget in CI
- **WHEN** `uv run pytest tests/visual/test_workbench.py -k budget` runs in the `viewer` job
- **THEN** the p95 frame times and the open time are within the budgets, and no board layer was redrawn during 200 pointer moves

### Requirement: Workbench accessibility
The chrome SHALL meet WCAG 2.2 AA:
- the menu bar, tabs, tables and splitters follow their WAI-ARIA patterns;
- focus is always visible and never hidden;
- every drag has a pointer or keyboard alternative;
- colour is never the only cue;
- the selection is announced in a live region.

No routine action MAY use a modal dialog.

#### Scenario: Keyboard only
- **WHEN** `uv run pytest tests/visual/test_workbench.py -k a11y` opens File with Alt+F, walks the menus with arrows, moves a panel through its menu and selects a net from the Nets grid
- **THEN** each step has a visible focus, names and roles are exposed, and no `alert`, `confirm`, `prompt` or modal dialog appeared
