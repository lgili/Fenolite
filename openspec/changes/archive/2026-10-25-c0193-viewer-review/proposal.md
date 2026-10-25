## Why

The maintainer's request of 2026-10-25, after change c0176. The board viewer of c0176 came from a viewer of the maintainer's own board work. That viewer had review aids that c0176 left out, and the maintainer asked for every one of them in Fenolite:
- the board's 3D models instead of extruded blocks ("the 3D must look as it does in the native tool, else it makes no sense");
- review findings drawn on the board: corners against the 45° rule, silkscreen against the mask, the edge and other silkscreen, copper outside the board, and copper islands;
- a measurement that snaps to centres, ends, corners and edges.

The native tool shows all of these. c0176's non-goals named STEP meshing; this change lifts that one.

## What Changes

- **Review findings** (`fenolite.view.findings`, model, geometry and backends only).
  - Corners: two free tracks meeting at an end with an acute, a right or an in-between turn; a track off the 45° directions; a zone outline vertex sharper than 45°, where the zone has copper.
  - Silkscreen: closer than a gap to a mask opening; text closer than a gap to other silkscreen; outside the board or nearer its edge than a gap.
  - Copper outside the board, one finding per net and cluster.
  - Each finding is an overlay item of a group, with a label and its place. Each group states its rule and its model.
- **Open connections on the board.** `fenolite view` draws `analysis.connectivity`'s open connections, one line between the two nearest anchors of two islands. Nets named as grounds have a group of their own.
- **Body models in 3D.**
  - A backend protocol, `BodyModelSource.body_models(path)`: each body's embedded model (format, bytes) and its placement (position, height, three rotations, side).
  - The Altium backend reads its `Models` storage and the body records.
  - `fenolite.view.meshes` tessellates a STEP model with `gmsh`, run as a subprocess (an external tool, GPL, never imported). It reads the CAD X3D that gmsh writes, with the model's own surface colours, and keeps the meshes in the state folder by SHA-256.
  - The scene places each mesh by the body's placement. A placement that disagrees with the body's stored outline and heights is fitted by quarter turns, a turn-over and a centring, or the body stays extruded. The page draws the meshes.
- **Measurement with snap.** The cursor snaps to pad, via, hole and arc centres, track ends, corners, then the nearest point of an edge; `Alt` measures without it.
- **Findings panel by group**, each with a show/hide box and a count, and its items listed.
- **`--overlay` also reads a findings file**, `fenolite.view_overlay.v0`: groups and items in the board frame, for findings of other tools.
- **`fenolite view` options:**
  - `--no-review` and `--no-models`;
  - `--silk-gap MM` and `--mask-expansion MM`, stated assumptions for boards whose silk and mask rules the model does not carry;
  - a port in use is a usage error with a hint.

  `fenolite capabilities` lists `gmsh`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `board-viewer` (open change c0176): ADDED "Review findings", "Body models", "Measurement with snap", "Findings file".
- `cli-contract`: ADDED "View command review and models".
- `altium-import`: ADDED "Embedded body models".

## Non-goals

- Pour simulation: a zone without a fill still shows its outline. A fill saved before the board changed is drawn as saved.
- KiCad body models in this change: the KiCad backend does not implement `BodyModelSource` yet. Its bodies stay extruded, and the notes say so.
- A design rule check: the review findings are aids, not a DRC. `fenolite check` and the native tool stay the judges.
- Importing gmsh, or any GPL code: gmsh runs as a separate process only.

## Evidence level required

- **Review findings:** `INFERRED`. Benches on authored designs pin each group, and a test pins the open connections against `analysis.connectivity`.
- **Altium placement of an embedded model:** measured on the eight public PCB documents of the corpus. For each body that names an embedded model, the placed model's box must match the stored outline and heights. The fact page records the count; the label is `CORPUS-VERIFIED` when every body matches or each exception is explained, else `INFERRED`.
- **Meshes:** `INFERRED`. A test parses an authored X3D; the gmsh run is tested where gmsh is installed.

## Impact

- **New:** `src/fenolite/view/findings.py`, `src/fenolite/view/meshes.py`, `src/fenolite/view/models.py`, `src/fenolite/backends/altium/models3d.py`, `tests/unit/view/test_findings.py`, `tests/unit/view/test_meshes.py`, `tests/unit/view/test_models.py`.
- **Changed:**
  - `backends/base.py` and `backends/altium/backend.py`;
  - `cli/cmd_view.py` and `cli/cmd_capabilities.py`;
  - `view/page.html`;
  - `docs/viewer.md`, `docs/cli-contract.md`, `docs/formats/altium/pcb-bodies.md` and `docs/hypotheses.md`;
  - the guide pages.
- **Size:** 4 design-days.
