## Context

- **Request.** On 2026-10-25 the maintainer asked for a board viewer in Fenolite, in English. A user opens a project, and the viewer lists all its documents in a side panel, with the layers as tabs below the board, as the native tools do. The maintainer's own board work had a viewer of this kind for one CAD format. This design keeps its proven interaction: canvas 2D drawing, WebGL 3D, live reload, a standalone export, findings on top, and a single-stroke font. It builds the scene from Fenolite's neutral model instead of a format's records, so that any backend's boards are shown.
- **What exists** on `release-0.5.0` at `a979b412`. These are what the view needs, for both backends:
  - `backends.registry.for_path` and `Backend.read` give a `Design` for an Altium `PcbDoc` and a KiCad board.
  - `BoardFrame.board_pads` gives every pad's copper per layer in the board frame (`PadCopper`: a disc, a stroked polyline or a filled ring), its hole and its net.
  - `BoardFrame.board_edges` gives the board's rings with exact arcs.
  - The board model holds:
    - tracks, arcs (start, mid, end) and vias;
    - zones with their fills per layer, read from the file;
    - graphics and texts, and footprint graphics, texts and fields in the pad frame (`position + R(rotation)·p`);
    - component bodies with their outline, height and standoff;
    - the stack-up.
  - `backends.altium.read.project.load_project` lists a project's documents with their kinds.

  A probe of 2026-10-25 read an Altium board of 261 parts, 915 tracks, 479 vias and 88 polygons (71 with a saved fill) in 2 s. It read the authored KiCad board `tests/data/kicad/board/two_layer.kicad_pcb` with its zone fills.
- **Gaps that the view works around and states.**
  - Altium pads read without mask or paste layers (`docs/conversion.md`). The view then derives openings from the pad kinds, with no expansion, and says so.
  - Board texts carry no mirror flag. A text on a back layer is drawn mirrored.

## Goals / Non-Goals

**Goals**
- One command shows any board that Fenolite reads, and lists every document of its project, without the native tool and without a network.
- The scene is data: an agent can read the summary in the reply, and a person reads the page.

**Non-Goals**
- See the proposal.

## Decisions

1. **The package `fenolite.view`.** It holds:
   - `scene.build_scene(design, frame, *, name, data, backend, evidence) -> dict` and `scene.summary(scene)`;
   - `project.load_tree(path) -> ProjectTree`;
   - `server.Live`, `server.serve(live, port)` and `server.run(live, httpd, until=...)`;
   - `page.html` as package data;
   - `export.page(tree, scenes) -> str`.

   It imports `model`, `geometry` and `backends*` (`backends.registry`, `backends.base`, `backends.altium.read.project`) and the standard library only.
2. **The scene format, `fenolite.view_scene.v0`.**
   - **Units:** integer micrometres in the board frame of the model (origin at the outline's top-left corner, Y down).
   - **`layers`:** `{id, name, kind, side, color, visible}`, in drawing order. `id` is the model's layer name. Three view layers are added: `View.Drill`, `View.Outline` and `View.ZoneOutline`.
   - **`prims`:** `[layer, kind, data, net, comp, label]`. Each kind holds:
     - `s`: a segment `x1 y1 x2 y2 w`;
     - `a`: an arc through three points `x1 y1 xm ym x2 y2 w` (start, mid, end), as the model holds it;
     - `c`: a disc `cx cy r`;
     - `l`: a polyline of width `w`;
     - `p`: a polygon with holes, filled by the non-zero rule, and its stroke width;
     - `o`: an outline, stroked only.
   - **The rest:** `texts`, `comps`, `nets`, `board` (outer ring and inner rings), `board3d` (thickness and rings), `bodies`, `overlays` and `meta` (file, SHA-256, backend, evidence, notes).
3. **Colours.** A palette authored for Fenolite gives one colour to each layer kind and side:
   - copper front red and back blue, with inner layers from a fixed list;
   - silkscreen front yellow and back olive;
   - mask purple and dark purple;
   - paste grey;
   - courtyard, fabrication and mechanical layers from a fixed list;
   - edge pale yellow, drill dark grey.

   No vendor's scheme is copied.
4. **Pads.** Each `PadCopper` becomes one primitive:
   - a disc for one point;
   - a polyline of its width for an open core;
   - a filled polygon stroked by its width for a filled core.

   Mask and paste openings come from the pad's own mask and paste layers. When the board holds no mask layer at all, an SMD pad gets its side's mask, and a through-hole pad gets both, with no expansion and one note. Drills come from `BoardPad.hole` and `drill` (a disc, or a slot as a polyline), and from vias and board holes.
5. **Zones.** Every fill polygon becomes a `p` on its layer and net. A zone without fills puts its outline on `View.ZoneOutline` and is counted in `meta.unfilled`.
6. **Texts.** A text is drawn with Fenolite's single-stroke font: cap height `size.h`, advance `size.w` per glyph, and its justification applied. Footprint fields take their text from the component: reference, value or the named property. A field that is not visible is left out.
7. **3D.** The board is a slab of the stack-up's thickness, or 1.6 mm with a note when there is none. Its two faces are textured with the 2D drawing of that side (copper, mask, silkscreen, drills), clipped to the board by an alpha mask, so no triangulation is needed. Each body is its outline extruded from `standoff` to `height`, above the face its footprint is on.
8. **Project tree.** The source of the tree depends on what the path is:
   - **An Altium project file:** the listed documents, by kind, grouped as "Source Documents" (schematics, boards), "Libraries" (schematic, PCB and integrated libraries), "Settings" (output jobs, rules, stack-ups) and "Documentation" (drawings, annotations, BOM documents). Documents outside these groups go under "Other".
   - **A KiCad project file:** the folder's boards and schematics, the library tables, the `.pretty` folders and the rules file, grouped the same way.
   - **A folder:** its project file, when it holds exactly one, else its boards.
   - **A board:** the board alone.

   Each document holds a stable id, its path relative to the project, its kind, whether it is present, and whether it can be viewed. A path that leaves the project folder is listed and never opened.
9. **The page.** It is one HTML file with inline CSS and JS, and no external URL.
   - **Left panel:** the project tree. A board document opens on click. Any other document shows its properties: kind, path, size, SHA-256.
   - **Below it:** the findings list, and the notes of the scene.
   - **The board view, in the centre.**
   - **Bottom bar:** the layer tabs, one per layer with its colour, then the status line.
     - A click on a tab makes that layer current: it is drawn last and its tab is marked.
     - A click on the tab's swatch, or a middle click, toggles its visibility.
     - `Shift+S` toggles single-layer mode: only the current layer is shown.
     - `+` and `-` move the current layer along the tabs.
     - A layer-set menu shows all layers, signal layers, the top side, the bottom side, or the defaults.
   - **Top toolbar:** 2D/3D, fit, flip (view from below), search (a part or a net), measure, clear, the opacity of the other side.
10. **The server.** It is a `ThreadingHTTPServer` on `127.0.0.1` with these routes:
    - `/` is the page;
    - `/project.json` is the tree;
    - `/scene/<id>.json` is the scene of one document, built on first request and cached by the file's hash;
    - `/version/<id>` is the state.

    A watcher thread checks the open documents every 2 s. When a document's size and time have changed, and then stayed the same for one more check, it rebuilds that scene. The page polls `/version` and reloads the scene, keeping the view. `--port 0` takes a free port.
11. **The command.** `fenolite view PATH [--doc ID|NAME] [--overlay FILE]... [--serve [--port N] [--no-browser]] [--export FILE]`. `mutates` is true, with the reviewed-plan protocol for `--export`. Without `--serve`, the reply holds `project` (the tree), `document` (the id shown), `summary` (layers and counts per item kind) and `notes`. With `--serve`:
    - one progress record on stderr gives the URL;
    - the command serves until it is interrupted, then replies with `url` and `seconds`;
    - `--serve` and `--export` together are a usage error.
12. **Overlays.** `--overlay FILE` reads a JSON envelope of `fenolite analyze`. For each row of `result.distances` it draws the clearance path in red and the creepage path in blue, labelled with the nets and the interval in mm. A row that an `error` or `warning` issue names is marked as a finding.

## Evidence

- **Scene:** `INFERRED`. `tests/unit/view/test_scene.py` compares, on `two_layer.kicad_pcb` and on the Altium test boards `board6` and `body2`, the scene's count of each item kind with the model's: pads, tracks, arcs, vias, fill polygons, graphics, texts and bodies.
- **Page:** a person reviews it in a browser, on a KiCad and an Altium board, and the date and the browser are recorded in the tasks.

## Risks / Trade-offs

- **Large boards make large scenes.** Micrometre integers, rounded rings and per-document scenes keep a 260-part board to a few megabytes.
- **The page is code that no unit test runs.** The test checks its structure (placeholders, no external URL, the ids the script uses). The review in a browser is a task, not a claim.
