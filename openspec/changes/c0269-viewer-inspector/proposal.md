## Why

The viewer shows what a click hits in `#info`, a floating box over the top-right corner of the drawing: a
pad of `U1` lists its layer, net, footprint, size and mask as plain text, covers the board, cannot be
copied value by value and offers nothing to do next. Selecting a net lightens the net's copper towards
white over a board dimmed to 28 %, so a net with a large pour washes the board pale instead of standing out.
The layer tabs along the bottom overflow at 1440 px and cut long names ("Board Outlin…"), and stay on
screen in 3D, where they do nothing. The 3D view has three buttons (Top, Bottom, Iso), one light and grey
extruded bodies.

This change docks the selection's properties and the layers beside the drawing, makes the net highlight
emphasise instead of wash, and gives the 3D view the controls it lacks. It needs nothing of c0270 or c0271
and builds on c0268's command registry and tokens.

## What Changes

- **Docked inspector.** A right-hand dock replaces the floating box: sections Part, Pad, Track, Arc, Via,
  Zone, Net, Keep-out and Finding, each a table of named values in the page unit with a copy control, and
  "Copy all". On sheets, libraries and drawings the same dock shows what their clicks show today.
- **Inspector actions.** Zoom to, Highlight net, Select part, Find similar, Show in schematic or Show on
  board (the existing cross-probe), and Open the finding. c0271 adds its writing actions here.
- **Net emphasis.** The selected net is drawn in its own layer colours at full opacity with a thin outline
  in the emphasis token, while the rest dims by the highlight mode (Dim, Mask, Normal). Zone fills of the net
  get an outline and a lighter fill, so a pour no longer covers the board.
- **Layers panel.** A Layers tab in the dock replaces the bottom layer tabs on boards and footprints:
  layers grouped (copper, mask and paste, silkscreen, mechanical and fabrication, view layers), each with
  its swatch, full name, visibility and opacity, the current layer marked, the layer sets of `LS` as
  presets. `Shift+S`, `+` and `-` keep working. Sheet tabs stay along the bottom.
- **3D controls.** Controls that only act in 2D are hidden in 3D. A view cube sets the six face views and
  the corner views; the light becomes an ambient term plus a key and a fill light; extruded bodies get a
  Fenolite body colour with a lighter top face; the 3D panel toggles bodies, board and silkscreen.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `board-viewer`: "Viewer page" (the Layers panel and the inspector replace the layer tabs and the
  floating box); new requirements for the inspector, its actions, net emphasis, the Layers panel, the
  3D controls and the inspector in narrow windows.
- `viewer-visual-tests`: a reference of a selected net in emphasis.

## Non-goals

- No writing action (c0271) and no command run from the page (c0270).
- No change of the scene format or of a scene's colours; the body colour applies only to bodies without a
  model, and models keep their own colours (c0193).

## Evidence level required

No format fact is involved and no evidence label changes. The inspector shows the values the scene holds
and keeps the evidence each already states (for example the mask expansion source of an Altium pad).
Behaviour is proven by Node and static tests in `tests/unit/view/` and by Chromium tests and screenshot
references in `tests/visual`, run by the `viewer` CI job.
