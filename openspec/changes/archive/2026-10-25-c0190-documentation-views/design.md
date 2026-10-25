## Context

- **Request.** P1-9 of the analysis of 2026-10-25.
- **What exists.** `read.outjob` (output jobs), `read.dwfdraw` (c0180), `fenolite bom`.

## Goals / Non-Goals

**Goals**
- See the proposal, "What Changes".

**Non-Goals**
- See the proposal.

## Decisions

1. A table scene is a new library-form item kind `table` with columns and rows; the page draws it as an HTML
   table with sorting and a filter.
2. Side views use the part heights of the board copy; a part without a height is drawn 1 mm high with a note.
3. An ActiveBOM document holds settings and a catalog, not lines (task 0.1): the BOM is built from the
   project's parts with the document's grouping, catalog, columns, aliases and sort, in `cmd_view` where the
   project's sheets are known; the document alone lists its catalog. Supplier columns are left out.
4. A table scene (`kind` `"table"`) holds `columns`, `rows`, and per row `docs` (documents a click opens) and
   `refs` (parts a click selects on the board, through the filter of c0187).
5. Side views take the frame the document stores and are not turned on the sheet; the board's lower face lies
   the frame's `Y` above the view's location (the front view's dimension fits it exactly at both ends).

## Risks / Trade-offs

- **`.BomDoc` facts** may not be enough; the fallback is the project's parts grouped by comment and footprint,
  stated in the notes.
