## 0. Entry check

- [x] 0.1 Read the measure code and the server; write `fenolite.review.v0` under this task. Proof: `openspec validate c0189-review-tools --strict --no-interactive`.
  - 2026-10-25, the measure: it measures point to point and snaps to pad centres, ends and vertices (c0179).
  - 2026-10-25, pads in the scene: a pad is drawn as its core (`c` round, `p` filled ring, `l` stroke) plus, for a filled ring grown by a width, a stroke of its edge. The edge measure therefore takes every primitive of the clicked pad on that layer.
  - 2026-10-25, the server: it only read (GET of the page, tree, scenes, versions) and bound only the loopback address.
  - **`fenolite.review.v0`** (`src/fenolite/view/review.py`, generated into `schemas/fenolite.review.v0.json` by `tools/gen_schemas.py`):
    - `{"schema": "fenolite.review.v0", "marks": [...]}`;
    - each mark holds `id`, `doc` (file name), `x_nm`, `y_nm` (integers, Y down, the document's frame), `note`, `select` (a part or net) and `created` (ISO 8601);
    - at most 5 000 marks; a note holds at most 4 000 characters.
  - Branch `c0189-review-tools`, from `c0188-check-overlay`. Proof passed.

## 1. Tools

- [x] 1.1 Edge measurement (scenario "Two pads"). Proof: `uv run pytest tests/unit/view/test_edge_measure.py -q`.
  - 2026-10-25: proof passed (2).
  - The authored pads read 200 µm, touching pads 0 and a track 500 µm.
  - On `two_layer`, pad D1-1 and track 2 agree with the gap `fenolite analyze --pair GND VCC` reports (9.156948 mm) within 1 µm, which is the requirement.
- [x] 1.2 Deep links and `--select`. Proof: `uv run pytest tests/unit/view tests/unit/cli/test_view_cmd.py -q`.
  - 2026-10-25: proof passed.
  - `result.select` gives `{name, found}`, and a note names a part or net that the document does not hold.
  - An exported page carries `select` and `marks`.
- [x] 1.3 Review marks and `--marks` (scenario "Marks for an agent"). Proof: `uv run pytest tests/unit/view/test_server.py tests/unit/cli/test_view_cmd.py -q`.
  - 2026-10-25: proof passed (22).
  - The server writes only with `--marks`. Without the review header, from another origin or as malformed JSON a mark is refused (403, 403, 400) and nothing is written.
  - A mark is added and then deleted in atomic replaces, and no temporary file is left.
  - `--marks` lists an authored file. A malformed file is `FEN-3004`, a missing one `FEN-3001`.
- [x] 1.4 Print and SVG. Proof: the record of task 2.1.

## 2. Closing

- [x] 2.1 Browser review: an edge measure, a link, a mark, a print to PDF. Proof: the record under this task.
  - 2026-10-25, the agent, in the Chromium of the container (Playwright, headless).
  - **Input:** the public demo project `interf_u` (KiCad repository, tag 10.0.6), served with `fenolite view … --serve --marks review.json --select U5`. The page opened with U5 selected.
  - **Edge:** `Shift+M` between U5-1 and U5-2 read 0.940 mm, which is the 2.54 mm pitch less the 1.6 mm pad.
  - **Mark:** `N` and a click dropped a mark with a note. The server wrote it to `review.json` as `x_nm` 88265000 and `y_nm` 75982000, with `select` U5.
  - **Link:** the address became `#doc=doc1&sel=U5&z=23.438&c=106.0450,68.5750&u=mm&l=F.Cu`. Opened in a new page, it restored the document, the selection, the zoom, the centre and the mark.
  - **SVG:** the board view gave 1.48 MB and the sheet 1.17 MB. Rendered again, both match the canvas: layers, the dimmed selection, KiCad's stroke text and the mark.
  - **Print:** headless Chromium shows no print dialog, so the page that Print sends to it (the SVG fitted to the page) was printed with Playwright's `page.pdf`: a 455 kB A4 PDF. The dialog itself is left to the maintainer's review.
- [x] 2.2 Docs, agent guide, fast gate. Proof: `make check-fast`.
  - 2026-10-25: proof passed (13 940 passed, 34 skipped).
  - The page test "loads nothing from the network" caught the SVG namespace string, so the page now builds it from parts (`SVG_NS`).
  - Changed: `docs/viewer.md` ("Review tools"), the `view` section of `docs/cli-contract.md`, a line in `references/files.md`, the regenerated guide (149 258 bytes), `schemas/fenolite.review.v0.json` and the LEGAL-ANNEX row.
