## Context

### The viewer today

`fenolite view` (c0176 and its followers) is a working tool. It has three parts:

- **Python side** (`src/fenolite/view/`, about 370 KB). Scene builders turn the neutral model into plain
  JSON in integer micrometres: `scene.py` for boards, `schematic.py` and `kicad_schematic.py` for sheets,
  `library.py`, `drawing.py` for Draftsman, `bom.py`, `outjob.py`, `compare.py`, `findings.py`,
  `check_overlay.py`, `project_review.py`, `variants.py`, `themes.py` and `altium_layers.py`. It also holds
  the compact scene form (`compact.py`, `fenolite.view_scene.v1`), the scene cache (`cache.py`), the gmsh
  bodies (`meshes.py`, `models.py`) and the server (`server.py`).
- **The page** (`src/fenolite/view/page.html`, 187 KB). One hand-written HTML file with inline CSS and
  JavaScript. It uses no framework and no library, and loads nothing (the `board-viewer` requirement
  "Viewer page"). It draws in 2D with canvas 2D, and in 3D with WebGL and no library. An SVG recorder
  replays the canvas calls for SVG and print.
- **Serving.** `--serve` runs a `ThreadingHTTPServer` from the standard library on `127.0.0.1`. Its routes
  are the page, `/project.json`, `/scene/<id>.json`, `/version/<id>` and `/marks`; a file watcher reloads
  saved files. `--export` writes the page with every scene embedded, gzipped, under the plan protocol.
  The only write the server accepts is a review mark, guarded by the `X-Fenolite-Review` header.

The core has no runtime dependency. gmsh is an optional external program run as a subprocess. The visual
tests (`tests/visual`, the CI job `viewer`) draw eight authored fixtures in the Chromium of Playwright
1.63.0, with the fonts of fonts-dejavu-core 2.37-8, and fail above a 0.1 % pixel difference. The
references are rewritten by `tools/update_view_refs.py`.

What the page shows:

- boards: layers, pads, tracks, zones, keep-outs, dimensions, placement marks, 3D with models, Altium
  layer names and mask expansions;
- Altium and KiCad sheets in their own manner;
- libraries, Draftsman drawings, BOMs and output jobs;
- comparisons (`--compare`), check findings (`--check`), review groups, edge measurement, review marks,
  links, SVG and print, variants;
- the project review status (c0239).

Colours follow each document's tool (c0178), and `--theme` reads a KiCad colour theme.

### What limits it

| limit | where it shows |
|---|---|
| **No application frame.** A 40-pixel toolbar of rounded web buttons (`border-radius:5px`), a fixed 260-pixel sidebar of stacked sections (Projects, Findings, Filter, Components, Nets, Notes), layer tabs and a 24-pixel status line | it reads as a web page: no menu bar, no panel title bars, no docking, no tabs, no Messages table |
| **Fixed keys.** One `keydown` handler with literal keys (`M`, `Q`, `B`, `D`, `E`, `F`, `N`, `X`, `S`, `C`, `+`, `-`, PgUp and PgDn) | no keymap, no Altium or KiCad habits beyond the few already copied, no accelerator sequences, no preferences |
| **No shared selection.** The canvas highlight, the filter, the findings list, the review panel and the BOM each keep their own state, reconciled by hand (c0233 and c0235 fixed races between them) | a selection made in one place is not always reflected in the others |
| **The whole board is redrawn on every pointer move** that changes the readout | the crosshair and hover feedback cost a full frame on large boards |
| **No roles.** c0222's roles, groups, measures, limits and findings exist only as JSON | confirming a role takes a command line, and the copper a role judges cannot be seen |
| **One 187 KB file** | every new panel grows one file that reviewers read as a whole |

### The maintainer's mock-up

The maintainer drew the direction on 2026-10-29: `eda-view.html` and its render `eda-view.png`. Both are in
his session's scratch folder and are not committed: the repository's data-file rules (`tests/data/MANIFEST.toml`,
the residue scan) cover only test data, and this description is enough to build from. It shows the board
`buck_shunt.kicad_pcb`, titled "roles: 6 confirmed, 2 pending":

- **Title bar, menu bar and toolbar.**
  - A title bar with the document name and the role state.
  - A menu bar: File, Edit, View, Place, Design, Roles, Route, Tools, Reports, Window, Help.
  - An icon toolbar: select, move, measure, line, place tools, a "Roles view" drop-down, a "Net: SW"
    drop-down, role actions, a "Grid 0.5 mm" drop-down, an "mm" drop-down, fit and zoom.
- **Left dock.**
  - A **Net Roles** panel with the tabs Nets, Groups and Classes. Each row holds a colour square, the net,
    the role with its current ("power 4 A"), a confidence badge (high, med) and a confirmed tick or a "?".
  - A **Groups** section: `hot_SW · C1 Q1 Q2`, `gate_Q1 · U1→Q1`, `kelvin_R12 · R12→U3`, each with a
    confidence badge.
  - A **Layers** section: F.Cu, B.Cu, F.Silkscreen and Edge.Cuts, plus the overlay layers "Loop areas" and
    "Corridors", each with a visibility eye.
- **Canvas.**
  - A black background with a dot grid, in KiCad-like layer colours, with a yellow outline.
  - The switch node is highlighted in orange and the rest dimmed.
  - The hot loop is drawn hatched, with a label "hot_SW 41.2 mm² / bound 30.1 · ratio 1.37 ✓".
  - A dimension "9.00 mm", a crosshair with a coordinate box "x 24.00 y 14.50", a red finding marker on a
    track, and a hatched green corridor under U3.
- **Right dock: the Properties panel**, with the tabs Net, Role and Measures:
  - Net SW, class Default;
  - role `switch_node` as a drop-down, origin "inferred · rule SW-1", evidence "Q1.S + Q2.D + L1.1",
    confidence high, confirmed 2026-10-29, current 3.0 A, working V 12 V;
  - a **Measures** section headed "c0213 · c0204": copper area, narrowest, distance to sensitive copper,
    under sensitive copper, vias;
  - a **Limits** section headed "profile": distance 1.00 mm (default), loop ratio 2.0 (default), and an
    override link "edit in rules.json…";
  - a **Router** section headed "phases": 0 Roles & checks done, 2 Critical routes 2 of 3, 1 Power copper
    1 finding, 4 Propose & lock not run.
- **Layer tabs** under the canvas, in Altium's manner: LS, F.Cu, B.Cu, F.Silkscreen, F.Mask, Edge.Cuts,
  Loops, Corridors, and "Snap: Grid + Pads" on the right.
- **Messages panel** headed "Messages — roles.rules · DRC", with the counts "3 errors · 2 warnings · 4
  info". Its columns are severity, code, object, message, source and layer, for example `roles.width-current`
  · VOUT · "track 0.30 mm carries 3 A; needs 1.14 mm (15 mil/A)" · S-0851 · default · F.Cu.
- **Status bar**: "x 24.00 mm y 14.50 mm", "dx 9.00 dy 0.00", "Grid 0.5 mm", "Net SW · switch_node",
  "Layer F.Cu" and, on the right, "KiCad 10.0.6 · evidence KICAD-VERIFIED".

The mock-up has a fault that this design corrects. Its status bar shows `KICAD-VERIFIED` while the screen
holds role findings, which are `INFERRED` (c0222, "Role evidence"). Decision 9 makes the status bar show the
lowest evidence level on screen, the lowest-wins rule of `AGENTS.md`.

### Net roles and the router phases

- **c0222 (phase 0, archived on `dev`)** gives each net a role: `power`, `switch_node`, `ground`, `kelvin`,
  `gate`, `high_voltage` or `signal`.
  - Roles are inferred from the circuit, then confirmed or declared. Groups are hot loops, gate loops and
    Kelvin pairs.
  - The measures come from the analyses, and the limits come from the role profile, with overrides.
  - The findings are `roles.*`, and the stage is `roles.rules`. Writes go through `fenolite roles --accept
    | --accept-all | --set | --reject | --accept-group | --reject-group | --current`, with the plan
    protocol, to `<stem>.roles.json` or `.fenolite/rules.json`.
- **c0243 (phase 1, branch `c0243-role-copper`)** writes power, switch-node and ground copper, via arrays,
  high-voltage keep-outs and corridors. The corridors are rule areas named `role.corridor.<group>`.
- **c0244 (phase 2, branch `c0244-critical-routes`)** routes the critical groups with locked copper and
  corridors named `role-corridor:<group>:<net>`. It returns `result.roles` with statuses, reasons and
  proposals, each proposal with its command.
- **Run order:** 0 → 2 → 1 → 4 → 3.
- **The corridor name is settled** (2026-10-29, task 0.1): `role.corridor.<group>.<net>` for both c0243 and
  c0244. The viewer matches the prefix `role.corridor.`.

## Goals / Non-Goals

**Goals**

- An engineer who uses Altium or KiCad recognises a CAD workbench at first sight and finds the expected
  panel, key and status field.
- Measurable advantages over both tools (decision 9) that a test proves.
- A Net Roles workspace where roles are reviewed, confirmed and undone without a command line, and never
  written without a reviewed plan.
- The same single offline page, both served and exported, and no runtime dependency.

**Non-Goals**

- Geometry editing, interactive routing, a schematic editor.
- Copying vendor artwork, colour files, layout files or code.
- Replacing `--serve` with a native application.

## Decisions

### 1. Technology: keep the page, rebuild it as a workbench

| option | what it gives | cost and consequences |
|---|---|---|
| **A. The current stack as a desktop-style workbench** (recommended) | Menus, docking, keymaps and a status bar drawn by the page. In served mode, the server also offers a web app manifest with `display: standalone`, so Chromium and Edge can install `http://127.0.0.1:<port>/` as an app window with no address bar (S-0929; a loopback origin is a secure context, S-0930) | No new dependency. The renderer, the export, the SVG recorder and the visual tests all stay. Limits: menus are drawn inside the page, not native; the browser keeps a few keys (decision 5); an exported page opens in a browser tab |
| **B. A native window over the same page**, optional extra `view-app` (pywebview, BSD, S-0931): `fenolite view --serve --window` | A real OS window with a title bar and no browser, and a JS-to-Python bridge | An extra imported lazily, as `AGENTS.md` requires. The platform engines differ (WebView2, WebKit, WebKitGTK), so WebGL and fonts vary, and the visual tests still run in Chromium only. Phase 11 is cut first |
| **C. A desktop toolkit**: Qt for Python (LGPLv3 or commercial, with some modules GPL-only, S-0932), Tk (permissive, S-0933, in the standard library but missing from some Linux Pythons), Electron or Tauri | A native look | A second renderer for 2D, 3D, sheets, drawings and SVG. It loses the one-file export that reviewers send by mail, and loses the visual-test harness. Qt would have to be an extra; its LGPL obligations (relinking, notices) and GPL-only modules need a licence review for every user who builds a distribution. Tk's canvas has no GPU path for the 10⁴ to 10⁵ primitives of a board. Electron and Tauri add a Node or Rust toolchain. Rejected |

Option A is the recommendation. An engineering look comes from the frame, density, behaviour and keys,
not from the widget toolkit. Option A keeps every working feature and the export. Option B stays open as an
optional phase if the maintainer wants a real OS window.

### 2. Scope: view, review and light role editing

| option | contents | verdict |
|---|---|---|
| view and review only | today's scope in the new frame | too little: the maintainer's workspace confirms roles |
| **light editing through existing commands** (recommended) | Role writes through `fenolite roles` (confirm, set, reject, forget, groups, currents), each as a reviewed plan. Once c0244 lands, a proposed critical route is applied through `fenolite route --roles critical` | each write is a command an agent can also run, with the same plan and receipt |
| full editing | moving parts, routing, drawing | duplicates Altium and KiCad, bypasses the scripts, and has no plan protocol |

Light editing is allowed only with `--serve --edit`. It is never allowed in an exported page, and never
without `--edit`, so an agent running `view --serve` cannot enable writes by accident. Lock and unlock are
out of scope because no command exists (open question 5).

### 3. Rollout: a thin shell for all documents, then Net Roles, then the rest

| option | verdict |
|---|---|
| Net Roles workspace only, the rest left in the old frame | two looks in one page, and two layouts to keep working in narrow windows |
| everything at once | 50+ design-days with no intermediate delivery and every baseline changing at the end |
| **shell first, for every document; Net Roles second; the other workspaces deepened third** (recommended) | Phase 2 wraps today's panels in docked panels unchanged, so that one review rebaselines the eight references. Phase 7 builds the new workspace on a tested shell, and phase 10 moves the other workspaces onto the Messages panel and the shared selection |

There is no `--ui classic` switch: one interface, one set of baselines.

### 4. Docking and layout persistence

- **Docks.** Left, right and bottom docks, each a stack of panel groups. A group has tabs and a blue title
  bar with pin (collapse to an edge button) and close. Splitters are draggable and keyboard-operable (the APG
  window splitter pattern, S-0926).
  - A panel is dragged to another dock or group by its title bar, with drop targets shown, or moved with
    the panel menu (keyboard and single-pointer alternative to dragging, WCAG 2.5.7, S-0925).
  - Altium's panels have docked, popup and floating modes and save layouts (S-0922). KiCad docks its
    Properties panel (S-0920). The workbench offers docked and pinned modes, and floating windows in served
    mode.
- **Floating windows (served mode).** Window ▸ Float opens the panel in its own browser window, at `/panel/<name>`
  of the same server. The windows share the selection through `BroadcastChannel`, the same way tabs share it
  today. The panel returns to its dock when its window closes. Exported pages have no floating windows.
- **Layout document.** `fenolite.view_layout.v0` is canonical JSON with the docks, groups, panel order,
  sizes in CSS pixels, collapsed and closed panels, per workspace (board, sheet, library, drawing, table,
  roles).
  - Default: stored in the browser per workspace (`localStorage`, guarded as today).
  - Window ▸ Save Layout As downloads the file, and `--layout FILE` opens with it. A bad file is `FEN-3004`
    and the page opens with the default layout.
  - Window ▸ Reset Layout restores the built-in default.
  - The server never writes a layout file.
- **Narrow windows** (760 pixels or below, c0233). The docks collapse into one drawer that the Panels button
  toggles. The canvas keeps the width, and Escape closes the drawer.

### 5. Keymaps

- **Built-in keymaps.**
  - `fenolite` (default): today's keys unchanged (`M`, `Shift+M`, `Q`, `B`, `D`, `E`, `F`, `N`, `X`,
    `Shift+S`, `Shift+C`, `+`, `-`, PgUp, PgDn, Esc), plus the new commands.
  - `altium`: the same keys plus menu accelerator sequences, a key per menu level, which Altium documents
    and lets users customise (S-0921): `V`,`F` fit board, `V`,`D` fit document, `X`,`A` deselect all,
    `T`,`M` reset error markers. Sequences time out after 1.5 s and show the pending prefix in the status
    bar.
  - `kicad`: KiCad's documented habits (S-0920): `` ` `` highlights the net under the cursor, `~` clears the
    highlight, `N` and `Shift+N` cycle the grid, `Alt+1` and `Alt+2` choose the fast grids.

  A binding not in S-0920 or S-0921 is Fenolite's choice and is labelled so in the Keyboard panel.
- **Customising.**
  - `fenolite.view_keymap.v0` is a JSON file of `command → [keys]` over a base keymap, read with
    `--keymap NAME|FILE`.
  - The Keyboard panel (Tools ▸ Preferences ▸ Keyboard) edits the keymap in place, shows conflicts, saves
    to the browser and downloads the file.
  - KiCad keeps hotkeys in a `user.hotkeys` file (S-0920). The two formats are not compatible, and no
    importer is offered (open question 6).
- **Reserved keys.** A keymap may not bind keys that a supported browser keeps in a tab: `Ctrl+W`, `Ctrl+T`,
  `Ctrl+N`, `Ctrl+L`, `Ctrl+Tab`, `F5`, `F11` and `F12`, among others. Task 4.1 records the list from the
  pinned Chromium and checks it on the other browsers. Such a binding is refused with a message.
- **Command registry.** Every command has an id (`view.fit-board`, `roles.confirm`), a label, a menu place
  and its keys. Menus, the toolbar, the command search and the Keyboard panel are generated from the
  registry, so a command cannot exist without a keyboard path.
- **Focus rules.** c0233's rules stay: no shortcut runs in a form field, during composition, or after
  default prevention. Ctrl, Meta and Alt combinations run only when the active keymap binds them.

### 6. Themes

- **Workbench chrome.**
  - `dark` (default): neutral greys, a blue panel title bar, square 2-pixel controls and 22-pixel rows. The
    density comes from the mock-up.
  - `light`: for daylight and screen sharing.
  - `contrast`: high contrast.

  The choice is made in View ▸ Theme and kept in the browser. `prefers-color-scheme` decides the first
  visit.
- **Document palettes are unchanged** (c0178):
  - KiCad documents keep Fenolite's KiCad-manner palette, or the user's `--theme`, and Altium documents keep
    the Altium-manner palette;
  - the canvas background follows the document palette, not the chrome theme;
  - the light chrome theme pairs with the light variant of each document palette, which task 5.2 authors
    (Fenolite's own values, no vendor colour file).
- **Role palette.** Seven role colours chosen for Fenolite, tested for separation under simulated protan,
  deutan and tritan vision. The test uses the severity-1.0 model of S-0928 (`H-G-WB-CVD`) and the advice
  of S-0927.
  - Every role also shows a glyph and its name (`P` power, `SW` switch node, `G` ground, `K` kelvin, `GT`
    gate, `HV` high voltage, `S` signal). Its overlays use line style and hatch direction as well as colour,
    so colour is never the only cue (WCAG 1.4.1, S-0925).
  - A `cvd` variant raises the hatch weight for colour-blind users.
- **Contrast.** Chrome text is at least 4.5:1 and non-text controls at least 3:1 against their background
  (WCAG 1.4.3 and 1.4.11, S-0925). A unit test checks the theme tokens (`H-G-WB-CONTRAST`).

### 7. Performance targets

- **Stress fixture.** `tests/visual/fixtures/stress_board.py` builds the board deterministically, authored
  for Fenolite: 4 layers, 160 × 100 mm, 2 000 pads, 10 000 tracks, 1 500 vias and 40 zone fills. That is
  about 1.2 times the largest public board of the corpus (8 355 tracks, `docs/viewer.md`, "Speed and size").
- **Budgets**, measured in the CI viewer job with Chromium's software rendering and on the maintainer's PC.

  | measure | CI budget | reference PC target | hypothesis |
  |---|---|---|---|
  | pan or zoom frame, p95 over 120 frames | ≤ 50 ms | ≤ 16.7 ms (60 Hz) | `H-G-WB-FRAME` |
  | crosshair move, p95 | ≤ 4 ms, with no board redraw | ≤ 2 ms | `H-G-WB-CURSOR` |
  | exported page, open to first full draw | ≤ 2.5 s | ≤ 1 s | `H-G-WB-OPEN` |
  | click on a Messages row to its framed copper | ≤ 100 ms | ≤ 50 ms | `H-G-WB-FRAME` |

  Task 0.2 first measures the current page on the fixture. If the current page already misses a CI budget,
  the budget becomes "no worse than today and 30 % better at phase 6", recorded under the task.
- **How the budgets are met:**
  - an overlay canvas for the crosshair, hover, rubber band and measure line;
  - a cached bitmap per visible layer, redrawn only when the view or the layer changes, and composited
    while panning;
  - a uniform grid spatial index for hit testing;
  - redraws limited to one per animation frame.

### 8. Accessibility

- **Keyboard and focus.** Every command is reachable from the keyboard (registry, decision 5). The menu
  bar follows the APG menubar pattern, panels and tabs the tabs pattern, and the role and Messages tables
  the grid pattern (S-0926). Focus is always visible and never hidden under a panel (WCAG 2.4.7, 2.4.11).
- **Pointer alternatives.** Dragging (docking, splitters, panning) has a single-pointer or keyboard
  alternative (WCAG 2.5.7).
- **Colour.** Colour is never the only cue (decision 6).
- **Screen readers.** The canvas has a text alternative: the selection and its properties are announced
  through a live region, and the Messages panel is a real table.
- **Target.** WCAG 2.2 AA (S-0925) for the chrome. The drawing itself is graphics with text alternatives.
  The test runs a check of Fenolite's own in Playwright (focus order, roles, names, contrast tokens). axe-core
  is not added.

### 9. What "better than Altium and KiCad" means, measurably

Each criterion has a test. The comparison is with what the tools' public documentation describes (S-0920
to S-0924), not with private measurements.

| # | criterion | proof |
|---|---|---|
| M1 | **Every number carries its source and evidence.** Every value in Properties, Measures, Limits and Messages, and on-canvas measure labels, carries a source (analysis, S-id, hypothesis, rule name, `default` or `override`) and an evidence level, shown on hover and on the line | `tests/visual/test_workbench.py -k provenance`: every `[data-value]` element has non-empty `data-source` and `data-evidence`, with zero exceptions |
| M2 | **Findings link both ways.** Altium's Messages panel cross-probes from a message to its object (S-0924). Here a click on a row frames the copper and makes its layer current, a click on a marker selects and scrolls to the row, and the Messages row is linked to the Properties panel | `-k linked`: both directions, on 3 authored findings, same selection hash |
| M3 | **One selection model** across the canvas, the Nets, Groups, Properties and Messages panels, the layer tabs, the status bar and the address | `-k selection`: the same net selected from 5 entry points gives one state hash, and `Esc` clears it everywhere |
| M4 | **No modal dialog for routine actions:** no `alert`, `confirm`, `prompt` or modal `<dialog>` for selecting, filtering, measuring, confirming a role, applying a plan or undoing. Print keeps the browser's own dialog | `tests/unit/view/test_ui_sources.py -k modal` over the UI sources, and `-k pending` in Playwright |
| M5 | **Responsive at the target size** (decision 7) | `-k budget`: `H-G-WB-FRAME`, `H-G-WB-CURSOR`, `H-G-WB-OPEN` |
| M6 | **Undo for every write the viewer makes** (decision 11) | `tests/unit/view/test_role_writes.py -k undo`: each of the 9 write kinds has an inverse plan that restores the document bytes (the canonical empty role set when the write created the file) |
| M7 | **Stable screenshots:** two renders of one fixture give identical PNG bytes, and the references hold at 0.1 % | `tests/visual/test_screens.py -k deterministic` (`H-G-WB-STABLE`) |
| M8 | **Honest evidence in the status bar:** the lowest evidence level of what is on screen, by `AGENTS.md`'s lowest-wins rule | `-k evidence`: a KiCad board with role findings shows `INFERRED` |
| M9 | **Every command has a keyboard path** | `tests/unit/view/test_ui_sources.py -k registry`: every registry command has a menu place, and every menu entry a registry id |
| M10 | **A layout survives:** a reload restores the layout exactly, and Reset restores the default | `-k layout` |
| M11 | **Explained codes:** every Messages row shows its `fenolite explain` text on demand, without leaving the page | `-k explain` |

### 10. The Net Roles workspace

Opened with `--workspace roles`, Window ▸ Workspace ▸ Net Roles, or the Roles menu. It applies to a board
whose project has roles (any KiCad or Altium board: inferred roles exist without a stored document).

- **Data.**
  - `fenolite.view.roles.roles_payload(path, *, roles_file)` runs `fenolite roles PATH --check --json` in
    process, read-only, through `fenolite.api`. It joins the reply to scene geometry: net to primitives,
    group to loop polygon, measure to the copper it read, finding to position.
  - The payload is `fenolite.view_roles.v0`, served at `/roles/<id>.json`, cached by the board's,
    role document's and code's SHA-256, and embedded in an export with `--workspace roles`.
  - The payload uses the command's own reply, so the numbers on screen are the numbers an agent reads.
- **Net Roles panel** (left), with three tabs:
  - **Nets:** colour square, glyph, net, role and current, confidence badge, and state: confirmed ✓,
    declared ◆, inferred ?, rejected ✕. Columns sort, the text filter works, and a multiple selection
    applies one action to all.
  - **Groups:** hot loops ⟲, gate loops ⟲ and Kelvin pairs ⇉, with their parts, confidence and state.
  - **Classes:** the part classes c0222 used (switch, shunt, driver, inductor, connector).
- **Layers panel** (left): the board layers with eye, colour and opacity, and the overlay layers:
  - **Loop areas**, hatched with their area and bound;
  - **Corridors**, the rule areas whose name has the settled corridor prefix;
  - **Locked copper**, an outline with a lock glyph;
  - **Measures**, dimension lines on the copper;
  - **Role copper**, the zones c0243 wrote, by role.
- **Properties panel** (right), with three tabs:
  - **Net:** name, class, pads, routed length.
  - **Role:** kind (a drop-down when editing is on), origin (inferred with its rule id, declared,
    confirmed), evidence pads, confidence, confirmation date, current, working voltage.
  - **Measures:**
    - every measure with its value, its analysis (`shapes.loop_areas`, `power.analyze_power`, …) and the
      copper state it read (`saved_fill`, `simulated`, `outline`, `tracks`);
    - every limit with its value and its source: profile default with S-id or hypothesis, or override with
      the file and key;
    - the router phases (decision 12).
- **Canvas.**
  - Selecting a net or group highlights its copper and dims the rest (Dim, Mask or Normal, as c0187).
  - The measures are drawn on the copper: loop polygon and bound, area and ratio label, narrowest width
    with a dimension, distance to sensitive copper with a dimension line.
  - Finding markers sit at the positions of the `roles.*` findings.
- **Messages panel** (bottom): the `roles.rules` findings with severity, code, object, message, source and
  layer, filterable and linked (M2).
- **Toolbar:** a Roles view drop-down (role colours, confidence, confirmation state), a Net drop-down, Grid
  and unit, and the role actions when editing is on.

### 11. Role writes: the plan protocol in the page

- **Gate.** Writes are possible only in served mode with `--edit`. Otherwise the action buttons are replaced
  by Copy command, which copies the exact `fenolite roles … --dry-run --json` line.
- **Actions and the commands they run.**

  | action | command |
  |---|---|
  | confirm a role | `--accept NET` |
  | confirm all at a confidence | `--accept-all --min-confidence high` |
  | set a role | `--set NET=KIND[:working_mv=N]` |
  | reject a role | `--reject NET` |
  | forget a role | `--forget NET` |
  | set a current | `--current NET=AMPS` |
  | confirm a group | `--accept-group NAME` |
  | reject a group | `--reject-group NAME` |
  | forget a group | `--forget-group NAME` |
- **Flow.**
  1. The page `POST`s the action to `/roles/plan`, with the review header.
  2. The server runs the command with `--dry-run` and returns `result.plan`, `plan_id`, the roles as they
     will be stored, and the findings before and after.
  3. The **Pending** panel (bottom dock, non-modal) shows the plan: the file, the old and new role per net,
     and the change in findings.
  4. Apply, or Enter in the panel, `POST`s `/roles/confirm` with the `plan_id`. The server runs `--confirm
     --plan <plan_id>` and returns the receipt.
  5. Discard drops the plan. `FEN-4002` (an input changed) is shown in the panel with Review again.
- **No write behind the user's back:**
  - every write follows an Apply on a visible plan;
  - the server holds at most one pending plan per page;
  - it refuses a confirm whose plan it did not stage;
  - it logs each receipt in the Messages panel (source `fenolite roles`, SHA-256 of the file).
- **Undo and redo.**
  - Each receipt pushes an entry with its inverse action, computed from the dry-run reply. For example, an
    accept is undone by a forget, a set over a confirmed role by a set back to it, and a current by the
    previous current or a forget.
  - Ctrl+Z stages the inverse plan. If its target's SHA-256 still equals the receipt's, the inverse is
    applied immediately: the user asked for exactly that change and nothing else has changed. Otherwise the
    plan stops in Pending for review.
  - Ctrl+Y (or Ctrl+Shift+Z) redoes. The history is kept per page and lost on reload, which the Edit menu
    says.
- **Why `--forget` is new.** c0222 has no way back from a confirmed role to an inferred one: `--reject`
  stores a confirmed `signal`. `--forget NET` removes the stored confirmation (role and current) and
  `--forget-group NAME` removes a stored group decision. Both use the same plan protocol and write only the
  role document. A declared role (from a script) cannot be forgotten: `FEN-2001` names the script to
  change, nothing is written, and no `roles.*` code is added (c0243 and c0244 already extend that table).

### 12. Phase results and the router phase status

- **Status per phase.** The Router section of Properties and the Window ▸ Router Phases panel list the
  phases in run order 0 → 2 → 1 → 4 → 3, each with a state of not run, done, partial (n of m), findings
  (k) or failed:
  - **Phase 0** comes from the live `roles --check` reply.
  - **Phases 2 and 1** come from recorded replies passed with `--report FILE`: a `route --roles critical`
    reply and a `copper` reply, accepted only once c0244 and c0243 are merged. They are bound to the
    board's SHA-256 as c0239 binds reports. A stale reply is shown Limited.
  - **Phases 4 and 3** show not available until their changes exist.
- **On the canvas.**
  - Corridors are drawn green and hatched, with their group name.
  - Locked role copper has its outline and a lock glyph.
  - Role copper zones are tinted by role.
  - A critical route that c0244 proposes but did not write (its `proposals`) is drawn dashed with its
    reason, and its command is in Properties.
- **Accepting a proposal** (with `--edit`, after c0244 lands) runs the proposal's own command (`fenolite
  route … --roles critical --group G`) through the same Pending flow and undo. Its inverse is the receipt's
  prior bytes through `route --rip` limited to the group, as c0244 defines. If c0244 does not provide an
  exact inverse, accepting a proposal is left out (cut order).
- **Lock and unlock** are shown, not changed (open question 5).

### 13. The UI sources and the single page

- `page.html` is split into `src/fenolite/view/ui/`:
  - `base.css` and `themes.css`;
  - `shell/` (menu, toolbar, docks, status, keymap, registry, selection);
  - `canvas/` (2D, overlay, 3D, SVG recorder);
  - `panels/` (one file per panel);
  - `workspaces/` (board, sheet, library, drawing, table, roles).
- `fenolite.view.export.page()` concatenates them in a fixed order into the same one file, with no URL and
  no framework.
- Phase 1's first step proves that the assembled page equals today's `page.html` byte for byte, before any
  change.
- The served page and the exported page come from the same assembly.

### 14. Icons and artwork

- The toolbar icons are 16-pixel SVG paths drawn for Fenolite, kept in `ui/icons.js`, with a tooltip and a
  keyboard label for each.
- No icon, bitmap, colour file or layout file of Altium or KiCad is used.
- The layer colours of the KiCad-manner palette are c0178's own values.

### 15. Command line

- `fenolite view`:
  - `--workspace board|roles` opens a workspace (sheets, libraries and drawings choose theirs by document);
  - `--keymap fenolite|altium|kicad|FILE`;
  - `--layout FILE`;
  - `--roles FILE` (the role document, as for `fenolite roles`);
  - `--edit` (with `--serve` only: allows the role writes of decision 11).

  `--edit` without `--serve` is `FEN-2001`. `--workspace roles` on a document that is not a board is
  `FEN-2001`. The JSON reply of `view --workspace roles --json` adds `result.roles`: the payload summary
  with role counts by state and the findings by severity.
- `fenolite roles`: `--forget NET[,NET]` and `--forget-group NAME`, repeatable.
- Phase 11 only, if it is not cut: `fenolite view --serve --window` opens the served page in a native window
  through the `view-app` extra. Without the extra the reply is exit 6 with its install hint.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| `H-G-WB-FRAME` | With layer bitmaps and the spatial index, pan and zoom of the stress board stay within the frame budget | `tests/visual/test_workbench.py -k budget` | p95 ≤ 50 ms over 120 frames in the CI viewer job, and ≤ 100 ms from a Messages click to the framed view; the reference PC figure recorded under task 6.4 |
| `H-G-WB-CURSOR` | The overlay canvas makes a crosshair move independent of the board | `tests/visual/test_workbench.py -k budget` | p95 ≤ 4 ms in CI, and zero board-layer redraws counted during 200 pointer moves |
| `H-G-WB-OPEN` | The exported stress page opens to its first full draw within budget | `tests/visual/test_workbench.py -k budget` | ≤ 2.5 s in CI from navigation start to the first full draw mark |
| `H-G-WB-STABLE` | The workbench renders deterministically in the pinned Chromium and fonts | `tests/visual/test_screens.py -k deterministic` | two renders of every fixture give identical PNG bytes |
| `H-G-WB-CONTRAST` | The theme tokens meet WCAG 2.2 AA contrast | `tests/unit/view/test_themes.py -k contrast` | text tokens ≥ 4.5:1 and control tokens ≥ 3:1 against their backgrounds, in dark, light and contrast |
| `H-G-WB-CVD` | The seven role colours stay apart under simulated colour-vision deficiency | `tests/unit/view/test_themes.py -k cvd` | pairwise CIEDE2000 ≥ 12 between the role colours on the dark and light canvas, under the S-0928 protan, deutan and tritan simulation at severity 1.0 |

## Evidence level per behaviour

| behaviour | level |
|---|---|
| workbench frame, docking, keymaps, themes (Fenolite's own interface) | not a format fact. Proved by the tests of decision 9 |
| key bindings said to follow Altium or KiCad | `INFERRED` from S-0920 and S-0921, with each binding traced to its source line in `docs/viewer.md` |
| role values, measures, limits, findings | as c0222 replies: `INFERRED` |
| frame budgets and colour separation | the hypotheses above, until measured |
| phase 1 and 2 overlays | the evidence of the recorded reply |

## Size and cut order

| phase | contents | design-days |
|---|---|---|
| 0 | Entry check; frame measurement of today's page on the stress fixture; reserved-key list; corridor-name reconciliation | 1.5 |
| 1 | UI source split, with a byte-identical assembly proof | 3 |
| 2 | Shell: title, menus (registry), toolbar, docks with tabs and splitters, status bar, layout persistence, narrow drawer, existing panels wrapped; one rebaseline | 8 |
| 3 | One selection store; Messages panel linked both ways; provenance attributes; status-bar evidence | 4 |
| 4 | Keymaps `fenolite`, `altium` and `kicad`, sequences, keymap file, Keyboard panel | 3 |
| 5 | Themes dark, light and contrast; role palette and glyphs; contrast and colour-blind tests | 2.5 |
| 6 | Performance: overlay canvas, layer bitmaps, spatial index, budget harness | 5 |
| 7 | Net Roles workspace, read-only: payload, panels, overlays, measures on copper | 7 |
| 8 | Role writes: `--edit`, server routes, Pending panel, undo and redo, `roles --forget` | 5 |
| 9 | Router phase status and phase overlays; proposal acceptance (gated on c0243 and c0244) | 4 |
| 10 | Other workspaces deepened onto the shell: sheets, libraries, drawings, BOM and output jobs, compare, project review | 6 |
| 11 | Optional native window, extra `view-app` | 3 |
| 12 | Baselines, docs, agent guide, evidence, residue, closing | 3 |
| | **total** | **55** |

**Cut order**, first cut first:

1. phase 11 (native window);
2. phase 10 (the other workspaces stay as wrapped panels);
3. proposal acceptance of phase 9 (the overlays and the status stay);
4. the `kicad` keymap and the Keyboard panel's editing (keymap files stay);
5. floating windows;
6. the layer bitmap cache, if the overlay canvas alone meets the CI budget;
7. the light theme (dark and contrast stay).

**Never cut:** phases 0 to 3, the role palette and glyphs, phase 7, phase 8 with undo, and phase 12.

## Risks / Trade-offs

- **"Still a browser."** Option A keeps a browser engine, and some users may notice browser behaviour
  (reserved keys, the tab bar when the app is not installed). Mitigations:
  - the standalone app window (S-0929);
  - the reserved-key refusal with a message;
  - option B as a later extra.
- **Baseline churn.** Phase 2 changes all eight references at once. The mitigation is one reviewed
  rebaseline with difference images attached to the pull request, and phase 1's byte-identical proof
  before it.
- **The size of the page.** More interface means more bytes. Target: the assembled page grows by at most
  120 KB uncompressed, which task 12.1 measures. Scenes stay gzipped.
- **Writes from a page.** A page that triggers writes is a new surface. Mitigations:
  - the gate is `--serve --edit`, on the loopback address only;
  - the server checks the review header (no preflight is answered);
  - one staged plan per page;
  - confirm only for a staged plan;
  - receipts are logged on screen.
- **Interface drift with c0243 and c0244.** Names (corridor prefix, reply fields) may still change. Task 0.1
  reconciles them, and phase 9 starts only after they merge.
- **Performance on WebKitGTK** (option B). It is not covered by CI, and is documented as best effort.
- **Clean-room.** The look must recall CAD programs without copying them. Every convention that is relied
  on is cited (S-0920 to S-0924), and icons and palettes are authored.

## Open Questions

**Decided on 2026-10-29.** The maintainer approved this change and accepted every recommended answer
below; each question now reads as a decision. The corridor name is settled for c0243 and c0244 as
`role.corridor.<group>.<net>`, and the viewer matches the prefix `role.corridor.`.

1. **Technology.** Option A (current stack as a workbench) with the native window as an optional later
   extra? **Decided: yes**, A now and B cut first.
2. **Default keymap.** Keep `fenolite` (today's keys, already close to Altium for `Q`, `Shift+S`, `+` and
   `-`, and `Shift+C`) as the default, or default to `altium`? **Decided: `fenolite`**, with `altium`
   and `kicad` one option away.
3. **Rollout.** Shell for every document first, then Net Roles? **Decided: yes** (decision 3).
4. **Undo without review.** May Ctrl+Z apply the exact inverse immediately when the file is unchanged since
   the receipt? **Decided: yes.** Any other case stops in Pending.
5. **Lock and unlock.** No command exists. Should a later change add `fenolite lock` under the plan protocol,
   for the viewer to call? **Decided: yes, as a separate change after c0244**, so that this one does
   not grow.
6. **KiCad hotkey import.** Read KiCad's `user.hotkeys` into a keymap? **Decided: no** until its format
   is documented in `docs/formats/kicad/` from a public source. Keymap files cover the need.
7. **The CVD simulation data.** The colour-blind test uses the severity-1.0 matrices published in S-0928
   (three 3 × 3 tables of numbers). **Decided:** record them as published facts with the S-id. If the
   maintainer prefers, derive them from the model the paper describes instead.
8. **The light theme in exported pages.** Should an exported page follow the reader's `prefers-color-scheme`
   or keep the sender's theme? **Decided: the reader's.**
