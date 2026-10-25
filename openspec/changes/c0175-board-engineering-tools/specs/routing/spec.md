## ADDED Requirements

### Requirement: Octilinear router plugin
A routing plugin named `octilinear` (`src/fenolite/routing/octilinear.py`) SHALL route short connections between pads of the selected nets on a board that a backend reads, in copper whose every segment runs at 0°, 45° or 90°, and SHALL be registered in the router registry with the feature `short` and no external tool.
- For each open connection, in the order of the job, it MUST try these shapes per leg, on each allowed copper layer: a straight segment; 45° then straight; straight then 45°; two orthogonal segments. It MUST accept the first shape that keeps the clearance in force (`copper-check`, "Clearance in force") to all other copper, the board edge, slots and drills, and MUST NOT make an acute angle with copper of its own net at a joint.
- A connection that no shape reaches within `--router-option max-length=LENGTH` (default 20 mm) MUST stay open and be reported with `route.unrouted`, never routed by a longer search.
- It MUST rip up its own copper of the job and retry, for at most `--router-option rounds=N` rounds (default 3), and MUST NOT remove copper that it did not place.
- A net of a differential pair MUST be routed with its partner as two parallel tracks at the pair's gap, starting at the inner edges of the pads, or left open with `route.pair-not-routed`.
- The routed copper MUST pass the copper check with no new finding before it is planned.

#### Scenario: A gate loop routed octilinear
- **GIVEN** an authored board with a driver and a switch, the nets `GATE` and `KSRC` unrouted, and a 0.3 mm clearance rule
- **WHEN** `uv run pytest tests/unit/routing/test_octilinear.py -k gate` routes them with `fenolite route <board> --router octilinear --nets GATE --nets KSRC --confirm`
- **THEN** both nets are complete, every segment angle is a multiple of 45°, no joint is acute, and `kicad-cli` DRC on the written board reports nothing new

#### Scenario: Too long stays open
- **GIVEN** a connection of 60 mm between two pads
- **WHEN** the plugin routes it with the default options
- **THEN** the connection stays open and the result holds one `route.unrouted` naming it
