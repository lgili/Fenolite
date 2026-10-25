## 0. Entry check

- [x] 0.1 Measure the public `.BomDoc` and the side views of S-0786; record the facts. Proof: `openspec validate c0190-documentation-views --strict --no-interactive`.
  - 2026-10-25, the `.BomDoc`: the repository of S-0786 holds `PiDP11IOExpander.BomDoc` as a Git object, not LFS (258 837 bytes). It is registered as S-0815 and read from a scratch folder, never committed.
    - **Form:** text, one `|RECORD=…|KEY=VALUE` record per line, 301 records of 21 kinds.
    - **Contents:** the BOM's settings and its catalog (25 `CatalogItem`, each with its `Solution`), plus 12 manual `Item` lines. No record lists the design's parts.
    - **Where recorded:** the new page `docs/formats/altium/bom-document.md`, under `H-A-PRJ-BOMDOC` (INFERRED).
  - 2026-10-25, the side views: the only side views of the four public drawings are the Right and Front views of S-0786's assembly drawing. The only callout is in its fabrication drawing, which the reader used to skip.
    - **Frames:** the document stores them (`BoardBoundsBack`, `BoardBoundsRight`), and part types carry `Height` and `MinZ`.
    - **Front view:** its dimension spans the frame exactly at both ends.
    - **Right view:** one dimension point lands on its part; another lands 3.3 units off.
    - **Callout:** it names note element 9 (border `Square`) by id.
    - **Where recorded:** `draftsman.md`, "Side views and callouts", under `H-A-DWF-GEOM` (INFERRED). The output-job page gained a row on the path keys of `[PublishSettings]`.
  - Branch `c0190-documentation-views`, from `c0189-review-tools`. Proof passed.

## 1. Views

- [x] 1.1 Output jobs (scenario "Public output jobs"). Proof: `uv run pytest tests/unit/view/test_documentation.py -k outjob -q`.
  - 2026-10-25: proof passed (4).
  - The three public jobs list every output with its name, type and folder.
  - An authored job checks the folder form, and checks that the absolute `RelativeOutputPath` of `[GeneratedFilesSettings]` is never shown.
- [x] 1.2 BOM table. Proof: `uv run pytest tests/unit/view/test_documentation.py -q`.
  - 2026-10-25: proof passed (5).
  - An authored `.BomDoc` is checked against authored sheet parts: grouping, catalog, manual lines, sort, numbering and the supplier columns left out.
- [x] 1.3 Draftsman side views and callouts. Proof: `uv run pytest tests/unit/view/test_drawing.py tests/corpus/test_draftsman_draw.py -q`.
  - 2026-10-25: proof passed (9 and 13; the corpus file with `FENOLITE_HEAVY=1`).
  - The tests cover the section and part boxes, a part without a height, the right view's axis, a dimension on a side view, and a callout's tag.
  - Fixed on the way: a view's title had been added to the box of the view's last part.

## 2. Closing

- [x] 2.1 Browser review of S-0786's project. Proof: the record under this task.
  - 2026-10-25, the agent, in the Chromium of the container.
  - **Input:** the project laid out in a scratch folder from the corpus (`PrjPcb`, `SchDoc`, `PcbDoc`, both drawings) and the repository (the three output jobs, the `.BomDoc`). The page was exported with `fenolite view … --export`.
  - **BOM:** 25 lines, 13 from the 23 parts and 12 manual.
    - The 13 part lines and their quantities equal the BOM table of the project's own assembly drawing (for example `A0, A1, A2, J3`, 4).
    - A click on that line opened the board with `ref:A0 | ref:A1 | ref:A2 | ref:J3`: 4 parts, 88 primitives.
  - **Output job:** `Assembly.OutJob` listed its 2 outputs. A click on the drawing's row opened `PiDP11IOExpander_Assembly.PCBDwf`.
  - **Drawings:**
    - the assembly drawing draws the Front and Right views under and beside the top view, with their three dimensions (59.69 mm, 21.59 mm and the override 43.2);
    - the fabrication drawing draws callout 9 at the board.
  - **Left for the maintainer:** comparing a BOM of their own with Altium's ActiveBOM (`H-A-PRJ-BOMDOC`).
- [x] 2.2 Docs, fast gate. Proof: `make check-fast`.
  - 2026-10-25: proof passed (13 948 passed, 34 skipped).
  - The reader test's placeholder of a skipped kind is now `TransmissionLineTableData`, because callouts are read.
  - Changed: `docs/viewer.md` ("Documentation: BOM, output jobs, drawings"), the `view` section of `docs/cli-contract.md`, the format pages, `docs/hypotheses.md`, `docs/evidence/sources.md` (S-0815), the evidence matrix and the LEGAL-ANNEX row.
  - No argument changed, so the agent guide is unchanged.
