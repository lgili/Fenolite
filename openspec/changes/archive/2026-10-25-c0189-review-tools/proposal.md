## Why

On 2026-10-25 the maintainer asked for an analysis of the viewer of c0176 to c0180 and of what it lacks to be "super útil" and professional, "principalmente para projetos de altium", then: "escreve as specs e começa pela primeira". This change is item P2-11 to P2-13 of that analysis.

Three things make a review with the viewer slower than in Altium: measurement is centre to centre only, so a
gap between two pads or a copper clearance cannot be read; a person cannot point an agent or a colleague at a
place ("look at U12"); and the page cannot print or give a PDF or SVG of what it shows.

## What Changes

- **Edge measurement.** `Shift+M` measures the shortest distance between the edges of two clicked objects
  (pad, track, via, zone fill, board edge), as Altium's clearance measure does, and shows which points it used.
- **Deep links.** The URL keeps the document, the selection, the view and the unit (`#doc=…&sel=U12&z=…`);
  opening it restores them. `fenolite view ... --select U12` opens there.
- **Review marks.** A person can drop a mark with a note; marks are saved to `<project>/.fenolite/review.json`
  through the server (`--serve`) or downloaded from an exported page, and `fenolite view --marks FILE --json`
  lists them for an agent.
- **Print, PDF and SVG.** A Print button prints the current view at a chosen scale on the paper; "SVG" saves the
  current view as vector SVG.

## Capabilities

### New Capabilities

- `review-tools`: edge measurement, deep links, review marks, print and SVG.

### Modified Capabilities

- `cli-contract`: ADDED "View command opens at a selection and reads review marks".

## Non-goals

- Multi-user comments.
- A PDF writer in Python: the browser's print gives the PDF.

## Evidence level required

- Edge distance is computed on the scene's geometry (Fenolite's computation) and tested against the
  clearance `analyze` reports for the same pair.

## Impact

- **New:** `tests/unit/view/test_edge_measure.py`, `schemas/fenolite.review.v0.json`.
- **Changed:** `view/page.html`, `view/server.py` (POST of marks under the mutation rules), `cli/cmd_view.py`,
  `docs/viewer.md`, `docs/cli-contract.md`, agent guide.
- **Size:** 5 design-days.
