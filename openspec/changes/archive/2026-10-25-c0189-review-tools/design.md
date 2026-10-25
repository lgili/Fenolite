## Context

- **Request.** P2-11 to P2-13 of the analysis of 2026-10-25.
- **What exists.** Measurement with snapping (c0179), the server (c0176), the `analyze` clearance paths.

## Goals / Non-Goals

**Goals**
- See the proposal, "What Changes".

**Non-Goals**
- See the proposal.

## Decisions

1. Edge distance: polygon-to-polygon distance on the shapes the page draws (pads, tracks as stadiums, arcs
   sampled), exact for segments.
2. Marks are written only by the server, atomically, to one file; the page never writes elsewhere. An exported
   page offers a download instead. The file is the one `--marks FILE` names: serving with it is the consent
   to those writes (a writing command never writes by default), and without it the server refuses marks
   (403) and the page keeps them in the browser. A `POST /marks` needs the header `X-Fenolite-Review: 1`, a
   JSON body of at most 64 KiB, and a `Host` (and an `Origin`, when sent) of the server itself, so a page of
   another site cannot write.
3. Positions in the review file are integer nanometres, as in the model; the reply adds millimetres.
4. SVG and print share one path: the page draws the view again into a recorder of its canvas calls (a
   `Path2D` stand-in for the board's cached paths), so both show exactly what the screen shows, as vectors.
   Print sends that SVG, sized in millimetres for a scale, to the browser's print dialog in a hidden frame.

## Risks / Trade-offs

- **Writes from a page.** The server accepts marks only from the loopback address and only to the review
  file.
