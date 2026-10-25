## 0. Entry check

- [x] 0.1 Record the parameter forms the readers give for Altium and KiCad parts. Proof: `openspec validate c0187-review-panels --strict --no-interactive`.
  - 2026-10-25, KiCad: the board reader gives a footprint's fields in `Component.properties` (`Reference`, `Value`, `Datasheet`, `Description` and user fields).
  - 2026-10-25, Altium: the board reader gives no parameters, so the census looked at the records themselves. The 961 `Components6` records of the eight public boards hold the source keys, plus optional `SOURCEDESCRIPTION` (822), `FOOTPRINTDESCRIPTION` (811), `HEIGHT` (777) and library identifiers. None holds a user parameter; those stay on the schematic part.
  - The census is recorded in `docs/formats/altium/pcb-document.md` (CORPUS-VERIFIED, H-A-PCB-DOC-OPEN).
  - Design decision 4 follows from it.
  - Branch `c0187-review-panels`, from `c0186-variants-view`. Proof passed.

## 1. Panels and filter

- [x] 1.1 Parameters and routed lengths in the board scene. Proof: `uv run pytest tests/unit/view/test_scene.py -q`.
  - 2026-10-25: proof passed (7).
  - Scene parts carry `params`, and an Altium part carries `uid`.
  - `netinfo` gives each net its pad count and its routed length in µm. Its arcs use `geometry.arc_length`.
  - `project_nets.sheet_params` adds the schematic part's parameters on a board of an Altium project (`test_project_nets.py`).
- [x] 1.2 The query parser and the Nets and Components panels (scenario "Parts of a footprint on the bottom"). Proof: `uv run pytest tests/unit/view/test_filter.py -q`.
  - 2026-10-25: proof passed (2). The page's query functions run in Node on an authored scene; the test covers and, or, not, quoted layer names, a parameter key, a bare word and Find similar.
- [x] 1.3 Highlight modes and Find similar. Proof: `uv run pytest tests/unit/view -q`.
  - 2026-10-25: proof passed (80).
  - Highlight modes: Dim, Mask and Normal (others at 28 %, 6 % and 100 %), remembered in the browser. `Shift+C` clears.
  - Parameters that are web addresses become links (`rel="noopener noreferrer"`).

## 2. Closing

- [x] 2.1 Browser review on S-0187's board: panel speed and a filter. Proof: the record under this task.
  - 2026-10-25, the agent, in the Chromium of the container (Playwright, headless), on `DM3370.PcbDoc`: 544 parts, 427 nets, 39 407 primitives.
  - **Speed:** both panels built in 28.5 ms (the budget is 100 ms). `footprint:*0402* side:bottom` ran in 41.5 ms and found 106 parts and 2 332 primitives.
  - **Net:** selecting GND from the Nets panel took 170 ms, zoom and redraw included, and read `604 pads · routed 496.390 mm`.
  - **Find similar:** on U26 it gave `footprint:"LuxonisMaster:BNO085" value:"BNO085"`, which found 1 part.
  - **Properties:** they list the description, library keys, path, height (now in the page's unit: 1.180 mm) and lock.
  - **Mask:** the board around the part nearly disappears.
- [x] 2.2 Docs, fast gate. Proof: `make check-fast`.
  - 2026-10-25: proof passed (13 927 passed, 34 skipped).
  - Changed: `docs/viewer.md` ("Reviewing a board: filter, panels and parameters"), the census row and the LEGAL-ANNEX row.
  - No command, argument or FEN code changed, so the agent guide is unchanged.
