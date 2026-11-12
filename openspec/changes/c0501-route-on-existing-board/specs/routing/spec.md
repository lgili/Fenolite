## ADDED Requirements

### Requirement: Rule areas and other copper in the routing world
The routing world (`routing.octilinear.World`) SHALL hold as obstacles, beside pads, holes, tracks, arcs, vias
and the edge (change c0501):
- each rule area of `model.board.rule_areas` and each area of `extra["rule_areas"]`: one with `no_tracks`
  MUST refuse a track segment that overlaps its outline on one of its layers, one with `no_vias` a via
  barrel there; an area that forbids only poured copper, pads or footprints MUST refuse nothing;
- each copper graphic on a copper layer, at the clearance in force with net `None`;
- with `extra["pours"] == "kept"`, the saved fill of each zone of another net, at the clearance in force.
`World.blocker(net, layer, points, width)` MUST return the first item that refuses a segment, with its kind,
net, layer, place and clearance, or `None`; `World.fits` MUST be `blocker(...) is None`.

#### Scenario: A keep-out of poured copper only
- **GIVEN** an authored two-layer bench with a rule area on `F.Cu` that forbids only poured copper across
  the straight line between two pads of one net
- **WHEN** `uv run pytest tests/unit/routing/test_world_areas.py -k pour_only` searches that connection on
  `F.Cu`
- **THEN** the path is straight through the area

#### Scenario: A keep-out of tracks
- **GIVEN** the same bench with the area forbidding tracks
- **WHEN** the connection is searched on `F.Cu` without vias
- **THEN** the path goes round the area and never overlaps it, and `World.blocker` on the straight line
  names the area with kind `keepout`

#### Scenario: Keep-Out layer of an Altium document
- **GIVEN** an authored PCB document with a keep-out fill on the Keep-Out layer whose restrictions are 24
  (pads only) and a keep-out track there whose restrictions are 2 (tracks)
- **WHEN** `uv run pytest tests/unit/routing/test_world_areas.py -k altium_keepout_layer` builds the world
- **THEN** the track's band refuses a track on every copper layer and the fill refuses none

### Requirement: Search refusals name their wall
A search that ends with `no-room` SHALL return in `search.Outcome.wall` the items that refused edges at the
edge of the explored states, merged by item with the number of edges each refused, at most 12, sorted by
that number then by place, and `proven` (change c0501). `proven` MUST be true only when, for the wall items
ordered round the start and closed by the edge, every free gap between two neighbours (their exact distance
less both clearances in force) is narrower than the track width; otherwise the refusal is `grid-limited`
and names its widest free gap with its two items. A search cut by `state-limit`, `budget` or `cancelled`
MUST give no wall and MUST NOT be `proven`.

#### Scenario: A closed ring of pads
- **GIVEN** an authored bench where a pad of net `A` is ringed by eight pads of net `B` whose free gaps are
  each 0.1 mm, and a 0.2 mm track of `A` must leave the ring
- **WHEN** `uv run pytest tests/unit/routing/test_search_wall.py -k ring` searches it
- **THEN** the reason is `no-room`, `proven` is true, and the wall names the eight pads

#### Scenario: A gap off the grid
- **GIVEN** the same ring with one free gap of 0.3 mm placed between two grid lines of a 0.5 mm grid
- **WHEN** the search runs on that grid
- **THEN** `proven` is false and the widest free gap names the two pads at 0.3 mm

#### Scenario: A cut search proves nothing
- **WHEN** the ring is searched with `max_states` 10
- **THEN** the reason is `state-limit`, the wall is empty and `proven` is false

### Requirement: Free channel width
`fenolite.routing.channel.widest(job, net, a, b, *, limits, low, high, resolution)` SHALL bracket the widest
track of `net` between two points under the clearances in force: `low` a width at which `search` found a path
(returned, and accepted again by `World.fits` at that width), `high` the smallest width at which a search
ended with `no-room`, and `pinch` the widest free gap of that refusal with its two items (change c0501). It
MUST bisect until `high - low <= resolution`; a probe cut by a bound MUST stop it with `undecided` and the
bracket reached. `high` MUST be marked `grid_limited` unless the refusal that set it was `proven`. Lengths
MUST be integer nanometres.

#### Scenario: A slot between two nets of different classes
- **GIVEN** an authored bench with a 3 mm gap between a pad of class `HV` and a pad of class `Default`, a
  clearance of 1 mm for `HV` and 0.2 mm for `Default`, a rule of 0.5 mm between `HV` and net `S`, and two
  points of net `S` on either side of the gap
- **WHEN** `uv run pytest tests/unit/routing/test_channel.py -k classes` asks for the channel of `S` with a
  resolution of 10 µm on a 0.05 mm grid
- **THEN** `high - low <= 10 µm`, `low <= 2.3 mm <= high` (3 mm less the 0.5 mm rule, which governs over the 1 mm class value, and 0.2 mm), and `pinch` names the
  two pads with that free gap

#### Scenario: No channel at all
- **GIVEN** the closed ring bench
- **WHEN** the channel is asked from inside to outside the ring
- **THEN** `low` is `None`, `high` is the smallest width tried, and the refusal is `proven`

### Requirement: Path command codes
`routing.codes.ISSUE_CODES` SHALL hold `route.no-path` (warning), `route.path-limit` (info),
`route.via-template` (error), `route.repour-needed` (warning) and `route.altium-edit-unconfirmed` (warning),
each with an `explain.toml` entry and a row in `docs/cli-contract.md` (change c0501).

#### Scenario: Codes explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py -k route` runs
- **THEN** the five codes have their severities, an entry and a documented row
