## Why

Package 3 of change c0175 ("Barrier crossings"), split into a change of its own as c0175's design allows and as
the maintainer chose on 2026-10-26. A floor plan fails late when a barrier (a row of connector pads, the gap
between two regions, a slot) leaves fewer ways than the nets that must cross it: the router leaves
connections open, and the parts have to move after the routing started. Nothing in Fenolite counts the ways
of a barrier today.

## What Changes

- `fenolite.analysis.crossings.analyze_crossings` counts, for each cut segment, the free ways along it on each
  copper layer and the tracks each fits.
  - The obstacles are item copper grown by the clearance in force, the board edge and cut-outs grown by the
    edge clearance, holes without copper, and rule areas that forbid tracks.
  - A way of length `L` fits `⌊(L + c) / (w + c)⌋` tracks.
  - The demand lists, per net, the open connections whose straight line crosses the cut and the tracks and
    arcs that cross it.
- `fenolite analyze` gains the opt-in kind `crossings` with `--cut X1,Y1,X2,Y2` (repeatable), `--width` and
  `--clearance`.
- One issue code: `analysis.crossings-short` (warning), when the open connections exceed the tracks of all
  layers.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `board-analyses`: ADDED "Barrier crossings", "Crossing ways and demand", "Crossings kind in the analyze
  command" and "Crossings analysis code".

## Non-goals

- `--render FILE.svg` of c0175's draft. `analyze` is a read-only command (`mutates` false is fixed per
  command), so a drawing would change its contract. Each way carries its two ends on the board and each layer
  its obstacles, so a drawing can be made from the reply; the drawing itself goes with c0175's "Region
  renders" (design, decision 5).
- Whether a via fits in a way: c0175's design mentions it, its requirement does not; it is left out.
- The other packages of c0175, which stay there.

## Evidence level required

`INFERRED`: geometry on the board's own copper, proved on authored benches whose ways are counted by hand
(`tests/_crossbench.py`).

## Impact

- `src/fenolite/analysis/crossings.py`, `src/fenolite/analysis/codes.py`, `src/fenolite/cli/cmd_analyze.py`,
  their tests, `docs/analyses.md`, `docs/cli-contract.md`, `src/fenolite/cli/data/explain.toml`, the agent
  guide's floor-plan page and generated command page, `CHANGELOG.md`.
- Size: about 2 design-days (c0175's estimate for the package).
