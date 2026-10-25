## Why

On 2026-10-25 the maintainer asked for an analysis of the viewer of c0176 to c0180 and of what it lacks to be "super útil" and professional, "principalmente para projetos de altium", then: "escreve as specs e começa pela primeira". This change is item P1-9 of that analysis.

An Altium project's documentation lives beside its boards and sheets: the ActiveBOM document (`.BomDoc`), the
output jobs (`.OutJob`) and the Draftsman drawings. The viewer draws the drawings (c0180) without their side
views and callouts, and lists the others without opening them.

## What Changes

- **BOM.** A `.BomDoc` opens as a table: the BOM lines the document defines (columns, grouping, the
  document's own fields), with the parts linked to the board and the sheets; when the BOM document cannot be
  read the BOM is built from the project's parts.
- **Output jobs.** An `.OutJob` opens as the list of its outputs (`output-job.md`): name, type, the documents
  it binds and the output folder; a click on a bound document opens it.
- **Draftsman.** Side views (`Front`, `Back`, `Left`, `Right`) drawn from the board copy's outline, thickness
  and part heights (`ComponentTypes/Height`, `MinZ`), and callouts with their leader and text.

## Capabilities

### New Capabilities

- `documentation-view`: BOM documents, output jobs, and the side views and callouts of Draftsman drawings.

### Modified Capabilities

- None.

## Non-goals

- Running output jobs.
- Supplier data of ActiveBOM (prices, stock).

## Evidence level required

- `.BomDoc`: its records are `UNKNOWN`; task 0.1 measures the public `.BomDoc` of S-0786. Side views:
  `INFERRED` from the Draftsman census of c0180 and the dimensions measured on them.

## Impact

- **New:** `src/fenolite/view/bom.py`, `src/fenolite/view/outjob.py`, `tests/unit/view/test_documentation.py`.
- **Changed:** `view/drawing.py`, `view/project.py`, `view/page.html`, `docs/formats/altium/draftsman.md`,
  `docs/viewer.md`.
- **Size:** 5 design-days.
