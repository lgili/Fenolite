## Why

On 2026-10-25 the maintainer asked for an analysis of the viewer of c0176 to c0180 and of what it lacks to be "super útil" and professional, "principalmente para projetos de altium", then: "escreve as specs e começa pela primeira". This change is item P2-10 of that analysis.

When an agent changes a board or a sheet, the person checks the change by reading `fenolite diff` JSON or by
opening both files. A drawing of the difference, what was added, removed or moved, is the fastest way to trust
or reject the change, and the one Altium users miss most when reviewing someone else's work.

## What Changes

- **`fenolite view NEW --compare OLD`.** Builds the scenes of both and a difference overlay:
  - boards: primitives added (green), removed (red), and parts moved, turned or flipped (an arrow from the old
    place, with the distance and the angle);
  - sheets: parts, wires and labels added or removed, and parts whose parameters changed;
  - a list of the changes in a panel, each one a click away; `X` shows or hides them over a dimmed board.
- **Matching.** Parts by reference (then by footprint and position), primitives by layer, kind, geometry and
  net, so a renumbered file still matches.
- **Reply.** `result.compare` counts each kind of change; `--json` gives the list.

## Capabilities

### New Capabilities

- `visual-diff`: the difference overlay of two boards or two sheets.

### Modified Capabilities

- `cli-contract`: ADDED "View command compares two revisions".

## Non-goals

- Three-way merges.
- Comparing an Altium board with a KiCad board (two families): refused, as `diff` does.

## Evidence level required

- Matching is Fenolite's; it is tested on authored pairs and on two commits of a public board.

## Impact

- **New:** `src/fenolite/view/compare.py`, `tests/unit/view/test_compare.py`.
- **Changed:** `cli/cmd_view.py`, `view/page.html` (diff layer, Changes panel), `docs/viewer.md`,
  `docs/cli-contract.md`, agent guide (`files.md`).
- **Size:** 5 design-days.
