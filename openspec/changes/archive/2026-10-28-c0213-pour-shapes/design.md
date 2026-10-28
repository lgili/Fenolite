## Context

c0175's design, "Package 7, more kinds", names the kinds of this change: `necks` (necks, slivers and acute
tips of pours), `loops` (the area of a declared loop, compared between two versions), `balance` (the copper
of the two pads of a two-pad SMD part, for tombstoning) and `--kinds power --split` (the share of a net's
current in each parallel path and in each via, from a resistive solve on a raster of the copper). Each keeps
the three copper states of c0204 apart and says which one a row used. c0204 gives the raster
(`pour.ring_cells`, `shape_cells`, `islands_of`) and the zone layers in their states (`pour_copper`), and
the shortest path along copper of `decoupling` (`practice.copper_distances`); c0115 gives the power paths and
the interval of their resistance (`power.analyze_power`).

## Decisions

1. **Widths on the raster.** The core has no polygon offset without the `geo` extra, so the copper of a net on
   a layer is the raster of c0204 (`--pour-grid`, 0.1 mm by default): the cells of the stored fills of its
   `saved_fill` zone layers and the kept islands of its `simulated` ones. An `outline` zone layer is an upper
   bound, not copper, and is skipped and counted. The width of a cell is the shortest of the four runs of
   copper cells through it: along the two axes `n·g`, along the two diagonals `n·g·√2` rounded down. A cell
   is wide when its width reaches the width `w` of the row, thin otherwise. A run measures a band crossed at
   an angle within 22.5° of its direction, so a width is high by at most 8 % plus one cell.
2. **Necks.** In each island (cells joined by a side), the cells are added widest first, ties in cell
   order, each joined to its added side neighbours. A cell that joins two sets that both hold wide cells is a
   neck, and its width is the neck's: it is the narrowest place of the widest path between two wide parts. A
   narrowing beside a wider parallel path is not a neck, because the current takes the other way.
3. **Tips and slivers.** An island without a wide cell is a sliver, of the width of its widest cell. Thin
   cells joined by a side, in an island with wide cells, are a tip when the wide cells next to them (eight
   neighbours) form one patch and the thin cells reach at least `w` from it, counted in steps of eight
   neighbours. The convex corner of a pour reaches about `w/3` and is no tip; a tip sharper than about 50°, or
   a finger longer than `w`, is one. A thin band with two patches is a neck or the narrow side of a ring.
4. **Neck rows.** A `[[neck]]` row has `select` (a net or net-class glob, as `[[current]]`) and
   `min_width_nm`. The row of a net is the matching row with the largest width. Each neck, tip and sliver of
   the net below it is `analysis.neck-narrow` (error), with the place (the cell centre) and the width. A row
   that matches no net with a zone is `analysis.requirement-unmatched`; without a row nothing is measured and
   the kind reports `analysis.input-missing`, as `bodies` does.
5. **Loops.** A `[[loop]]` row has `name`, `pads` (two or more `REF-PIN`, in order around the loop) and an
   optional `max_area_nm2`. The loop is closed. Each leg between two pads of one net that copper joins follows
   the shortest path along copper of c0204's decision 4 (stored fills walked, a simulated pour not); any
   other leg is straight, through a part or across a gap, and says so. The area is that of the closed
   polyline (shoelace), exact for straight tracks. Above `max_area_nm2` it is `analysis.loop-area` (error).
   `--loop-baseline FILE` measures the same rows on another board read by the same rule and gives each row's
   area there and the change. A pad name that no pad holds is `analysis.requirement-unmatched`.
6. **Balance.** A two-pad SMD part has exactly two pads, both SMD on one layer. For each pad the window is
   the box of its copper grown by the larger side of that box; the copper is the cells of the pad's net on
   that layer in the window (tracks, arcs, vias, other pads, stored fills, kept islands) joined by sides to
   the pad's cells, the pad's own cells not counted. A row gives both areas and their ratio in permille
   (larger over smaller; `null` when one is 0). Nothing is judged.
7. **The split solve.** For a row of `power`, the cells of the net's copper on every layer are nodes. The
   cells of each pad and each via on a layer are one node (an ideal contact, as a joint of c0115); regions
   that share or touch cells are one node, and a through-hole pad's layers too. Neighbour cells are joined by
   the conductance `t/ρ` of a square of copper, doubled between a contact and a free cell (the contact's edge
   lies at the cell face, half a step away). The layers of a via are joined pairwise down its span by
   `A/(ρ·h)`, `A` the barrel's area by c0115's plating and `h` between the layer middles of the stack-up. `ρ`
   cancels from the shares. The start pads are held at `2^40`, the end pads at 0, and the others are solved
   by over-relaxation in integers (`ω = 2 − 3/n`, `n` the raster's two spans added) until no potential moves
   by more than `2^16` in a pass, or the iteration limit (`converged` false). A via carries the flow through
   its barrel. A track, an arc or a fill carries, in each piece of the cells it alone covers, the net inflow
   from the nodes around it, cells shared with other elements joined into one node, so a current through a
   contact or a joint counts once; the largest piece counts. Its share is that over the path's current, in
   permille. With a resistivity, the resistance `ρ·2^40/I` is given and checked against `power`'s interval
   (`within`). On fills the two use the same contacts; `power` counts a track from the centres of its pads,
   so on a path of tracks the solve can lie below the interval by the copper inside the pads.
8. **Inputs.** `--split` needs `power`; a copper thickness for every layer of the net, and for a net with a
   via a plating and a stack-up, else the row is not solved and `analysis.input-missing` names what is
   missing. Nothing is assumed.

## Risks / Trade-offs

- The raster places copper to within one cell; a neck narrower than a cell can vanish or close. The rows give
  the grid; `--pour-grid` trades time for detail, and the width of a row should be five cells or more.
- The solve runs in Python over every cell of the net: a large board takes time at a fine grid. It is opt-in.
- Contacts as equipotential nodes put a via's annular ring at one potential, as c0115's joints do.

## Open Questions

None.
