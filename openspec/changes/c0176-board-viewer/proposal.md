## Why

The maintainer's request of 2026-10-25. A user often holds a board or a whole project from a tool they do not have installed: an Altium project on a machine without Altium, or a KiCad board in a review meeting. Fenolite reads and judges those files, but cannot show them. `fenolite render` needs `kicad-cli` and a KiCad board, and `region`, `net` and `pads` answer in text. In the maintainer's board work a viewer was used at every review step: a region before routing, a pour after a refill, a net, a finding of `analyze`, the board turned over, part heights in 3D. It should feel like the native tools: the project's documents in a side panel, and the layers as tabs below the board.

## What Changes

- **Package `fenolite.view`, standard library only.** It reads any board a backend reads (Altium `PcbDoc`, KiCad `.kicad_pcb`) through the neutral model and the backend's `BoardFrame`, and builds a plain JSON scene. The scene holds layers, pads, tracks, arcs, vias, zone fills (or outlines), graphics, texts, fields, holes, the outline, cut-outs, components, nets and part bodies. No tool runs, and no connection opens.
- **Project tree.** An Altium `.PrjPcb`, a KiCad `.kicad_pro`, a folder or a single board becomes a tree of documents, grouped as the native tools group them: source documents, libraries, settings, documentation and other. Each document says whether it can be viewed.
- **Packaged web page** (canvas 2D and WebGL, no external library):
  - the project tree on the left;
  - layer tabs along the bottom: current layer, visibility, single-layer mode, layer sets;
  - Top and Bottom views, net and component highlight, search and measurement;
  - findings on top, and a 3D view with extruded bodies;
  - stroke text in Fenolite's own font.
- **`fenolite view PATH`.** It is read-only by default and replies with the tree and a scene summary.
  - `--serve` starts a server on `127.0.0.1` that reloads the page when a document is saved.
  - `--export FILE.html` writes one standalone page under the mutation protocol.
  - `--overlay FILE` draws the distance findings of an `analyze` reply.
- **Docs.** `docs/viewer.md`, a `view` section in `docs/cli-contract.md`, and a tested line on the guide page `files`.

## Capabilities

### New Capabilities

- `board-viewer`: the scene, the project tree, the page, the server and the export.

### Modified Capabilities

- `cli-contract`: ADDED "View command".
- `package-layering`: MODIFIED "Allowed import edges" (the package `view`).

## Non-goals

- Editing: the viewer writes no design file.
- A schematic view or a library browser in this change. Such documents are listed in the tree, with their kind and hash, as not viewable yet.
- STEP meshing: bodies are extruded from their outline and heights.
- Pour simulation: a zone without a fill shows its outline, and the page says so.
- Any vendor's layer colours: the palette is authored for Fenolite.
- Any traffic off the machine: the server binds the loopback address only.

## Evidence level required

- **Scene:** `INFERRED`. Benches compare the scene's count of every item kind with the model's, on the authored KiCad and Altium boards of the test data.
- **Page:** a test checks that the page holds no external URL and that a scene round-trips through the export. A person's review of the drawing in a browser is recorded, not automated.

## Impact

- **New:** `src/fenolite/view/` (`scene.py`, `project.py`, `server.py`, `page.html`), `src/fenolite/cli/cmd_view.py`, `docs/viewer.md`, `tests/unit/view/`.
- **Changed:** `tests/unit/test_import_graph.py`, `docs/cli-contract.md`, the guide page `files` and the generated pages.
- **Size:** 6 design-days.
