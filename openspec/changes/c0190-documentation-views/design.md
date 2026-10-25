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

## Risks / Trade-offs

- **`.BomDoc` facts** may not be enough; the fallback is the project's parts grouped by comment and footprint,
  stated in the notes.
