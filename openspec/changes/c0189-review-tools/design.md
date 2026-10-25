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
   page offers a download instead.

## Risks / Trade-offs

- **Writes from a page.** The server accepts marks only from the loopback address and only to the review
  file.
