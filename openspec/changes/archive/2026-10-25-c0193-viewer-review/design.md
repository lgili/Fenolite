## Context

- **Request.** On 2026-10-25 the maintainer compared c0176's viewer with the one of his own board work, and asked for every function and check that c0176 left out:
  - the 3D models;
  - corners, silkscreen, copper outside the board and copper islands drawn on the board;
  - a measurement with snap.
- **What exists** on `c0176-board-viewer` at `36b3767b`:
  - The scene (`fenolite.view.scene`) holds bodies as extruded outlines, and overlays from an `analyze` reply.
  - The page draws the overlays as one flat list.
  - `analysis.connectivity.connectivity` gives each net's islands and its open connections, between the nearest anchors (`KICAD-VERIFIED`, `H-K-CONN-PARITY`).
  - `geometry` gives thick shapes with exact gaps (`thick_closer_than`, `thick_witness`), point-in-ring tests and a spatial index.
  - The Altium reader keeps the `Models` storage among the document's storages. `docs/formats/altium/pcb-bodies.md` records `MODELID` as naming an entry of `Models`, and says that the `MODEL.2D.*` and `MODEL.3D.*` keys are not typed.
- **Gaps.**
  - The model carries no solder-mask expansion and no Altium silkscreen rule. The silkscreen findings take their two gaps from the options, or from a `silk_clearance` rule of the design, and the note states which.
  - The model carries no 3D model data (`ComponentBody`: "No model data is carried"). The models come through a backend protocol that reads the file, as a backend's board frame gives what the model does not hold.

## Goals / Non-Goals

**Goals**
- Every review aid of the request, drawn on the board as groups of findings that a person can show, hide and step through.
- The 3D view of an Altium board with its embedded models, placed as the native tool places them.

**Non-Goals**
- See the proposal.

## Decisions

1. **Review findings, `fenolite.view.findings`.** The module imports `model`, `geometry` and `backends.base` only; it is pure, and lengths are nanometres. `review(design, frame, *, silk_gap, mask_expansion) -> Review` returns overlay items and group records:
   - **Corners.**
     - **Two free tracks.** Two tracks of one copper layer that share an end point, and no third item ending there, form a corner.
     - **Inside a pad.** A corner whose point lies in a pad's copper on that layer is left out: the pad hides it.
     - **The turn.** It is classed by the exact sign of the dot product of the two directions: acute (above 90°), right (90°), or in-between (above 45°, below 90°). A turn of 45° or less passes. Right turns are listed apart: a straight track may turn 90° on purpose.
     - **Off-angle tracks.** A track whose direction is more than 0.5° from a multiple of 45° is listed (an Altium length unit is 2.54 nm, so a test in nanometres would list short tracks one unit off).
     - **Zone outlines.** A vertex with an interior angle below 134° (a turn above 46°, one degree for rounded chamfers) is listed when a fill of the zone covers it, or when the zone has no fill, and it is not inside a pad.
   - **Silkscreen.** The items are graphics, texts and visible fields on a silkscreen layer, as thick shapes. A text is the box of its ink, from its size, stroke and justification, as the page draws it.
     - **Openings.** The mask openings are the pads' copper on the side's copper layer, grown by `mask_expansion`, and the untented vias.
     - **Three findings:** an item closer than `silk_gap` to an opening; a text closer than `silk_gap` to another item of its side; and an item with a core point outside the board ring, inside a cut-out, or closer than `silk_gap` to an edge.
     - **The place** of a finding is `thick_witness`.
   - **Copper outside the board.** It covers every pad copper entry, track, arc, via and fill polygon with no core point inside the board ring, or with all of them in a cut-out. Such items are grouped by net, and by clusters joined within 2 mm. Each cluster is one finding with its counts and its box.
   - **Groups.** Each group has an `id`, a `title`, a `color` and a `note` that names its rule and its model. Every group is reported, so a zero is a result.
2. **Open connections.** The view package may not import `analysis` (`package-layering`). `cmd_view` calls `connectivity(design, pads=frame.board_pads(design))`. Each `OpenConnection` becomes a line between its two anchors, labelled with the net, the two ends and the length. Nets whose name matches `GND|GROUND|VSS|EARTH|0V|PE|FE|COM` as a word go to the group `open_ground`; the others go to `open_net`.
3. **Overlay items.** The scene's `overlays` holds items `{group, kind, pts, label, layer, color, bbox?}`:
   - `kind` is `line`, `path` or `point`;
   - `pts` are micrometres;
   - `meta.findings` lists the groups.

   An `analyze` reply gives the groups `analyze_clearance` and `analyze_creepage`. A findings file gives its own groups.
4. **Findings file, `fenolite.view_overlay.v0`.** `{"schema": "fenolite.view_overlay.v0", "groups": [{id, title, color?, note?}], "items": [{group, kind, points_nm: [[x, y], ...], label, layer?}]}`, in the board frame of the model (nanometres, Y down). A file that is neither an `analyze` reply nor this schema is `FEN-3004`.
5. **Body models, `BodyModelSource`.** It is a protocol of `backends.base`:

   ```python
   body_models(path: Path) -> tuple[BodyModel, ...]
   ```

   `BodyModel` holds:
   - `locator`: the provenance locator of the body it belongs to;
   - `name` and `format` (`step`);
   - `data`: the model file's bytes;
   - `position`: the board frame of the model, nanometres;
   - `z`: nanometres from the face its footprint is on;
   - `rotation`: three angles in microdegrees, about x, then y, then z, in a frame of the top face with x to the right, y the board frame's −y (up as the board is seen from the top), and z out of the top face.

   The side is the footprint's. The placement of a model point `p` (millimetres) in the page's 3D frame (x and −y of the board frame, z up from the bottom face) is `T(position, face ± z) · F(side) · Rz · Ry · Rx · p`. `F` is the identity on the top. On the bottom it is a half turn about the x axis (the corpus measure of task 1.1: 181 of 181 bottom bodies match with x, 151 with y), and the model hangs below the bottom face.
6. **Altium models, `backends.altium.models3d`.**
   - **Records.** `Models/Data` is a run of records, each a 32-bit length and a property text. Record `n` names stream `Models/<n>`, which holds the model as zlib-compressed data.
   - **Matching a body.** A body with `MODEL.MODELTYPE=1` names a record by `MODELID`.
   - **Placement.** It reads `MODEL.2D.X` and `MODEL.2D.Y` (the position, as the units module turns any point: Y negated), `MODEL.3D.DZ` (the height) and `MODEL.3D.ROTX`, `ROTY` and `ROTZ`.
   - **Facts and evidence.** These go on the fact page, measured on the corpus (task 1.1).
7. **Meshes, `fenolite.view.meshes`.**
   - **The run.** `gmsh` runs once per model, in a temporary folder and with a time limit, on a `.geo` script:
     - it merges the model with labels and target unit mm;
     - it meshes the surfaces with a size from the model's box (as the maintainer's viewer did: 10, 16 or 24 elements per turn below 5, 15 mm and above);
     - it saves CAD X3D with one shape per surface (`Print.X3dSurfaces = 2`, `Print.X3dColorize = 1`).
   - **Reading the X3D.** The standard library's XML parser reads it. A white or missing colour means "no colour in the model".
   - **The mesh.** `{v, i, c, bbox, tri}`: base64 float32 positions, uint32 indices, uint8 RGBA per vertex (alpha 0 for no colour), the box, the count.
   - **Cache.** Meshes are kept in `state_dir()/view-meshes/<sha256 of data and settings>.json`, and a failure is kept as `.failed`. With the state folder `off`, nothing is kept.
   - **Locating gmsh.** It is `FENOLITE_GMSH`, else `gmsh` on `PATH`. A launcher that is a Python script runs with the current interpreter. No gmsh module is imported.
8. **Placing meshes, `fenolite.view.models`.** `attach_models(scene, design, models, meshes)` joins each model to its body by the locator.
   - **The matrix.** It builds the placement, then compares the placed box with the body's outline box (0.5 mm) and its z range (1 mm).
   - **A match.** The body is drawn with the model (`render = "model"`).
   - **No match.** The first fit that matches the size within 1 mm, with the body above its face, is kept (`render = "fitted"`, with a note). The fits tried are quarter turns about the vertical through the outline centre and a half turn about x, then centring on the outline.
   - **Else** the body stays extruded, with the reason.

   The scene gains `meshes` (by SHA-256) and, per body, `mesh`, `m` (the column-major matrix), `render` and `fit`.
9. **The page.**
   - **Findings panel.** One row per group: a box that shows or hides the group, the title, the count; a click opens its items. A click on an item fits the view to it and shows its group's note.
   - **Snap.** Snap targets are built from the visible layers into a grid of 2 mm cells. A point within 10 px wins (a centre, an end, a corner); else the nearest point of an edge (a pad or fill border, a track border or axis, a circle, an outline). `Alt` turns snap off.
   - **3D.** A second shader program draws each mesh with its matrix and per-vertex colour, falling back to the body colour.
10. **The command.**
    - **Options:** `--no-review`, `--no-models`, `--silk-gap MM`, `--mask-expansion MM`.
    - **When models are meshed.** With `--serve` the models are meshed in a background thread after the first scene, and the page reloads when they are ready. With `--export` they are meshed before the page is written. The summary-only form meshes nothing.
    - **The reply** carries `summary.findings` (count per group) and `summary.models` (counts by render).
    - **A port in use** is `FEN-2001`, with the hint `--port 0`.
11. **Capabilities.** `detect_tools` probes `gmsh` with `-version`.
12. **Texts of an Altium board.** The Altium import gives a stroke text its record's point as position, centred, with a width equal to its height. The text record's anchor is its lower-left corner (`pcb-records.md`, the row of `H-A-PCBX-KICAD`, oracle-verified), and the Altium writer pairs with the import: it writes a centred text at its position and refuses any other justification. Changing the import would change what the writer and the KiCad conversion do, so it is not this change's (a finding for a later one).
    - **The view.** The scene and the review draw a text of an Altium board at its lower-left corner, with a glyph two thirds of its height, and the notes say so.
    - **Why two thirds.** The advance of Altium's stroke font is about the height: the stored text boxes of 1095 stroke texts of the eight public documents give a median of 0.979 of the height, and at most 1.0 (task 1.1, `pcb-records.md`).
    - **Measured effect.** On a 260-part board the silkscreen findings fell from 325 and 264 to 29 and 19, and those left include each overlap a review in the native tool had found.

## Evidence

- **Review findings:** `INFERRED`. `tests/unit/view/test_findings.py` builds authored designs, one per group, and pins the findings. `tests/unit/cli/test_view_cmd.py` pins the open connections against `connectivity`.
- **Placement:** task 1.1 records the corpus count on the fact page, with the hypothesis `H-A-BODY-MODEL-PLACE`.
- **Meshes:** `tests/unit/view/test_meshes.py` parses an authored X3D. Where gmsh is installed, it meshes an authored STEP box and checks its box.

## Risks / Trade-offs

- **gmsh is slow on large assemblies.** One process per model, a time limit and a cache keep the page usable. A model that fails or times out leaves its body extruded and is counted.
- **Size.** A board with a hundred models adds megabytes of meshes. The mesh size follows the part size, and meshes are shared by SHA-256.
- **White surfaces.** A surface coloured white in the model takes the body colour; X3D gives no other mark of "no colour".
