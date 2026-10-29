## Context

c0175's design, decision 2 ("Ground ties"), holds the method of this change: take the copper graph of the
tie's nets, remove exactly the tie's items, and compute the connected groups. `analysis.connectivity` already
shapes a net's copper (`net_copper`) and joins it with `touch_groups`. A tie needs the edges themselves (the
neighbours of the tie and a shortest path), so `analysis.ties` builds them with the same predicate
(`thick_touch`, per layer, over a `SpatialIndex`).

## Decisions

1. **Nodes and names.** A node is a pad, a track, an arc or a via (its shapes on every layer), or one filled
   polygon of a zone. `--tie-item` matches a track, an arc, a via or a zone by its model id, any native id
   (the KiCad uuid) or its locator. A zone's id removes every fill polygon of the zone. `--tie REF` removes
   the pads of the part. The graph holds the nets of the removed nodes only.
2. **Groups and split.** The neighbours of a tie are the nodes that touch a removed node. The groups are the
   connected parts, after the removal, that hold a neighbour; each lists its pads. `split` is true with two or
   more groups. Pads that were apart before the removal are not the tie's business, so they are not listed.
   A tie with fewer than two neighbours joins nothing: `analysis.tie-dangling` (warning).
3. **Sides and the parallel path.** With one group, another path joins the tie's sides
   (`analysis.tie-parallel`, error). The path is a shortest path in nodes, ties broken by node order, from
   the neighbours of the first side to those of the others.
   - The sides of a part are its pads by net.
   - The sides of copper items are the free ends of their chain: an anchor of a removed track, arc or via
     that touches no other removed node. A neighbour belongs to an end when it touches a 1 nm disc at it.
   - A tie with fewer than two sides (a zone) gets the issue without a path.
4. **Domains.** `--domains A=GLOB,B=GLOB` names two domains; a name may repeat to add a pattern. After a
   split, a group that holds pads of both domains is `analysis.tie-extra` (error). The domain with fewer pads
   in the group is the stray one, the second named on a tie. One issue per group names the first stray pad
   and the shortest path to the other domain. With one group, `analysis.tie-parallel` already says it, so
   `tie-extra` is not added.
5. **Sense nets.** For each sense net, a node of it that touches a node of another net is
   `analysis.sense-shared` (error), naming both. The exception is two pads of one footprint in one net-tie
   group (`FootprintInstance.net_ties`, change c0114).
   - c0175's `analysis.sense-entry` is left out: its rule ("reaches the pad from outside the pad's outline
     before joining it") has no measurable form recorded from a public source.
6. **Islands.** `isolation_islands` joins the nets of each part that is not a barrier; nets with no pin are
   left out. Each island lists the barrier parts with a pin on it. It reads no copper, so it runs on any
   design.
7. **Unfilled zones and names.**
   - A zone of the tie's nets without fill polygons makes the row's `zones` `unfilled` and adds
     `analysis.input-missing`. Fenolite does not pour it.
   - A tie, a sense net or a barrier that names nothing is `analysis.tie-unmatched` (warning), not a usage
     error, as `analysis.path-unmatched` is for power paths.

## Risks / Trade-offs

- A tie whose items are given only in part (a track but not the via beside it) is reported parallel. That is
  the purpose: the user names the whole tie.
- The free-end rule of decision 3 does not order the sides of a branched tie (three free ends); the path then
  goes from the first end to the nearest other. It is still a real path.

## Open Questions

None.
