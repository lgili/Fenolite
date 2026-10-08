## MODIFIED Requirements

### Requirement: Net selection
`fenolite.routing.select.unrouted(design, open_nets, *, patterns=("*",), include_zone_nets=False) -> tuple[str, ...]` SHALL return, sorted, the names of the nets to route. `open_nets` is a collection of the names of the nets that have at least one open connection on `design` (`board-analyses`, "Open connections of a net"); the caller computes it, because `routing` may not import `analysis`:
- a net MUST have two or more pads on placed footprints and MUST be in `open_nets`; copper of its own MUST NOT exclude it;
- a net that a zone carries MUST be left out unless `include_zone_nets` is true;
- `patterns` are `fnmatch` globs on the net name; a pattern starting with `!` excludes, and a net is selected when it matches a non-excluding pattern and no excluding one.

`select.rip(design, nets, *, keep=frozenset()) -> tuple[Design, int]` SHALL remove the tracks, arcs and vias of those nets whose `locked` is false and whose id is not in `keep`, and return their count. Every other item MUST stay, in its order.

#### Scenario: Unrouted nets
- **GIVEN** an authored design with nets `A` (two pads, no copper), `B` (two pads joined by one track), `S` (two pads and a 3 mm track from one of them), `GND` (three pads, one zone) and `NC` (one pad), and `open_nets` computed by `analysis.connectivity.connectivity`
- **WHEN** `uv run pytest tests/unit/routing/test_select.py` calls `unrouted(design, open_nets)`
- **THEN** it returns `("A", "S")`, and `("A", "GND", "S")` with `include_zone_nets=True`

#### Scenario: Patterns
- **WHEN** `unrouted(design, open_nets, patterns=("*", "!A"))` is called on the same design
- **THEN** it returns `("S",)`

#### Scenario: Rip
- **GIVEN** the same design, where `B` also holds a second track with `locked=True` that joins nothing
- **WHEN** `rip(design, ("B", "S"), keep=frozenset({<id of the track of S>}))` is called
- **THEN** the unlocked track of `B` is gone, the locked track of `B` and the track of `S` stay, and the count is 1

#### Scenario: The old call fails loudly
- **WHEN** `unrouted(design)` is called without `open_nets`
- **THEN** it raises `TypeError`

## ADDED Requirements

### Requirement: Router copper on open nets
A router MAY return copper for a net that it lists in `unrouted`, and the `routed` and `unrouted` of a `RoutingResult` SHALL be read as the router's own claim. `fenolite route` takes its verdict from the open connections after the merge (`cli-contract`, "Route command"); it MUST merge every valid item of a result, the copper of nets that stay open included, and MUST NOT remove copper that a router returned because its net stays open. A router MUST NOT be given a net that has no open connection. `docs/routing.md` MUST tell plugin authors both rules.

#### Scenario: Partial copper is merged
- **GIVEN** `two_pads.kicad_pcb` and a test router that returns one 2 mm track from `J1-1` on `ROUTE_ME` and lists that net in `unrouted`
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k partial` runs `fenolite route <board> --router <test router> --confirm`
- **THEN** the written board holds the track, `result.unrouted` is `["ROUTE_ME"]`, and the issues hold one `route.partial` naming `ROUTE_ME`

#### Scenario: A closed net is not given to the router
- **GIVEN** a board with a net whose pads are joined and a net that is open, and a test router that records its job
- **WHEN** `fenolite route <board> --router <test router> --dry-run` runs
- **THEN** the recorded job holds only the open net
