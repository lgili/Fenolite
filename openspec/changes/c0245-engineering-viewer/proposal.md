## Why

The users of Fenolite are engineers who work in Altium Designer and KiCad every day. On 2026-10-29 the
maintainer reported that `fenolite view` reads to them as a web page, and that this makes them uneasy. He
asked for the look and the behaviour of an engineering program, taking the good parts of Altium and of KiCad,
and for a quality above both. He approved a mock-up as the direction (described in `design.md`, "The
maintainer's mock-up").

The viewer already draws boards, sheets, libraries, Draftsman drawings, BOMs, output jobs, comparisons and
check findings (c0176 to c0193, c0233, c0235, c0239). What it lacks is the frame around the drawing:

- **No window frame.** The page is one 40-pixel toolbar of buttons, a fixed 260-pixel sidebar of stacked
  sections, layer tabs and a one-line status. It has no menu bar, no dockable or tabbed panels, no saved
  layout, no Messages table, no crosshair and no status fields.
- **Fixed keys.** The shortcuts are hard-coded in one handler, with no keymap and no way to change them.
- **Panels that do not talk to each other.** The selection is held separately by the canvas, the filter,
  the findings list and the review panel.
- **No net roles.** c0222 gives every net a role and judges the copper against it. Phases 1 and 2 (c0243,
  c0244) will write role copper, locked critical routes and corridors. The viewer shows none of this, and
  confirming a role still takes a command line.
- **One file of 187 KB.** `page.html` holds every style and script, which makes a larger interface hard to
  build and to review.

## What Changes

- **Approach.** The current rendering stack is kept: one offline HTML page, canvas 2D and WebGL, served on
  the loopback address, or exported as one file. It is rebuilt as a desktop-style workbench, with no new
  runtime dependency. A native window through an optional extra is a later, cuttable phase. A desktop
  toolkit (Qt, Tk, Electron) is rejected, for the reasons in `design.md`, decision 1.
- **Workbench shell.** Every document kind gets the same frame:
  - a title line with the document and its state;
  - a menu bar (File, Edit, View, Place, Design, Roles, Route, Tools, Reports, Window, Help) whose entries
    show their keys, with keyboard navigation;
  - an icon toolbar with grid, unit, view and net drop-downs;
  - left, right and bottom docks holding tabbed panels with title bars, splitters and close and pin
    buttons;
  - the canvas with a dot grid and a crosshair;
  - layer tabs under the canvas;
  - a Messages panel;
  - a status bar with x/y, dx/dy, grid, net and role, current layer, tool version and evidence level.
- **Layouts.** Named layouts per workspace are kept in the browser. Window ▸ Reset Layout restores the
  default. A layout file can be saved and read with `--layout FILE`. In served mode a panel can float into
  its own window, for example on a second monitor.
- **Keymaps.** There are three built-in keymaps:
  - `fenolite`, today's keys, the default;
  - `altium`, with accelerator sequences such as `V`,`F`;
  - `kicad`.

  A keymap file can be read with `--keymap NAME|FILE`, and there is an in-page Keyboard preferences panel.
  Keys that a browser reserves are refused.
- **Themes.**
  - The workbench is dark by default. A light and a high-contrast variant are available.
  - Each document keeps its tool's palette (c0178).
  - Role colours come from a palette that is safe for colour-blind users, and every role always shows a
    glyph and its name as well, so colour is never the only cue.
- **One selection model.** The canvas, every panel, the layer tabs, the Messages panel, the status bar and
  the address of the page read and write one selection.
- **Linked messages.** Every finding with a position has a marker on the canvas. A click on the message
  frames its copper, and a click on the marker selects the message.
- **Provenance on screen.** Every number in Properties, Measures, Limits and Messages names its source:
  analysis, S-id, hypothesis, rule or override, and its evidence level.
- **Frame budget.** Pan and zoom meet a measured frame budget on an authored stress board. Moving the
  crosshair never redraws the board.
- **Net Roles workspace** (`--workspace roles`), the first workspace built on the shell:
  - **Net Roles panel** with the tabs Nets, Groups and Classes;
  - **Layers panel** with the overlays Loop areas, Corridors, Locked copper and Measures;
  - **Properties panel** with the tabs Net, Role and Measures: the role, its origin rule, evidence,
    confidence, confirmation, current and working voltage; every measure with its analysis; every limit
    with its source and override; the status of the router phases;
  - **role highlight** that dims the rest of the board, with the measures drawn on the copper;
  - **Messages panel** holding the `roles.*` findings.
- **Writes only through the existing protocol, and only when asked.**
  - With `--serve --edit`, the workspace can confirm, set, reject or forget roles and groups, and set
    currents.
  - Each action runs `fenolite roles … --dry-run`. The plan is shown in a docked Pending panel, and
    nothing is written until the user applies it, which runs `--confirm --plan <plan_id>`.
  - Every write can be undone, and the undo is itself a planned write.
  - Without `--edit`, and in an exported page, the workspace is read-only and offers the command line to
    copy.
- **`fenolite roles --forget NET` and `--forget-group NAME`.** These are new options that drop a stored
  confirmation, so that undo has an exact inverse. They use the same plan protocol.
- **Phase results** (when c0243 and c0244 land):
  - the corridors, the locked critical copper and the power copper are drawn as overlays;
  - their replies are read with `--report`, and the router phase panel lists phases 0, 2, 1, 4 and 3 in
    run order;
  - a proposed critical route is applied only through `fenolite route … --roles critical` under the same
    plan protocol.
- **Source split.** The page is assembled from `src/fenolite/view/ui/` into the same single file, with no
  URL, no framework and no build tool beyond Python.
- **Visual tests.** New baselines, authored for Fenolite, cover the workbench, the Net Roles workspace, the
  light theme, the colour-blind palette, the narrow window and the linked messages. A determinism check
  renders twice and expects identical bytes.

## Capabilities

### New Capabilities

- `roles-workspace`: the Net Roles workspace of the viewer. It covers the panels, the overlays, the role
  writes through the plan protocol, undo, the router phase status and the phase results.

### Modified Capabilities

- `board-viewer`:
  - MODIFIED "Viewer page", "Context-aware viewer shortcuts" and "Review in narrow windows";
  - ADDED "Workbench shell", "Docked panels and layouts", "Keymaps", "Workbench themes", "One selection
    model", "Linked messages", "Provenance of displayed values", "Viewer frame budget" and "Workbench
    accessibility".
- `cli-contract`: ADDED "View command workbench options" (`--workspace`, `--keymap`, `--layout`, `--roles`
  and `--edit`).
- `net-roles`: ADDED "Forget stored roles" (`--forget`, `--forget-group`).
- `viewer-visual-tests`: ADDED "Workbench references" and "Deterministic screenshots".

## Non-goals

- **Geometry editing.** The viewer does not move, draw, route or delete copper, parts or wires. Designs are
  changed by scripts and commands.
- **Copies of vendor artwork.** No Altium or KiCad icon, artwork, colour file, layout file or code is
  copied. Their conventions are described from public documentation (S-0920 to S-0924), and the icons are
  Fenolite's own.
- **A runtime dependency in the core.** `pyproject.toml` `dependencies` stays empty. The optional native
  window is an extra, imported lazily.
- **Lock and unlock.** No command locks or unlocks copper today. The viewer shows locks and does not
  change them (open question 5 of `design.md`).

## Impact

- **Code:**
  - `src/fenolite/view/` (the page split into `ui/`, the export assembly, the server write routes, the
    roles scene);
  - `src/fenolite/cli/cmd_view.py`, `src/fenolite/cli/cmd_roles.py`;
  - `tests/visual/`, `tests/unit/view/`, `tests/unit/cli/`.
- **Docs:**
  - `docs/viewer.md` (rewritten around the workbench), `docs/roles.md`, `docs/cli-contract.md`;
  - agent guide pages `commands` and `board-review`;
  - `docs/evidence/sources.md` (S-0920 to S-0933);
  - `docs/hypotheses.md` (`H-G-WB-*`).
- **Behaviour:**
  - every existing view feature stays, with new places in the workbench;
  - the eight screenshot baselines are regenerated once, after review;
  - `fenolite view` without `--edit` still writes nothing but `--export` and `--marks`.
- **Changelog.** The entry is added only after `0.7.0.dev0` opens. While `0.6.0` is cut and not published,
  the v0.6 guard requires `## [Unreleased]` to be empty.
