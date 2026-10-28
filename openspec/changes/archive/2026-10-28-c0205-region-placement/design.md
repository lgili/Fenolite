## Context

`placement.grid.place` packs boxes into one rectangle around occupied boxes and cut-outs. `place` builds
those boxes from the placed extents (courtyard, else pad hull) and moves the parts with `move_footprint`,
then judges the layout. `analysis.ties.isolation_islands` (c0198) gives the islands of nets once named
barrier parts are removed. `analysis.connectivity` gives the open connections of each net as a minimum
spanning tree between pads. The import graph lets `placement` import only `model`, `geometry` and
`backends.base`, so everything that reads nets or analyses lives on the CLI layer.

## Modules and API

- `src/fenolite/placement/regions.py`: `Region(name, bbox)`, `Barrier(box, sides)`, `Boundary`,
  `RegionRow`, `BarrierRow`, `RegionResult`, `split`, `band_order`, `boundary`, `place_regions`,
  `region_of`, `EVIDENCE` (`INFERRED`, `H-G-REGION-PLACE`).
- `src/fenolite/cli/place_regions.py`: `RegionOptions`, `parse_options`, `plan_regions`, `crossings`,
  `to_json`, `evidence`. It is the glue between `placement.regions` and `analysis`.
- `src/fenolite/cli/cmd_place.py`: the strategy `regions` and its four options; the box building of the
  grid is shared (`_packing`).

## Decisions

1. **A strategy of `place`, not a new command.** It stages, packs, judges and writes as the grid does, under
   the same mutation protocol, legality check and `--force`. Only staged parts move (off the board, or
   `--only`): parts on the board are obstacles, as for the grid.
2. **Domains.** Without `--group`, a domain is an island of `isolation_islands(design, barriers=…)` that
   holds a part other than a barrier. A part's domain is the island of its nets (all in one island by
   construction). With `--group`, the first group whose glob matches the reference wins. A part in no
   domain stays staged with a warning (`place.region-unassigned`): the conservative choice, since putting
   it in an arbitrary region could cross a barrier.
3. **Explicit regions need groups.** Island names (`D1`, `D2`, …) are only known after a run, so
   `--region` is accepted only with `--group`, and the two must name the same set. A TOML file of regions
   is left out: repeated options are enough for a lean first version (maintainer's choice pending; this is
   the conservative default).
4. **Default bands.** The outline's bounding box is cut along `--split`, by default along its longer
   side. Each band first gets its widest staged box plus two margins, so that every part fits across its
   band; the rest is shared in proportion to the courtyard-box area of the domain's parts (on the board
   and staged), a weight of 0 counting as 1. Cuts are whole nanometres, rounded down; the last band takes
   the rest. When the minimums do not fit, the weights alone share the length.
5. **Band order.** For islands, the domains form a graph whose edges are the barriers with pins in
   exactly two domains. `band_order` walks chains: start at the first remaining domain with the fewest
   remaining neighbours, go on to the first remaining neighbour, repeat. A chain of barriers therefore
   gives neighbouring bands; a barrier off the chain is reported. For groups the user's order is kept.
6. **Barriers first, across the boundary.** Two regions meet when they face each other over a common span
   with no other region in the space between them; the boundary is the middle of that space. A barrier
   is packed by `grid.place` in a strip as wide as its box plus two margins, centred on the boundary and
   as long as the common span, so it lies centred across the line at the first free place along it. It
   keeps its rotation and side. A barrier whose sides share no boundary, or with pins in one or in more
   than two domains, is packed in its first domain's region with `place.region-barrier`.
7. **Regions are packed by the grid,** in region order, each inset by `--margin`, around the occupied
   boxes, the cut-outs, the boxes of rule areas that forbid footprints and every box placed before. No
   new packer is written. A part that fits nowhere keeps `place.no-room`.
8. **Crossings as a check.** After the moves, each open connection of `analysis.connectivity` whose two
   ends lie in two different regions (first region in order whose closed box holds the point) counts
   against that pair; one `place.region-crossing` warning per pair, with the nets. An end outside every
   region (a part still staged) is not counted. It is a warning, never a refusal: a crossing is a fact to
   review, and `analyze --kinds crossings` counts the ways.
9. **Fill.** `fill_permille` is the area of the boxes placed in the region over the region's area, in
   thousandths rounded down: integers only. Parts already on the board are not counted.
10. **Evidence.** `INFERRED` under `H-G-REGION-PLACE`, combined with `H-G-TIES` when the islands gave the
    domains and with the connectivity's own evidence. The placement evidence of the moves stays.

## Risks / Trade-offs

- Packing in component-path order from the top-left corner of each band ignores the wire length inside a
  region; the measures of `place` (`hpwl`, `ratsnest`) say how far a run is from a good placement.
- A barrier whose pins face the wrong way after a translation shows up as crossings, not as a rotation.

## Open Questions

- Whether the maintainer wants a TOML file of regions and groups (decision 3).
