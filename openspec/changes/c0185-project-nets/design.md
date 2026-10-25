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
3. The sheets a project net reaches come from the scenes of the project's sheets (cached), as a component's
   path names its module, not its sheet file. `cmd_view` compiles the project once per run, when a sheet of an
   Altium project is first shown; the scene cache keeps the sheet's own scene, and the annotation is added
   after it.

## Risks / Trade-offs

- **Projects that do not compile** (missing sheets): sheets keep local nets, with a note.
