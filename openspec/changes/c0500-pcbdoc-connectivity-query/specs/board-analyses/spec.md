## ADDED Requirements

### Requirement: Island members and removal by name
`fenolite.analysis.connectivity.net_islands(design, *, pads, nets=None, pour=None, without=())` SHALL give,
for each net, its counted islands as `connectivity` counts them, each with `members` (change c0500).
- `members` MUST hold one `IslandItem(kind, id, where, layers)` per pad, track, arc, via and fill of the
  island, sorted by `(kind, where, id)`. `where` MUST be `REF-PIN` for a pad and the provenance locator
  otherwise. `layers` MUST be the sorted copper layers of the item's copper.
- `without` MUST name tracks, arcs, vias or zones by model id, native id or locator, resolved by
  `analysis.ties.item_names`, the resolver of `--tie-item`. The copper of every named item MUST be left out
  before the islands are grouped. A zone removes all its fill polygons. A name that matches nothing MUST
  raise `KeyError` with that name.
- No item MUST be removed because of where it lies. Saved fills MUST NOT be poured again after a removal.
- The union MUST stay `geometry.touch_groups`. No second union is added.

#### Scenario: Members of each island
- **GIVEN** the bench of "Open connections of a net" with net `N` split into a pad-and-stub island and a far
  pad
- **WHEN** `uv run pytest tests/unit/analysis/test_connectivity.py -k members` computes `net_islands`
- **THEN** `N` has two islands, the first with members `pad RA-1` and the stub `track` with its locator and
  `F.Cu`, the second with `pad RB-1` alone

#### Scenario: A cut splits the net
- **GIVEN** an authored board whose net `GND` joins pads `RA-1` and `RB-1` by one track `t1`
- **WHEN** `net_islands` runs with `without={"t1"}`
- **THEN** `GND` has two islands, `RA-1` and `RB-1`, and `t1` is a member of neither

#### Scenario: A parallel path keeps it whole
- **GIVEN** the same board with a second track `t2` joining the two pads
- **WHEN** `net_islands` runs with `without={"t1"}`
- **THEN** `GND` has one island holding both pads and `t2`

#### Scenario: An unknown name
- **WHEN** `net_islands` runs with `without={"t9"}` on that board
- **THEN** it raises `KeyError` naming `t9`
