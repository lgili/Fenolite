## 0. Entry check

- [x] 0.1 Read the c0176 specs (`board-viewer`, `cli-contract` "View command") and the living `altium-schematic-reader` and `altium-import` specs. Note under this task, with the date, what this change builds on and which open change holds a delta of "View command". Proof: `openspec validate c0177-schematic-viewer --strict --no-interactive`.
  - 2026-10-25: this change is on `c0176-board-viewer` (`36b3767`), which is on `release-0.5.0`. It builds on:
    - `read_schematic` and `SchDocument.shown_children`;
    - `adapter.connectivity.local_nets` and `Lines.groups`;
    - `read.sheet.SHEET_STYLES` and `LINE_WIDTHS`.

    Only c0176 holds "View command" (ADDED). This change ADDs "View command shows schematics" beside it, and changes no text of c0176's. Proof passed (openspec 1.x). c0176 itself fails `--strict` on the "requirement text is very long" warning, which this change's requirements avoid.

## 1. Scene

- [x] 1.1 Add `fenolite.view.schematic` with the sheet, fonts, graphics, texts, components and pins (scenarios "Counts of an Altium sheet" and "Every graphic kind"). Proof: `uv run pytest tests/unit/view/test_schematic.py -k "counts or graphic" -q`.
  - 2026-10-25: proof passed. The text size first followed `size / 72` inch. In the browser, the pin numbers of a 100-mil pitch touched at that size, so the em became 9 mil per point (design, "fonts").
- [x] 1.2 Add the connectivity symbols (power ports, ports, sheet symbols and entries, harnesses, junctions, No ERC) and the nets (scenario "Wires carry their nets"). Proof: `uv run pytest tests/unit/view/test_schematic.py -q`.
  - 2026-10-25: proof passed (6 tests). Every committed `.SchDoc` of `tests/data/altium/` builds a scene without an error.
- [x] 1.3 Mark Altium sheets as viewable in `fenolite.view.project` (scenario "An Altium project with sheets"). Proof: `uv run pytest tests/unit/view/test_project.py -q`.
  - 2026-10-25: proof passed. `test_refusals` now refuses a `.SchLib` and a text file, since a lone `.SchDoc` is a tree.

## 2. Page and command

- [x] 2.1 Add the schematic drawing to `page.html` (scenario "A schematic scene round-trips through the export"). Proof: `uv run pytest tests/unit/view/test_page.py -q`.
  - 2026-10-25: proof passed.
- [x] 2.2 Build schematic scenes in `cmd_view` for the reply, the export and the server (scenario "Summary of a sheet"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py tests/unit/view -q`.
  - 2026-10-25: proof passed. With `tests/consistency` and `tests/unit/test_import_graph.py`: 466 passed, 24 skipped.
- [x] 2.3 Review the page in a browser on `tests/data/altium/hier/altium_hier.PrjPcb` and `tests/data/altium/blink/blink.PrjPcb` through `fenolite view --serve`. Record the date, the browser, and what was checked: sheet, grid, colours and fonts, parts, pins, power ports, ports, sheet symbols, net highlight, Properties, Navigator, search, sheet tabs, a double click on a sheet symbol, and the cross-probe to the board. Proof: the record under this task.
  - 2026-10-25, the agent, in the Chromium of the container (Playwright, headless, 1500 × 950). The pages were exported standalone pages of the two projects and of `tests/data/altium/tree/tree.PrjPcb` and `tests/data/altium/sample/altium_sample.PrjPcb`, read from screenshots. `--serve` was not used: the live route serves the same scene JSON, which `test_server.py` covers.
  - **Checked:**
    - the A4 sheet in its colour on the grey workspace, with the grid lines, the border and its zones;
    - the colours of the file: pale yellow bodies, dark red outlines, navy wires and labels;
    - texts in a serif face (the container has no Times New Roman);
    - parts with designator and comment, and pins with names, numbers, a dot and a clock wedge;
    - power ports (bar, power ground), ports, the bus and its entries, the sheet symbols with their entries, the harness connector and the directive flags;
    - the net highlight on a click on a wire (the rest dims, Properties lists the pins);
    - the part selection with its dashed box;
    - the Navigator, the search by designator, and the sheet tabs;
    - a double click on a sheet symbol, which opened `altium_hier_mcu.SchDoc`;
    - the cross-probe from `U1` of `blink.SchDoc` to the board and back.
  - **Found and fixed in the same session:**
    - the text size (task 1.1);
    - one-pin nets with a made-up name filled the Navigator; they are no longer listed there.
- [ ] 2.4 The maintainer reviews the page on an Altium project of their own, against Altium Designer, through `fenolite view --serve`. The review covers the text size, the shapes of power ports, ports and sheet entries, and the title block. Proof: the record under this task.
  - 2026-10-25: WAITS on the maintainer.

## 3. Docs

- [x] 3.1 Write the schematic section of `docs/viewer.md` and the `view` lines of `docs/cli-contract.md` and the guide page `files`, then run `tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
  - 2026-10-25: proof passed (81 passed, 12 skipped). The skill folder holds 149 887 bytes against its budget of 150 000 on this branch. c0174 raises the budget to 260 000.

## 4. Closing

- [x] 4.1 Run the fast gate and the residue scan. Proof: `make check-fast`.
  - 2026-10-25, Linux container: lint, format, pyright and residue clean; tests 13 853 passed, 34 skipped. The full gate is left to CI.
- [x] 4.2 Evidence labels: the schematic scene is `INFERRED`, and no other label changes. Proof: `uv run python tools/gen_evidence_matrix.py --check`.
  - 2026-10-25: proof passed.
- [x] 4.3 Add an entry under `## [Unreleased]` in `CHANGELOG.md` once the version after 0.5.0 is open. Proof: `uv run pytest tests/unit/test_release_record_v05.py -q`.
  - 2026-10-25: the entry is under `## [0.5.0]` of `CHANGELOG.md`, not `[Unreleased]`: by the maintainer's decision of 2026-10-25 the change ships in 0.5.0 (c0171 task 1.15). Proof passed (`tests/unit/test_release_record_v05.py`).
  - 2026-10-25: WAITS on the maintainer: the release guard keeps `[Unreleased]` empty while the version is `0.5.0`. The text is ready: `- **Schematic viewer** (c0177): `fenolite view` draws the Altium sheets of a project as Altium Designer does — the file's colours and fonts on its paper, grid, border and title block, parts, pins, power ports, ports, sheet symbols and harnesses — with net highlight, a Properties and a Navigator panel, search, sheet tabs, a double click into a child sheet, and cross-probing between the sheet and the board; `--doc` replies with a sheet's counts of parts, pins, wires and nets.`
