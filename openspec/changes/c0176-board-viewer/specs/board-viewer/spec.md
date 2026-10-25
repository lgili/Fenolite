## ADDED Requirements

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
