## ADDED Requirements

### Requirement: Routed copper below the governing track width
`fenolite route` SHALL judge the copper a router adds against the `track_width` rule that governs it and report `route.width-below-minimum` (error) for each net with copper narrower than that rule's `min`, so no write is planned; `route.width-below-job` MUST stay as it is (change c0403, F6).

#### Scenario: A router that narrows wires
- **GIVEN** a stub router that returns 0.15 mm copper on a board whose rules file holds a 0.2 mm `track_width` minimum
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k below_the_minimum` runs the route with `--dry-run`
- **THEN** the exit code is 5, the reply holds `route.width-below-minimum` and `route.width-below-job`, and no plan is written
