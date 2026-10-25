## Why

On 2026-10-25 the maintainer asked for an analysis of the viewer of c0176 to c0180 and of what it lacks to be "super útil" and professional, "principalmente para projetos de altium", then: "escreve as specs e começa pela primeira". This change is item P0-3 of that analysis.

The board view does not draw keep-outs and rule areas, rooms, or the dimensions of a board, which a reviewer
checks first: whether a part sits in a keep-out, where a room is, the board's stated size. The model holds
keep-outs (`Board.keepouts`), and the Altium and KiCad readers fill them; the scene skips them.

## What Changes

- **Keep-outs and rule areas.** Each keep-out of the model is drawn on its layers (or a "Keep-Out" layer for
  an Altium keep-out of every layer) as a hatched outline, with what it forbids (tracks, vias, pads, pours,
  footprints) in Properties.
- **Rooms (Altium).** The room definitions of `Rules6` (`RoomDefinition` rules) with a rectangular or polygonal
  region are drawn on a "Rooms" view layer with their name, and the parts their scope names are listed.
- **Board dimensions.** Altium `Dimensions6` records and KiCad `dimension` items are drawn: the lines, arrows
  and text the file holds, on their layer.
- **Courtyard overlap.** Overlapping courtyards (the `placed_extents` of the board frame) are drawn red on a
  "Checks" view layer, with the two parts in Properties.

## Capabilities

### New Capabilities

- `board-annotations-view`: keep-outs, rooms, board dimensions and courtyard overlaps in the board scene.

### Modified Capabilities

- None.

## Non-goals

- Evaluating room scopes beyond `read.scope`.
- Editing rule areas.

## Evidence level required

- Altium `Dimensions6` records: `UNKNOWN` today. Task 0.1 measures them on the public boards; without public
  facts the change draws KiCad dimensions and Altium keep-outs and rooms only, and names Altium dimensions in a
  note.
- Keep-outs: as the readers label them (`board.keepouts`).

## Impact

- **New:** `tests/unit/view/test_board_annotations.py`; reader facts in `docs/formats/altium/pcb-records.md`.
- **Changed:** `view/scene.py`, `view/page.html` (hatch, view layers), `docs/viewer.md`.
- **Size:** 4 design-days.
