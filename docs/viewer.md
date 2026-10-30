# Board and schematic viewer

`fenolite view` shows the boards, the sheets, the libraries and the Altium Draftsman drawings of a project in a web browser, without the tool that made
them: an Altium project on a machine without Altium, a KiCad board in a review, a board or a sheet an agent
just wrote. It reads every board through the neutral model (change c0176), draws every Altium `.SchDoc` in
the manner of Altium Designer (change c0177) and every KiCad `.kicad_sch` in the manner of KiCad (change
c0178). Each document keeps the look of its own tool (see "Colours"). It writes no design file and opens no
connection beyond the loopback address.

```bash
fenolite view MyProject.PrjPcb --serve              # live: http://127.0.0.1:8765/, reloads when a board is saved
fenolite view board.kicad_pcb --export board.html --confirm    # one standalone page to open or send
fenolite view MyProject.PrjPcb --json               # for an agent: the documents and a scene summary
fenolite view MyProject.PrjPcb --doc Power.SchDoc --json        # the parts, pins, wires and nets of one sheet
fenolite view Assembly.PCBDwf --export assembly.html --confirm  # an Altium Draftsman drawing, sheet by sheet
fenolite view board.kicad_pro --serve --theme my-theme          # a KiCad project in your own KiCad colours
fenolite view MyProject.PrjPcb --serve --silk-gap 0.15 --mask-expansion 0.1   # with the board's silk rules
```

Saved-file rebuilds and background 3D refinement belong to a document generation. If the file changes
while an older refinement is running, that refinement cannot replace the newer scene.

Document navigation also keeps the latest selection: a slow scene or error from a previous document
cannot replace the current view, even when switching back to the same document. A new document shows
its name and a reading card while loading. Delayed cross-probes, marks and BOM selections stop when
another navigation supersedes them. Live polling revalidates a scene before adopting its first version
(including a cached scene opened again), waits during scene loading, and ignores older replies. Failed
reads retain their error and can be retried by a later poll without marking the failed version as loaded.

## Colours

Each document is drawn in the colours of the tool that made it (change c0178):

| document | colours |
|---|---|
| KiCad board, KiCad sheet | Fenolite's palette in the manner of KiCad: a dark navy board with red front and blue back copper, a cream sheet with a dotted grid, green wires, dark red symbols on a pale yellow body, stroke text. With `--theme`, your own KiCad colour theme |
| Altium board | Fenolite's palette in the manner of Altium Designer: black background, red top and blue bottom layers, yellow overlay |
| Altium sheet | the colours its records hold, as Altium draws them (c0177) |

`--theme NAME` takes a KiCad colour theme: a `.json` file, or the name of a theme in the `colors` folder of
your KiCad settings (`~/.config/kicad/<version>/colors` on Linux, `%APPDATA%\kicad\<version>\colors` on
Windows, `~/Library/Preferences/kicad/<version>/colors` on macOS). With it, a KiCad project looks colour for
colour as in your KiCad. The palettes are Fenolite's own: no value of KiCad's or Altium's built-in themes is
copied (`docs/formats/kicad/color-theme.md`).

## The page

The page is one HTML file with its styles and script inline and no external URL, served by `--serve` and
written by `--export`. It is built from the TypeScript sources in `viewer/src/` into `src/fenolite/view/static/`
(change c0304; `CONTRIBUTING.md`, "The viewer page's sources"); installing Fenolite needs no Node.

- **Toolbar** (change c0300). The document's name with **About this document** (the ⓘ button), then three
  groups: **View** (2D / 3D `D`, Fit `F`, Top / Bottom `B` with the far side's opacity in its menu), **Tools**
  (Measure `M`, whose menu also offers Edge gap `Shift+M`; Mark `N`; the unit, mm or mil, `Q`) and **Share**
  (Copy link; Export: Save as SVG, Print fitted to the page or at 1:1, 2:1, 5:1 or 10:1). At the right: **Run
  checks** when the server runs them (change c0302), the assembly variant, the search field, the interface
  theme and the shortcut sheet. Every button has an icon, a name for screen readers and a tooltip with its
  shortcut; a control that does not apply to what is shown (Measure in 3D, Top / Bottom on a sheet) is not
  shown. The selection clears with `Esc` or from the palette.
- **Command palette.** `Ctrl+K` (`Cmd+K` on macOS), or typing in the search field, opens one search box over
  the commands of the toolbar and the parts, nets, documents and library items of the open project. Arrows
  move, `Enter` runs the command or selects and frames the part or net (or opens the document), `Esc` closes.
  A leading `>` keeps commands, `@` parts and `#` nets. `Ctrl+K` works from a text field too; no other
  shortcut does.
- **Shortcut sheet.** `?` lists every shortcut by group, with the pointer gestures; the toolbar, the palette
  and the sheet are built from one command registry, so what one offers the others offer.
- **Interface theme.** The page follows the system's light or dark setting until a theme is chosen in the
  toolbar's theme menu or the palette; the choice is kept in the browser. Only the interface changes: a
  document keeps its own colours (see "Colours").
- **Side bar** (left). **Project review** at its head, with the states of its cards ("1 failed · 7 not run");
  then one section per panel, each with a count, that folds open or closed and stays so on the next visit:
  Project, Library or Navigator, Filter, Components, Nets, Changes, Messages, Marks, Findings and Document
  notes. A list with nothing to show says why ("No nets match 'x'").
- **Projects** (the Project section). The project's documents, grouped as the native tools group them:
  Source Documents (schematics, boards, harnesses), Libraries, Settings (output jobs, rules, stack-ups, library
  tables), Documentation (drawings, annotations) and Other. A board opens on click; any other document shows a
  card with its kind, path and size and the kinds the viewer opens. A document listed by the project but
  missing from the folder is grey.
- **Loading and errors.** While a document is read, a card names it and a thin bar runs under the toolbar. A
  read that fails shows its error with **Retry**, which reads the same document again if it is still the one
  chosen.
- **Status bar** (bottom). The cursor position in the page's unit, the grid of a sheet, the zoom, the current
  layer, the selection, the unit and the live state ("Live · updated 12:03", "Building…" or the read error).
- **About this document.** The file's name and path, size, full SHA-256 with **Copy**, the backend, the
  evidence level of the read, the scene version of a served page and the number of notes.
- **Narrow windows.** At 760 CSS pixels or below, the side bar button shows or hides the side bar over the
  view; it starts closed so the board keeps the window's width. The toolbar wraps into rows and shows icons;
  Share moves into the **More** menu. Choose a document, use the button again, or press `Esc` outside a form
  field to close the side bar.
- **Keyboard focus.** Viewer shortcuts pause while editing a text field, choosing a select value or using
  Ctrl, Command/Meta or Alt combinations, except `Ctrl+K` for the palette. Shift shortcuts remain available
  outside form controls.
- **Inspector** (right dock, change c0301). Beside the drawing, never over it: the **Properties** tab shows
  what a click selected in sections (Part, Pad, Track, Arc, Via, Zone, Net, Keep-out, Finding; on sheets the
  component or the object with its net and project net; on libraries the item), each value in the page's unit
  with a copy control, and **Copy all** copies every row as `label: value` lines. A value the file does not
  hold is left out, never shown as 0. With nothing selected it shows the document's summary. Above the
  sections are the actions on the selection: **Zoom to**, **Highlight net**, **Select part**, **Find
  similar**, **Show in schematic** or **Show on board** (the cross-probe of a double click), **Open in
  review** for a finding, and on a page served with `--allow-actions` **Move part…** and **Waive finding…**
  (see "Actions"); the palette lists them too. `I` hides or shows the dock; its left edge resizes it (240 to
  480 px); both are kept. At 760 CSS pixels or below it is a sheet over the lower part of the window (at most
  60 % of its height) that a selection opens and `Esc` or its close button dismisses.
- **Layers panel** (the dock's Layers tab on boards and footprints). The layers in groups (copper, mask and
  paste, silkscreen, mechanical and fabrication, view layers), each row with its colour, its full name (the
  native name of an Altium layer), whether it is current, its opacity and its visibility; a group's eye shows
  or hides the group.
  - A click on a name or its radio makes that layer current: it is drawn last, above the others.
  - `Shift+S` shows the current layer alone; `+` and `-` step through the visible layers.
  - **Presets** offers layer sets: all layers, signal layers, the top side, the bottom side, the defaults, and
    the current layer alone. Sheets keep their document tabs in the bottom bar.
- **Net emphasis.** A selected net or part, or the filter's result, is drawn in its own layer colours at full
  opacity with a thin outline, while the rest of the board steps back by the highlight mode (Dim 22 %, Mask or
  Normal); the zone fills of a selected net are drawn lighter and outlined, so its tracks and pads stay visible
  over the pour.
- **Board view.** Wheel to zoom, drag to pan, click a pad or track to highlight its net (or a part's own
  drawing to highlight the part). **Top / Bottom** (`B`) turns the board over: the other side is drawn under
  the visible one at the opacity set in the button's menu. The palette finds a part by reference or a net by
  name.
- **Measure** (`M`): see "Units and measurement" below. Change c0193 adds the edges: without a point target
  within reach, a click snaps to the nearest point of an edge (a pad or fill border, a track border or axis, a
  circle, an outline), and the readout names what each end snapped to. Hold `Alt` to measure without snapping.
- **3D** (`D`). The board is a slab of its stack-up's thickness (1.6 mm, stated, when the file has none). Its
  faces are textured with the copper, mask, silkscreen and drills of each side. The controls that only act in
  2D (Measure, Mark, Top / Bottom, the Layers tab, Find similar) are hidden. The **view cube** at the top right
  turns with the camera: a click on a face sets that view (top, bottom, front, back, left, right), a click on a
  corner the iso view from it. The dock's **3D view** tab has the same views, Reset, and shows or hides the
  bodies, the board, the silkscreen and the copper. The light is an ambient term with a key light from the
  upper left and a fill light from the other side.
  - **Models.** A board that embeds 3D models (an Altium `PcbDoc`) shows them, in their colours, placed as
    the native tool places them (change c0193). A model whose stored placement does not match its body's
    outline is fitted to it, and the info says how.
  - **Extruded bodies.** Any other body is extruded from its outline between its standoff and its height,
    in Fenolite's dark body colour with a lighter top face.
  - **gmsh.** Models are meshed by `gmsh` (`FENOLITE_GMSH`, or `gmsh` on `PATH`), run as a separate
    program. Meshes are kept in the state folder. Without gmsh every body is extruded, and the notes say so.
- **Findings** (left), by group. The box beside a group shows or hides it on the board, a click on its title
  lists its items, a click on an item fits the view to it, and the tooltip says the group's rule and model.
  Groups with no finding fold into one line, "n groups with no findings", that lists them with their 0.
  - **Review groups** (`--no-review` leaves them out): 45° corners (acute, 90° and in-between turns of two
    tracks, tracks off 0/45/90°, zone outline corners); silkscreen near a mask opening, near other silkscreen
    or outside the board; copper outside the board; the open connections of `fenolite analyze`'s
    connectivity, ground nets apart.
  - **Silkscreen gap.** It is `--silk-gap`, else the board's `silk_clearance` rule, else 0. The pads' mask
    openings grow by `--mask-expansion`; the viewer does not read the pads' own `mask_margin` (change c0223).
  - **Files.** With `--overlay REPLY.json`, the clearance (red) and creepage (blue) paths of a `fenolite
    analyze` reply are drawn. A pair that an error or a warning names is marked as a finding.
  - **Findings files.** `--overlay` also reads a findings file of another tool, `fenolite.view_overlay.v0`:
    `{"schema", "groups": [{"id", "title", "color", "note"}], "items": [{"group", "kind": "line" | "path" |
    "point", "points_nm": [[x, y], ...], "label", "layer"}]}`, in the board frame of the model (nanometres,
    Y down).
- **Document notes** (left): what the scene had to assume.

## What the scene shows, and what it states

| item | drawn from | stated when |
|---|---|---|
| pads | the backend's board frame: the copper of each pad on each layer | — |
| mask and paste openings | the pad's own mask and paste layers; Altium native expansion rules as described below | derived from the pad kind with no expansion when only the neutral model is available; Altium native views state rule/default assumptions |
| tracks, arcs, vias, holes | the model | — |
| zones | the fills saved in the file | a zone without a fill is drawn as a dashed outline and counted; refill it in its tool |
| graphics and texts | the model, footprint items placed by the footprint's position and angle | texts use Fenolite's own single-stroke font; a text on a back layer is drawn mirrored |
| bodies | the model's body outlines and heights, or the board's embedded 3D models (gmsh) | a fitted model, a body left extruded, gmsh missing |
| texts of an Altium board | anchored at their lower-left corner, a glyph two thirds of the height | always: the import gives them as centred |

The palette is Fenolite's own. Coordinates are in the board frame of the model: millimetres from the
outline's top-left corner, with Y growing downward.

## Nets across sheets and the board

In an Altium project a net crosses sheets through ports, sheet entries, power ports, net labels and harnesses
(change c0185). The viewer names every net of a sheet by its project net, as the project compiles (`build` and
`check` see the same nets):
- **The Navigator** lists each net with its pin count on the sheet and the number of sheets it reaches; a
  local net whose label differs shows its project net (`N1 → RESET_N`).
- **A click on a net** shows its pins on the sheet and in the whole project, and links to the other sheets it
  reaches.
- **The selection follows you**: a net chosen on a sheet is selected on the next sheet or board you open, and a
  net clicked on the board is selected on the sheets. With `--serve`, the pages of other tabs follow too. `Esc`
  clears it.
- A project that does not compile keeps each sheet's own nets, with a note.

## Assembly variants

An Altium project's variants (`[ProjectVariant<n>]` of the `.PrjPcb`, change c0186) get a selector in the
toolbar, `[No Variations]` first; the choice applies to every sheet and to the board:
- a part the variant does not fit is crossed out in red on its sheet and on the board, where it is also dimmed,
  and its body is left out of the 3D view;
- a part's Properties show its state in the variant and the variant's values of varied parameters;
- `fenolite view PROJECT --variant NAME --json` opens with that variant and counts the fitted and not-fitted
  parts of the document shown; an unknown name is `FEN-2001`.

A variation names its part by the part's unique id, so a part annotated after the variant was made is still
found. The kinds (not fitted, alternate part, fitted with other values) are read as `INFERRED`
(`H-A-PRJ-VARIANT`).

## Reviewing a board: filter, panels and parameters

The side bar of a board holds, as Altium's PCB panel does (change c0187):
- **Filter.** A query selects primitives and parts and highlights them: `key:value` terms joined by spaces
  (and), `|` (or), a leading `-` (not), `*` and `?` wildcards and quoted values. The keys are `net`, `ref`,
  `footprint`, `value`, `layer` (its id or the board's own name, such as `"Top Layer"`) and `side`; any other key
  names a part parameter (`tolerance:1%`), and a bare word matches a reference or a net. For example
  `footprint:*0402* side:bottom`, `net:GND layer:"Bottom Layer"`, `ref:R* -value:10k`, `ref:U1 | ref:J?`.
  Enter applies it and zooms to what it found. The grammar is Fenolite's, not Altium's query language.
- **Find similar** fills the filter from the selection: the same footprint and value for a part, the same net
  and layer for a primitive of a net, the same layer otherwise.
- **Highlight.** `Dim` (the default) dims the rest of the board, `Mask` nearly hides it and `Normal` leaves it;
  the choice is remembered. `Shift+C` clears the filter and the selection.
- **Components** and **Nets** list every part (reference, value, footprint, side) and every net with its pad
  count and its routed length, the centre lines of its tracks and arcs (Fenolite's computation, vias not
  counted). With a filter they list what it found; each has its own text filter, and a click selects and zooms.
- **Parameters.** The Properties of a part show every parameter the file holds: a KiCad footprint's fields, and an
  Altium part's description, footprint description, library keys, hierarchical path, height and lock (its
  `Components6` record). On a board of an Altium project the parameters of the schematic part are added,
  matched by unique id. A parameter that is a web address is a link.

## Check findings

### Project review (development after 0.5.0)

Choose **Review** in the Projects heading for the current document's status and a guided list of
reported problems. Reading, netlist connectivity, ERC, DRC, clearance, placement, fill, model validation,
conversion and fabrication export have separate states: **Not run**, **Passed**, **Failed** or **Limited**.
An absent check is not a pass. Expand a card to read stage evidence, skip reasons, warnings, partial
coverage and capped counts. This panel does not give an overall fabrication approval.

`--check FILE` supplies an existing check reply; `--check run` keeps its existing explicit execution
behavior. Repeat `--report FILE` to attach one recorded `convert` reply and one recorded `export` reply.
For example, when those JSON files have already been recorded:

```sh
fenolite view board.kicad_pcb --check checks.json --report conversion.json --report fabrication.json --json
```

Loading a report never runs its command. The same information is in `result.review`, a served page and
an exported HTML page. Export uses the usual dry-run/confirmation protocol, and a changed report file
invalidates its staged plan. Reports do not refresh automatically when a live document changes.

A matching report input hash binds only the named document's bytes. A missing hash, another input or a
changed revision keeps passing results **Limited**, with a historical-report warning; other project files
are not bound by that one hash. Reported errors remain failures. A conversion needs its receipt and
equivalence record and must state nonexperimental, nonlossy scope before its recorded result can pass.
An export reply records artifact generation; it currently does not attest successful readback, so the
fabrication-export card remains limited even when generation succeeded.

#### Running checks from the page (change c0302)

A page served with `--serve` can run the checks itself. Each card whose stages the server can run has a
**Run** control, and **Run from this page**, under the cards, picks the stages of `check` (**Run checks**,
**Run all checks** for the default stages), the kinds of `analyze`, a readiness check (`ready`) and a
comparison with another document of the project (`equivalent`). Nothing runs unless you ask: opening a
document or saving a file runs nothing.

One job runs at a time. A strip over the drawing shows the command, its last progress record, the elapsed
time and **Cancel**; a cancelled run, or one that passes `--run-timeout SECONDS` (default 600), changes
nothing and says so. A failure shows the command's message and hint; when `kicad-cli` is missing the stages
that need it could not run. A `check` run replaces the stages it ran, with their findings, and keeps the
other stages with their own input hash, so a stage run on an older revision reads **Limited**; the cards, the
Messages panel and the markers are drawn again. `analyze` paths become finding groups; `ready` and
`equivalent` findings join the review list with **Locate** when they name a part, pad or net. Results stay in
the server's memory for the session; a finding is never marked fixed, the next run replaces it.

The server runs only `check`, `analyze`, `ready` and `equivalent`, read-only, on the files of the project,
with options checked against the commands' own choices; it never takes a command line, a path or
`check --exclude` from the page. Each run is a child process in the project folder. Requests must come from
the page of this server (`Host` and `Origin` checked, the header `X-Fenolite-Run: 1`). Serve with `--no-run`
to show recorded results only; an exported page never runs anything.

```sh
fenolite view board.kicad_pro --serve --run-timeout 1200   # a slow DRC on a large board
```

#### Actions: writing from the page (change c0303)

`fenolite view board.kicad_pro --serve --allow-actions` lets the page write the project's files, always
through a plan you review first. Without `--allow-actions` the page offers no action and the server refuses
every one. The **Actions** section of the review panel holds **Fill zones**, **Tidy copper** (prune,
straighten, chamfer; each edit kept only when KiCad's DRC accepts it, `--gate drc`), **Silkscreen**
(designators, clipping), **Place test points**, **Export fabrication files** and **Bill of materials** (into
`fab/` or another folder under the project), **Move or rotate a part** (the selected part's position and
rotation filled in, in the page's unit; the arrow keys nudge it, Shift for ten steps), and **Move** or
**Turn parts with their copper**. A finding of KiCad's DRC in **Review findings**, or in the inspector, gets
**Waive finding** with a required one-line reason, stored as a KiCad DRC exclusion in the project file. Waive
is not offered on a finding of a check of an earlier revision of the file (its index may name another
violation now): the page says so and offers **Run again**. A write that changes a project file the checks read
(a waiver writes the `.kicad_pro`, not the board) marks the document's results stale: the run strip, the
Project review and the inspector say so and offer **Run again**, which repeats the document's last run, until
a check runs again (fixes of 2026-10-29).

**Review plan…** runs the command's dry run. The plan dialog names every file it would write (path, kind,
size, new SHA-256 and the SHA-256 it replaces), the issues by severity and the evidence, and draws the
changes of the staged board over the current one: added copper in green, removed in magenta, moved parts as
arrows, listed under Changes. An error finding plans no write and disables **Confirm and write**, the only
control that writes. Confirm writes exactly the reviewed bytes (`--confirm --plan`); when a file changed
since the review the dialog says so and offers **Review again**. After a write the dialog shows the
receipt (files, digests, backups kept) and the board is read again at once. **Undo…**, on the receipt or in
**Writes of this session**, plans `fenolite restore` on that receipt and is reviewed and confirmed the same
way; `restore` refuses when a written file changed since. Each receipt is also kept in
`view-receipts/` of the state folder.

Security: the server listens on `127.0.0.1` only, checks `Host` and `Origin`, needs the header
`X-Fenolite-Action: 1` and a per-session token that only this server's page can read, runs only the fixed
templates of these actions with typed options (lengths with a unit, angles, part references of the board,
a reason of one line, output paths under the project folder), confirms only plans it made in this session
whose every write lies under the project folder, never sets `--no-backup`, and writes no Altium document
(the actions show as unavailable there). Every write keeps a backup. Stop the server when you are done.

Use **Review findings** to jump from the status cards to the problem list. Filter by severity, stage or
text; Previous/Next visits matching messages with their original hints and evidence. **Locate in drawing**
reveals the finding's layer and marker and closes the panel so the drawing is visible. Unplaced findings
say so. Reviewing or locating an item does not mark it fixed; check again after editing. Native controls
support keyboard use; Escape closes the panel, including while a filter has focus.

`fenolite view PATH --check FILE` draws the findings of a `fenolite check --json` reply over the document
shown; `--check run` runs `check` first, in the same process and read-only (change c0188):
- **Markers.** A finding with a position gets a ring in the colour of its severity (red error, orange warning,
  blue info); errors are drawn on top. `E` shows or hides them. A marker on a hidden layer is hidden too.
- **Messages.** The panel lists every finding grouped by code, errors first; a click zooms to the finding,
  makes its layer current, frames what it names, and shows its message, its `where`, its stage and that
  stage's evidence (`KICAD-VERIFIED(kicad-cli 10.0.7)` for KiCad's DRC and ERC). Findings without a position on
  the document are listed with "(no position)".
- **Positions.** A finding is placed by the position KiCad reports (`@x,y` in `where`), by the point of
  Fenolite's copper check (`on F.Cu at (x, y) mm` in its message), or by what it names: a pad (`R1-2`), a part, a
  track, arc, via or zone by its KiCad locator (`/kicad_pcb/zone[0]`), or a net. When it names a zone and a pad
  inside it, the marker goes on the pad. ERC findings are placed on sheets (on the root sheet for the path `/`,
  else on the sheet whose file stem is the last segment of the path), and findings of the board stages on
  boards.
- A DRC that `summary.limits` capped is a lower bound; the panel says so.
- **Role findings.** A finding of the stage `roles.rules` (`docs/roles.md`) is placed on the pads of the role
  group it names (`hot_SW`), or on one of them (`kelvin_R12:R12-1`), when the board has role data.

## Net roles

`fenolite view BOARD --roles run` runs `fenolite roles BOARD --check` first, in the same process and
read-only, and draws its reply on the board; `--roles FILE` reads a saved `--json` reply of it (change c0305,
which brings over the role view of c0245-engineering-viewer). The numbers on the page are the reply's: every
role, group, measure and finding as the command gives it, with its evidence (`INFERRED`).
- **Net roles panel.** A side bar section: the counts by state (declared by a script, confirmed by a person,
  inferred), a legend with the colour, glyph (`P` power, `SW` switch node, `G` ground, `HV` high voltage, `GT`
  gate, `K` Kelvin, `S` signal), name and count of each role kind (a click lists that kind only), one row per
  net (glyph, net, kind and current, confidence, state: ✓ confirmed, ◆ declared, ? inferred), the groups (hot
  loops, gate loops, Kelvin pairs) and the role findings by code. A net row highlights the net and opens it in
  the inspector, where a **Role** section follows the Net section (kind, state, rule, confidence, the pads the
  inference read, current, working voltage, sensitivity, the groups that hold the net); a group row frames its
  pads and shows its pads, net and loop area against its placement bound; a finding row selects its marker.
- **Overlays.** The Layers tab of the dock gets a **Roles** group: **Role colours** (the copper of each role
  net in its role's colour; signal nets keep their layer colours; a picked net still shows in its own
  emphasis), **Loops** (each hot loop hatched at 45° and each gate loop at 135°, a polygon through the centres
  of its pads in loop order, labelled from 12 px/mm with the loop area the analysis measured along the
  copper), **Kelvin pairs** (dashed sense lines from the element's pads to the receiver's) and **Role
  findings** (rings with a cross, in the colour of their severity). Colour is never the only cue: each role
  has a glyph, each overlay its own hatch or dash. The palette commands **Roles: …** toggle the same.
- **From a served page.** The panel's **Run roles again** (or the palette's **Roles: run fenolite roles
  --check**) runs the command in a child process like the other runs; a board without role data shows the
  section with that one control. With `--allow-actions`, **Confirm N inferred…** plans `fenolite roles
  --accept NETS --accept-group NAMES` for every inferred row, and **Confirm role…** in the inspector for one
  net: the plan dialog names the role document it writes (`<board>.roles.json`, or `.fenolite/rules.json` of
  a project Fenolite built), Confirm writes it, and the board is read again with its roles run again (a
  `--roles FILE` reply stays until **Run roles again**). Undo is
  `fenolite restore` on the receipt; it deletes no file, so undoing the write that created a role document
  leaves the file in place. A script's declared roles are never written from the page.

```sh
fenolite view build/board.kicad_pcb --roles run --export roles.html --confirm   # a page with the roles
fenolite view build/ --serve --roles run --allow-actions                          # confirm roles from the page
```

## Review tools

Change c0189 adds what a review in Altium relies on:
- **Edge measure.** `Shift+M` (or Edge gap in the Measure menu) measures the shortest distance between the edges of two clicked
  objects: pads (all of a pad's copper on the layer clicked), tracks, arcs, vias, zone fills, board edges. A
  line joins the two closest points and the gap reads in the page's unit; overlapping objects read 0. Arcs are
  sampled every 2°, the rest is exact; on the authored test pair and against the gap `fenolite analyze` reports
  for a pad and a track the two agree within 1 µm. Objects on two layers are measured in the plane.
- **Links.** The address of the page keeps the document, the selection, the zoom, the centre, the unit and the
  current layer (`#doc=doc1&sel=U5&z=23.438&c=106.045,68.575&u=mm&l=F.Cu`); Copy link copies it, and opening it
  restores the view. `fenolite view PATH --select U12` opens at a part or a net.
- **Review marks.** `N` (or Mark) drops a mark with a note where you click; the Marks panel lists them, a click
  zooms, `×` deletes. With `fenolite view PATH --serve --marks review.json` the server saves them to that
  file (`fenolite.review.v0`, positions in nanometres); an exported page keeps them in the browser and
  Download marks saves the file. `fenolite view PATH --marks review.json --json` lists them for an agent.
- **SVG and print** (the Export menu). Save as SVG saves the view as a vector file: the page draws it again into a recorder of its own
  drawing calls, so the file shows what the screen shows (layers, selection, markers). Print prints that SVG,
  fitted to the page or at 1:1, 2:1, 5:1 or 10:1 on paper; the print dialog's Save as PDF gives a PDF. Both
  need the 2D view.

## Documentation: BOM, output jobs, drawings

Change c0190 opens what an Altium project keeps beside its boards and sheets:
- **BOM.** A `.BomDoc` opens as a table. Altium's ActiveBOM document holds the BOM's settings and catalog, not
  its lines, so the viewer builds the lines from the project's parts: grouped by the document's grouping
  parameters (`Comment` and `Footprint` by default), with each group's designators and quantity, the catalog's
  description, manufacturer and part number, the document's manual lines (a bare board, labels, bags), its
  columns, aliases and sort. Supplier columns (prices, stock) are left out. A click on a line selects its parts
  on the board, with the filter of the review panels. Opened without its project, the document lists its
  catalog.
- **Output jobs.** An `.OutJob` opens as the list of its outputs: group, name, type, category, the document it
  binds, variant, whether it is enabled, and each container with its output folder as the job writes it
  (`Outputs\[Media Name]\board.PDF`); the viewer does not run the job. A click on an output opens the
  document it binds (the project's BOM document for `[ActiveBOM Document]`).
- **Draftsman side views and callouts.** Front, back, left and right views are drawn from the document's copy of
  the board: the board's section and each part's box, as high as the part type's `Height` from its `MinZ`, in the
  frame the document stores, with the dimensions placed on them. A part without a height is drawn 1 mm high.
  A callout is drawn with its leader, its arrow and its tag, the number of the note element it names. Both are
  `INFERRED` (`docs/formats/altium/draftsman.md`, "Side views and callouts").

## Comparing two revisions

`fenolite view NEW --compare OLD` shows what changed between two revisions of a board or a sheet (change
c0184), the fastest way to check a change an agent made:
- **On the board** the primitives NEW adds are green and those it removes magenta, over a dimmed board; a moved,
  turned or flipped part gets an arrow from its old place. `X` shows or hides the changes.
- **The Changes panel** lists one line per change: a part added, removed, moved (with the distance and the
  angle) or with a new value or footprint; a part whose own pads or graphics changed; a track, via or graphic
  added or removed; a zone whose filled area changed (with both areas). A click zooms to it.
- **On a sheet** the parts added, removed, moved or with changed parameters are framed, and the nets whose pins
  changed are listed.
- Parts match by reference and the rest by geometry, net and part, not by numbered labels, so a renumbered file
  still matches; a refilled zone is one change. Two documents of different tools, or a board and a sheet, are
  refused (`FEN-2001`).

## Keep-outs, dimensions and placement marks

The board view also draws what a reviewer checks first (change c0183):
- **Keep-outs.** A rule area is drawn hatched on its layers (on every copper layer for one of all copper),
  and a click names what it forbids (tracks, vias, pads, copper pours, footprints). The regions of Altium's
  Keep-Out Layer are drawn hatched too, and that layer is shown by default; its free board cut-outs are drawn
  as the board's outline.
- **Dimensions.** A linear dimension of the board is drawn with its extension lines, its line and its value,
  on its own layer, which is then shown by default. An orthogonal dimension follows KiCad's side for its
  offset; an aligned one puts its line on the same side (INFERRED).
- **Placement marks.** Parts whose courtyards overlap, and parts inside a keep-out that forbids footprints, are
  marked hatched on the `Checks` layer, judged as `fenolite place` judges them. Overlaps of parts without a
  courtyard (their extent taken from their pads, as for every Altium board read today) are counted in the
  notes, not marked, as they are often no conflict.
- Altium rooms and Altium dimensions are not drawn: no public board shows their records (`H-A-ROOM`).

## Speed and size

Large boards open fast the second time (change c0182):
- **Cache.** Each scene is cached by the SHA-256 of its file, the theme and Fenolite's own code, in your user
  cache folder (`--cache user`, the default; `FENOLITE_CACHE_DIR` moves it), under `.fenolite/view-cache/` of
  the project with `--cache project`, or not at all with `--cache off`. A changed file, theme or Fenolite
  rebuilds the scene; the cache is safe to delete.
- **Compact scenes.** Board scenes leave Fenolite in a compact form (`fenolite.view_scene.v1`), and an
  exported page holds each scene gzipped and decodes it only when its document is opened. On the largest public
  board of the corpus (544 parts, 8 355 tracks) the page went from 5.9 MB to 0.5 MB.
- **`--docs ID,...`** with `--export` embeds only those documents, for a page to send; a page above 20 MB gets a
  warning in `result.export`.

## Altium boards

An Altium board is shown as Altium shows it (change c0181):
- **Layer names.** Each layer has the name the board's layer stack gives it (`Top Layer`, `GND 1`, `Top Mask`,
  `Mechanical 1`, or the designer's own names); the outline is `Board Outline`. The tabs follow Altium's order:
  signal layers, planes, overlays, pastes, solders, mechanical layers, then the drill and keep-out layers.
- **Mask and paste openings.** Each pad's solder-mask and paste opening is its copper grown by its expansion:
  the pad's manual value, else the `SolderMaskExpansion` or `PasteMaskExpansion` rule that governs it (by
  priority; scopes that Fenolite does not evaluate are skipped and counted in the notes), else 4 mil of mask and
  no paste expansion. A negative expansion shrinks the opening.
- **Properties.** A click on a pad shows its expansions, where each comes from (manual, the rule's name, or
  default) and the size of its mask opening.

## Units and measurement

Every length the page shows can be read in millimetres or in mil (change c0179). The **mm / mil** button in
the toolbar's Tools group and the key `Q` switch it, as in Altium. The choice is kept for the next visit of
the page, and the status bar names it. It applies to:
- the cursor position in the status bar and the grid of a sheet;
- measurements;
- the inspector's rows: track width, length and ends, arc width, radius and length, via diameter and drill,
  hole diameter, pad size, corner radius, drill and slot, mask and paste expansion and the mask opening, part
  position and extent, a net's routed length, a zone's filled area, a footprint's copper and courtyard extent.
  A row's copy control copies the value as it reads.

**Measure** (`M`) works on boards, sheets and library items. Each click snaps to the nearest pad centre, line
end, vertex, circle centre or text anchor within 8 px. A pitch therefore reads centre to centre, and the
readout gives the distance with Δx and Δy. A third click starts a new measurement, and `Esc` ends it.

A click on a pad shows its exact size from the model, in the inspector's Pad section:
- width × height, shape and corner radius;
- drill, and slot length;
- centre, rotation and layers.

This is the place to check that an agent gave a pad, a pitch or a part the size that was asked for.

## Libraries

Schematic and footprint libraries open from the tree like any document (change c0179):
- Altium `.SchLib` and `.PcbLib`;
- KiCad `.kicad_sym`, a `.pretty` folder or one `.kicad_mod`.

The left panel lists the library's symbols or footprints, with a filter and a short summary of each: pins, or
pads and copper extent. A click opens the item:
- **A footprint** is drawn alone at its origin, as on a board: layer tabs, pads with their exact sizes,
  silkscreen, courtyard, fabrication and mechanical layers, and the 3D view of its bodies. Its colours are
  those of its tool.
- **A symbol** is drawn as on a sheet, one item per part or unit, with its pins, names, numbers and fields.
  The status line reads library coordinates from the symbol's origin.

Integrated libraries (`.IntLib`) are listed, not drawn.

## Draftsman drawings

Altium Draftsman documents (`.PCBDwf`) open from the tree like a library whose items are the sheets (change
c0180). A Draftsman document holds its own copy of the board, so a sheet is drawn from the document alone, as
Altium shows it before a refresh; Altium is not needed:
- **Views.** An assembly view draws the board outline and the parts of its side, each with its assembly
  strokes (else its silkscreen) and its designator; a fabrication view draws the outline and the copper of
  its layer; a drill view draws one symbol per hole size. Bottom views are mirrored.
- **Tables.** The drill table (symbol, count, size, plating), the layer stack legend (layer, material,
  thickness) and the bill of materials (comment, designators, quantity) are drawn from the document's data.
- **Sheet items.** Lines, rectangles, texts with their `=Parameter` values, pictures, notes and linear
  dimensions; the dimensions are measured on the board copy.
- A click on a part shows its designator, comment, side and size on the board; `M` measures on the sheet,
  in millimetres or mil. The status line reads sheet coordinates from the lower-left corner.

Front, back, left and right side views and callouts are drawn as described under "Documentation" above.
Transmission line tables remain omitted and are named in the notes.
Drill symbols, table cells, zone marks, dimension texts and the place of view titles are Fenolite's drawings;
texts use the font family the document names, in the browser's font, and break only at their own line breaks.
The view placement is `INFERRED` (`docs/formats/altium/draftsman.md`, "Drawing geometry").

**Panels.** An Altium board whose `EmbeddedBoards6` holds an Embedded Board Array, and a drawing whose
`IsPanel` is true, get a note: the array is not drawn until its records are measured (`H-A-PANEL-RECORD`,
Part Q of `docs/evidence/altium-pcb.md`). The board itself is drawn once.

## Schematics

An Altium sheet opens like a board: from the project tree, from the sheet tabs along the bottom, or with
`--doc`. The page then turns into a schematic view.

- **The sheet as Altium draws it.** The paper of the sheet's style or custom size, in its own colour, on a grey
  workspace, with the visible grid as lines, the border and its zones, and the title block. Every record keeps
  the colour, line width and font that the file gives it: pale yellow part bodies, navy wires and labels, red
  directive flags when the file says so. Texts use the font the sheet names (Times New Roman by default; the
  browser falls back to a serif font when the machine does not have it).
- **What is drawn.**
  - Parts in their own part and display mode, with their designator (and part letter), comment and visible
    parameters; a parameter `=Value` shows the value it names.
  - Pins with their names (overbars included), numbers, dots, clock wedges and active-low flags.
  - Wires, buses, bus entries, junctions, net labels, power ports in their style (bar, arrow, circle, wave,
    power ground, signal ground, earth), off-sheet connectors, ports, No ERC marks.
  - Sheet symbols with their entries and file names, harness connectors and signal harnesses.
  - Lines, polylines with their line styles and end shapes, polygons, rectangles, round rectangles, ellipses,
    arcs, pies, Bezier curves, notes, text frames, embedded images, and the template's own graphics.
  - Hidden pins and parameters are left out. IEEE symbols are counted in the notes, not drawn.
- **Navigation.** Wheel or `PgUp`/`PgDn` to zoom, drag (left or right button) to pan, `F` to fit.
- **Selection.**
  - A click on a part selects it: a green dashed box, and its properties (designator, comment, design item,
    footprint, parameters) in the Properties panel.
  - A click on a wire, a pin, a label, a port or a power port highlights its net: the rest of the sheet dims,
    and the panel lists the net's pins.
  - `Esc` clears.
- **Navigator** (left). The parts and the named nets of the sheet, with a filter; a click zooms to a part or
  highlights a net. **Search** finds a designator (`U1` or `U1A`) or a net name.
- **Double click.** On a sheet symbol, it opens the child sheet. On a part, it cross-probes: it opens the
  project's board and selects the part of that designator. On a board, a double click on a part opens the
  sheet that holds it.

What the schematic view states:

| item | drawn from | stated when |
|---|---|---|
| sheet, records, colours, widths | the file's records | a sheet without an area colour is drawn off-white, as saved sheets are |
| text size | the font table, at 9 mil per point | always: a Fenolite choice that keeps the pin texts of a 100-mil pitch apart |
| power ports, ports, sheet entries, pin marks, pin text offsets | the documented styles | always: these drawings are Fenolite's and may differ from Altium's by a few mil |
| title block of a sheet without a template | the sheet's parameters | always: the block is Fenolite's drawing |
| nets | the connectivity of one sheet (`altium-import`) | a net that crosses sheets is highlighted on each sheet under its own name |

### KiCad sheets

A KiCad sheet is drawn the same way, with KiCad's habits:
- the paper of its `paper` size with a frame and a title block from its `title_block`;
- the embedded symbols turned and mirrored as KiCad places them, with their pins (names, numbers, overbars,
  dots, clock wedges) and visible fields;
- wires, buses, bus entries, junctions, local, global and hierarchical labels, no-connect flags, power symbols,
  sheets with their pins, and free texts and graphics.

Every text is a stroke text in Fenolite's own stroke font, so a long field may end a little earlier or later
than in KiCad. The nets come from wires, junctions, labels, power symbols and hidden power pins. Images, text
boxes, tables and rule areas are counted in the notes, not drawn.

## For agents

Use `fenolite view PATH --json` to list a project's documents and to check what a board holds (the counts of
pads, tracks, zones, fills, texts and bodies, and the notes), or `--doc SHEET` for what an Altium sheet holds
(parts, pins, wires, labels, ports, sheet symbols and nets), or `--doc LIBRARY` for the names of a library's
symbols or footprints, or `--doc DRAWING` for the sheets and item counts of a Draftsman document. Use `--export` to hand a person one page to
review. `--serve` keeps running until it is interrupted; it is for a person at a browser.
