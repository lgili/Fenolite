## Why

On 2026-10-25 the maintainer asked for an analysis of the viewer of c0176 to c0180 and of what it lacks to be "super útil" and professional, "principalmente para projetos de altium", then: "escreve as specs e começa pela primeira". This change is item P1-6 of that analysis.

The schematic view computes nets per sheet (`local_nets`). In a hierarchical Altium project a net crosses
sheets through ports, sheet entries, power ports and harnesses, and a reviewer follows it across sheets and onto
the board. Today a click on a net lights it on one sheet only, and the board and the sheets do not light the
same net together.

## What Changes

- **Project nets.** For an Altium project, nets are compiled across the project's sheets as the project's
  net identifier scope says (`project.md`): ports and sheet entries, power ports (global), net labels (per the
  scope), harness entries. Each sheet's local net gets its project net name.
- **Cross highlight.** A click on a net on a sheet lights it on every sheet and on the board; a click on the
  board lights it on the sheets. The Navigator lists project nets with their sheets and pins.
- **Reply.** `fenolite view PROJECT --doc SHEET --json` gives project net names in `summary.nets`.

## Capabilities

### New Capabilities

- `project-connectivity-view`: project nets across sheets and the cross highlight between sheets and board.

### Modified Capabilities

- None.

## Non-goals

- KiCad hierarchical nets (a later change, same design).
- Net classes and differential pairs in the view.

## Evidence level required

- The compilation reuses `backends/altium/adapter/connectivity.py` (the netlist the Altium adapter builds);
  the view adds nothing to the connectivity facts (`connectivity.md`).

## Impact

- **New:** `src/fenolite/view/project_nets.py`, `tests/unit/view/test_project_nets.py`.
- **Changed:** `view/schematic.py`, `view/page.html`, `view/server.py` (shared selection), `docs/viewer.md`.
- **Size:** 4 design-days.
