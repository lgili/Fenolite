## 0. Entry check

- [x] 0.1 Count the keep-outs, room rules and dimension records of the public boards; record the forms of `Dimensions6` if any board holds one. Proof: `openspec validate c0183-board-rule-areas --strict --no-interactive`.
  - 2026-10-25: six boards (`-pcbdoc-01` to `-04`, `-06`, `-07`) were fetched with `tools/corpus_fetch.py`, giving all 8 public Altium boards.
  - **Rooms and dimensions:** no board holds a `RoomDefinition` rule. Every `Dimensions6` is empty (a 4-byte `Header`, no `Data`). `H-A-ROOM` is registered as `UNKNOWN`.
  - **Model keep-outs:** none of the 8 boards gives a model keep-out.
  - **Keep-Out Layer (56):** objects are on 5 boards:
    - free tracks and arcs (12 and 8 on `-01`);
    - free regions with `KEEPOUT=TRUE` and `ISBOARDCUTOUT=TRUE` (board cut-outs, already the outline's);
    - regions of a part (`-04`, `-06`).
  - All Altium courtyards are made from pad copper (`placed_extents` source `pads`).
  - The rows are in `pcb-document.md`. The branch is `c0183-board-rule-areas`, from `c0182-viewer-performance`. Proof passed.

## 1. Scene

- [x] 1.1 Draw keep-outs (scenario "An authored keep-out"). Proof: `uv run pytest tests/unit/view/test_board_annotations.py -k keepout -q`.
  - 2026-10-25: proof passed. A new primitive kind `h` (hatched ring) is drawn by the page with 45° lines clipped to the ring; v1 encodes it like `p`.
- [x] 1.2 Draw rooms and dimensions as the facts of 0.1 allow. Proof: `uv run pytest tests/unit/view/test_board_annotations.py -q`.
  - 2026-10-25: proof passed. The model's dimensions are drawn; `dimension.kicad_pcb` reads `30.0000 mm`, with its line 3 mm below the points. Altium rooms and dimensions are left to `H-A-ROOM`: no public record exists.
- [x] 1.3 Mark courtyard overlaps (scenario "Two overlapping parts"). Proof: `uv run pytest tests/unit/view/test_board_annotations.py -k overlap -q`.
  - 2026-10-25: proof passed (exact courtyards are marked; extents made from pads are a note).
  - **Why the change:** on the public boards every overlap is "approximate extent", e.g. a capacitor inside a crystal's pad hull, so the first version would have shown false conflicts. They are now counted: 5, 1 and 4 on `-01`, `-04` and `-08`. `tests/corpus/test_board_annotations_public.py` fixes the counts.

## 2. Closing

- [x] 2.1 Browser review of a public board with keep-outs. Proof: the record under this task.
  - 2026-10-25, the agent, in the Chromium of the container (Playwright, headless), on exported pages.
    - **`two_layer.kicad_pcb`:** the rule area is hatched on F.Cu.
    - **`dimension.kicad_pcb`:** the dimension and its value `30.0000 mm`. The first screenshot showed nothing, because `Dwgs.User` was hidden by default; a layer that holds a dimension is now shown.
    - **`-06`:** a part's keep-out region is hatched on the Keep-Out Layer, which was hidden by default and is now shown, as in Altium.
- [x] 2.2 Docs, `LEGAL-ANNEX.md` row, fast gate. Proof: `make check-fast`.
  - 2026-10-25: proof passed (13 911 passed, 34 skipped). `docs/viewer.md` gained "Keep-outs, dimensions and placement marks".
