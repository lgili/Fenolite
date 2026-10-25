# board-viewer Specification

## Purpose
A board that a backend read is drawn in a browser without KiCad or Altium: the scene is built from the design model in plain JSON, the project tree lists the documents beside it, a single offline page draws them, and a local server keeps the page live while files change (change c0176).

## Requirements

### Requirement: Board scene
`fenolite.view.scene.build_scene(design, frame, *, name, data=b"") -> dict` SHALL turn a board design that a backend read, with that backend's `BoardFrame`, into a scene of plain JSON values in integer micrometres of the board frame: the board's layers in drawing order with a colour each, its primitives, texts, components, nets, outline and cut-outs, and its part bodies; it SHALL run no tool and import nothing outside the standard library.
- Every pad copper entry, track, arc, via, zone fill polygon, graphic (board and footprint), text, visible footprint field and hole of the design MUST appear in the scene, each on its layer, with its net and its component where it has them.
- A zone with no fill MUST appear as an outline on the layer `View.ZoneOutline` and be counted in `meta.unfilled`.
- When no layer of the board is a solder-mask layer, mask openings MUST be derived from the pads (an SMD pad on its side, a through-hole pad on both) with no expansion, and `meta.notes` MUST say so.
- `meta` MUST hold the file name, its SHA-256, the backend name and the evidence level of the read.

#### Scenario: Counts of a KiCad board
- **GIVEN** `tests/data/kicad/board/two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/unit/view/test_scene.py -k kicad` builds its scene
- **THEN** the scene holds one primitive per pad copper entry, track, arc and via of the model, one polygon per zone fill, and the layers `F.Cu` and `B.Cu` with their colours

#### Scenario: An Altium board without mask layers
- **GIVEN** `tests/data/altium/board6/board6.PcbDoc`
- **WHEN** its scene is built
- **THEN** the scene holds mask openings on `F.Mask` and `B.Mask` derived from its pads, and `meta.notes` names the derivation

### Requirement: Project tree
`fenolite.view.project.load_tree(path) -> ProjectTree` SHALL list the documents of an Altium project file, a KiCad project file, a folder or a single board, grouped as "Source Documents", "Libraries", "Settings", "Documentation" and "Other", each document with a stable id, its path relative to the project, its kind, whether it is present and whether it can be viewed.
- A board document (`.PcbDoc`, `.kicad_pcb`) MUST be viewable; no other kind is in this change.
- A path that leaves the project folder MUST be listed with `present` false and never opened.
- A folder MUST give the tree of its one project file, or of its boards when it holds none or several.

#### Scenario: An Altium project
- **GIVEN** `tests/data/altium/blink/blink.PrjPcb`
- **WHEN** `uv run pytest tests/unit/view/test_project.py -k altium` loads its tree
- **THEN** "Source Documents" holds its schematic and its board, the board is viewable, and the schematic is listed as not viewable

### Requirement: Viewer page
`src/fenolite/view/page.html` SHALL be one HTML file with inline styles and scripts and no external URL, that draws a scene in 2D (canvas) and 3D (WebGL), with the project tree in a left panel, the layer tabs along the bottom (current layer, visibility, single-layer mode, layer sets), Top and Bottom views, net and component highlight, search, measurement, overlays and notes; and `fenolite.view.export.page(tree, scenes)` SHALL embed a tree and its scenes into it.
- The page MUST read a scene either embedded (export) or from the server routes of "Live server".
- Texts MUST be drawn with Fenolite's own single-stroke font.

#### Scenario: Standalone page round-trips
- **GIVEN** the tree and the scene of `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/unit/view/test_page.py` exports the page and reads the embedded JSON back
- **THEN** the JSON equals the scene, and the page holds no `http://` or `https://` URL

### Requirement: Live server
`fenolite.view.server.serve(live, port)` SHALL serve the page, `/project.json`, `/scene/<id>.json` and `/version/<id>` on the loopback address only, and a watcher SHALL rebuild a document's scene when the file changed and then kept its size and time for one more check.

#### Scenario: A saved board is reloaded
- **GIVEN** a server on port 0 over a copy of `two_layer.kicad_pcb` in `tmp_path`
- **WHEN** `uv run pytest tests/unit/view/test_server.py` fetches the scene, rewrites the file with one track less and runs two watcher steps
- **THEN** `/version/<id>` reports a new version and the scene holds one segment less

### Requirement: Review findings
`fenolite.view.findings.review(design, frame, *, silk_gap=None, mask_expansion=0) -> Review` SHALL return the review findings of a board as overlay items of groups, with the standard library, `model`, `geometry` and `backends.base` only; it SHALL run no tool. Every group SHALL be reported with its count, a title, a colour and a note that names its rule and its model, so that a zero is a result.
- `corner_acute`, `corner_90`, `corner_mid`: two free tracks of one copper layer that share an end point, with no third item ending there, MUST be judged by the turn between them: above 90°, exactly 90°, or above 45° and below 90°. A corner inside a pad's copper on that layer MUST NOT be listed.
- `track_angle`: a track whose direction is more than 0.5° from a multiple of 45° MUST be listed.
- `corner_zone`: a zone outline vertex whose interior angle is below 134° MUST be listed when a fill of the zone covers it or the zone has no fill, and the vertex is not inside a pad.
- `silk_mask`, `silk_silk`, `silk_edge`:
  - `silk_mask`: a silkscreen item closer than the silk gap to a mask opening. Openings are the pad copper on the side's copper layer grown by `mask_expansion`, and the untented vias.
  - `silk_silk`: a text closer than the gap to another silkscreen item of its side.
  - `silk_edge`: an item outside the board ring, in a cut-out, or closer than the gap to an edge.
  - Each MUST be placed at the shapes' witness point.
  - The silk gap is `silk_gap` when given, else the design's `silk_clearance` rule, else 0. The note MUST say which.
- The scene MUST hold every zone's outline, filled or not, on the view layer `View.ZoneEdge`, hidden when the scene opens, so that a saved fill that no longer follows its outline shows against it.
- `copper_out`: copper with no core point inside the board ring (or with all of them in a cut-out) MUST be listed once per net and cluster (items within 2 mm), with the counts per kind and the cluster's box.

#### Scenario: Corners of authored tracks
- **GIVEN** an authored design with a right-angle and an acute junction of two tracks, a 45° junction, a right-angle junction inside a pad, and a track at 30°
- **WHEN** `uv run pytest tests/unit/view/test_findings.py -k corners` builds its review
- **THEN** `corner_90` and `corner_acute` hold one item each, `track_angle` holds the 30° track, and the junction inside the pad and the 45° one are not listed

#### Scenario: Silkscreen and copper outside the board
- **GIVEN** an authored design with a silkscreen line over a pad, a text touching another text, a silkscreen line outside the board, and a via outside the board
- **WHEN** `uv run pytest tests/unit/view/test_findings.py -k silk_and_outside` builds its review with `silk_gap=150_000`
- **THEN** `silk_mask`, `silk_silk`, `silk_edge` and `copper_out` hold one item each, and every group of `GROUPS` is reported

### Requirement: Body models
`fenolite.view.meshes` SHALL tessellate a body's model with `gmsh` run as a subprocess (never imported), and `fenolite.view.models.attach_models(scene, design, models, meshes)` SHALL place each mesh on its body in the scene.
- `mesh_model(data, *, gmsh=None, cache=None, timeout=120) -> Mesh | None`:
  - it MUST write the model and a `.geo` script to a temporary folder, run gmsh with a time limit, and read the CAD X3D it writes with the standard library: positions, triangle indices and per-surface colours;
  - it MUST return `None`, and keep a failure mark in the cache, when gmsh fails, times out or writes no triangle;
  - the cache, when given, MUST key a mesh by the SHA-256 of the data and the mesher settings.
- `find_gmsh()` MUST return the command of `FENOLITE_GMSH`, else of `gmsh` on `PATH` (a launcher that is a Python script run by the current interpreter), else `None`.
- `attach_models`:
  - it MUST join a model to a body by its locator, and build the placement of "Body models" of the design;
  - it MUST compare the placed box with the body's outline box (0.5 mm) and its z range (1 mm);
  - on a match, the body MUST render the model;
  - otherwise the first of these that matches the outline's size within 1 mm, with the body on its face, MUST be kept with a note: quarter turns about the vertical through the outline's centre, then a half turn about x, each centred on the outline;
  - else the body MUST stay extruded, with the reason.
- The scene MUST hold `meshes` by SHA-256, and per body `mesh`, `m`, `render` and `fit`. The page MUST draw a body's mesh with its matrix and colours, else its extruded outline.

#### Scenario: X3D of an authored model
- **GIVEN** an authored CAD X3D of two coloured triangle sets
- **WHEN** `uv run pytest tests/unit/view/test_meshes.py -k x3d` reads it
- **THEN** the mesh holds their vertices and triangles, the colours of each set, and alpha 0 for the white set

#### Scenario: Placement and fit
- **GIVEN** a body of a top footprint whose outline is a 4 mm by 2 mm rectangle, a mesh box of 2 mm by 4 mm by 1 mm, and a model rotation of 0
- **WHEN** `uv run pytest tests/unit/view/test_models.py -k fit` attaches it
- **THEN** the body renders `fitted` with a quarter turn, and with a rotation of 90° it renders `model`

### Requirement: Measurement with snap
The page SHALL snap a measurement point to the nearest point target within 10 pixels: a pad, via, hole or arc centre, a track end, a corner of a pad or an outline. Without one, it SHALL snap to the nearest point of an edge within 10 pixels: a pad or fill border, a track border or axis, a circle, an outline. Only visible layers SHALL count, `Alt` SHALL measure without snap, and the result SHALL name what each end snapped to.

#### Scenario: Snap targets in the page
- **WHEN** `uv run pytest tests/unit/view/test_page.py -k snap` reads the page
- **THEN** the page holds the functions `buildSnap` and `snapAt`, and its measurement uses `snapAt` unless `Alt` is held

### Requirement: Findings file
`fenolite view --overlay FILE` SHALL also read a findings file of the schema `fenolite.view_overlay.v0`: groups (`id`, `title`, optional `color` and `note`) and items (`group`, `kind` of `line`, `path` or `point`, `points_nm` in the board frame of the model, `label`, optional `layer`). The page SHALL list the findings by group, each group with a box that shows or hides it and its count, and its items on demand.

#### Scenario: A findings file is drawn
- **GIVEN** a findings file with one group and one line item
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k findings_file` runs `fenolite view <board> --overlay FILE --json`
- **THEN** the exit code is 0 and `result.summary.findings` names the group with one item
