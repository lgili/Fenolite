## Why

Task 12.4 of c0175 (package 11, release checks). `fenolite render` plots whole sides through `kicad-cli`.
An agent, or a person, that wants to see why one crowded area fails needs a close view of it. The view
needs the nets of its pads, the connections still open, and coordinates it can act on. A whole-board plot
gives none of these. The crossing analysis of c0199 (`analyze --kinds crossings`) also left out its
`--render FILE.svg`: its reply holds each way's ends on the board, but nothing draws them.

## What Changes

- `fenolite render BOARD --region X1,Y1,X2,Y2 -o DIR` writes `DIR/region.svg`, drawn by Fenolite from the
  model under the mutation protocol, with no tool. The drawing holds:
  - pads, tracks, arcs, vias, holes, slots and the board edge, clipped to the rectangle;
  - the zone copper in its state of `analysis.pour` (saved fill, simulated pour, outline);
  - a grid labelled in millimetres of board coordinates (`--grid LENGTH`);
  - with `--nets`, each pad's net name; with `--open`, the open connections as straight lines.
- `--cut X1,Y1,X2,Y2` (repeatable, with `--cut-width` and `--cut-clearance`) draws a barrier cut and its
  ways per layer from `analyze_crossings`. This is the overlay c0199 left out.
- Every element carries `class` and `data-*` attributes, and coordinates are exact millimetres, so the file
  reads as data.
- `analysis.connectivity.connectivity(..., pour=)` computes the open connections on the copper of
  `analysis.pour`: the items that one island of a simulated pour covers are joined.
- New codes `render.region-empty` (warning) and `render.copper-simulated` (info); new hypothesis
  `H-G-REGION-RENDER`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `manufacturing-exports`: ADDED "Region renders" (from c0175), "Region render elements", "Region render
  copper", "Region render cut overlay" and "Region render refusals".

## Non-goals

- A PNG of the region: the project has no rendering extra, and the SVG is the analysis view. `--png` stays
  the `kicad-cli` render of a whole side.
- Silkscreen, fabrication and courtyard layers in the region: the view is about copper and connections.
- A separate `analyze --render`: the cut overlay lives on `render --region`, which already writes files
  under the mutation protocol.

## Evidence level required

`INFERRED` (`H-G-REGION-RENDER`): the drawing is the model's own geometry, proved on authored benches by the
elements and their coordinates. The open connections keep the level of `analysis.connectivity`, lowered to
`INFERRED` (`H-G-PRACTICE-POUR`) when a pour is simulated.

## Impact

- New: `src/fenolite/analysis/region.py`, `src/fenolite/cli/_region.py`.
- Changed: `src/fenolite/cli/cmd_render.py` (the region options), `src/fenolite/analysis/connectivity.py`
  (`pour=`), `src/fenolite/exports/codes.py`, `src/fenolite/cli/data/explain.toml`.
- Tests: `tests/unit/analysis/test_region_render.py`, `tests/unit/cli/test_render_region.py`,
  `tests/_regionviewbench.py`; `tests/unit/exports/test_plan.py` learns the two codes.
- Docs: `docs/cli-contract.md` ("Region renders"), `docs/exports.md`, `docs/hypotheses.md`, the guide's
  `fabrication` page and the generated `commands` page, `docs/evidence/matrix.md` (regenerated),
  `CHANGELOG.md`.
