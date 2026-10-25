## Context

- **Request.** P1-6 of the analysis of 2026-10-25.
- **What exists.** The Altium adapter compiles the project netlist for `build`/`check`; the viewer's
  `local_nets`; the cross-probe of parts (c0177).

## Goals / Non-Goals

**Goals**
- See the proposal, "What Changes".

**Non-Goals**
- See the proposal.

## Decisions

1. The view asks the adapter for the project netlist once per project and maps each sheet's local nets to
   it by pin membership, so the two never disagree.
2. Selection is shared through the page state; in `--serve` it also passes between tabs with
   `BroadcastChannel`.

## Risks / Trade-offs

- **Projects that do not compile** (missing sheets): sheets keep local nets, with a note.
