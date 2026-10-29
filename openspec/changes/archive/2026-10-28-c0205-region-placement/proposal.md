## Why

An agent that builds a board with Fenolite gets stuck at placement. `fenolite place` offers manual moves, a
grid that packs every staged part from the top-left corner, and bounded constrained proposals (c0096). None
of them knows that a board with an isolation barrier has two sides: the grid mixes the primary and the
secondary parts, and the routing then has to cross the barrier many times. The roadmap moved the annealing
placer after 1.0; the maintainer asked on 2026-10-28 for a lean initial placement by regions now: group the
parts by domain and put each group in its own region of the board, so that a first placement respects the
isolation barriers before routing.

## What Changes

- `fenolite.placement.regions`: pure functions on boxes. `split` cuts a box into bands, `band_order` orders
  the domains so that the two sides of each barrier are neighbours, `boundary` finds where two regions
  meet, and `place_regions` centres each barrier across its boundary and packs each region with
  `placement.grid.place`. `region_of` names the region of a point.
- `fenolite place --strategy regions` with `--barrier REF[,REF...]`, `--group NAME=GLOB[,GLOB...]`,
  `--region NAME=X1,Y1,X2,Y2` and `--split x|y`. The domains are the islands of
  `analysis.ties.isolation_islands` once the barriers are removed (c0198), or the groups. The regions are
  the user's rectangles, or one band of the outline per domain.
- After the moves, the open connections (`analysis.connectivity`) whose ends lie in two regions are counted
  per pair of regions.
- `result.regions`, three new warnings (`place.region-unassigned`, `place.region-barrier`,
  `place.region-crossing`), `fenolite explain` entries, `docs/placement.md` ("Regions"),
  `docs/cli-contract.md` ("Region placement") and a line on the guide's `board-floorplan` page.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `placement`: ADDED "Region placement" and "Region placement codes".
- `cli-contract`: ADDED "Region strategy in the place command".

## Non-goals

- An optimiser: no annealing, no wire-length objective, no rotation or flip. Parts are packed in
  component-path order, as the grid packs them.
- Creepage and clearance across the barrier: a rule area or a slot drawn along the border does that.
- Regions that are not rectangles, a TOML file of regions, and moving parts that are already on the board.

## Evidence level required

`INFERRED` (`H-G-REGION-PLACE`): the regions are Fenolite's own rule, on the authored bench of
`tests/_regionbench.py`, whose islands, bands and boundary are known by construction. The moved footprints
keep `placement.EVIDENCE`, and KiCad's DRC still judges the board.

## Impact

- `src/fenolite/placement/regions.py`, `placement/codes.py`, `src/fenolite/cli/place_regions.py`,
  `cli/cmd_place.py`, `cli/data/explain.toml`, tests, `docs/placement.md`, `docs/cli-contract.md`,
  `docs/hypotheses.md`, the guide's `board-floorplan` page and generated `commands.md`, `CHANGELOG.md`.
