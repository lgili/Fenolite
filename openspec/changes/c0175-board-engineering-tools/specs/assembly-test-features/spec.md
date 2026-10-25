## ADDED Requirements

### Requirement: Test-point placement
`fenolite testpoints BOARD --place --side SIDE [--pitch LENGTH] [--reach LENGTH] [--size LENGTH] [--nets GLOB]` SHALL place one test point for each eligible net (`Test-point coverage`) that has no access from `SIDE`, under the mutation protocol, and SHALL report the coverage before and after.
- A site MUST lie on a grid of `--pitch` (default 2.54 mm) within `--reach` (default 5 mm) of the net's copper on `SIDE`'s outer layer; it MUST keep the clearance in force to other nets' copper, the board edge, slots and drills, MUST miss the courtyards and bodies of parts, and MUST lie outside rule areas that forbid footprints on that side.
- The probe MUST be joined to its net by sitting on the net's copper, or by one straight track of the net's class width that keeps every clearance. The nearest such site wins; ties are broken by the smallest track length, then by position.
- Placed probes MUST spread so that no two are closer than `--min-pitch` (default 1.27 mm) and no two joining tracks cross.
- A net for which no site exists MUST be reported with `testpoints.no-site` (warning), with the nearest blocked site and its blocker.
- The probe part MUST be the generated test point of `design.test_point`, so the report of "Test-point report rows" lists it.

#### Scenario: Coverage raised to every net
- **GIVEN** an authored two-layer board with six eligible nets and room around each, none with a bottom test point
- **WHEN** `uv run pytest tests/unit/exports/test_testpoint_place.py -k cover` runs `fenolite testpoints <board> --place --side bottom --confirm --json`
- **THEN** `result.coverage.covered` goes from 0 to 6, and `kicad-cli` DRC on the written board reports nothing new

#### Scenario: A net without room
- **GIVEN** the same board with one net whose copper lies only under a part body
- **WHEN** the command runs
- **THEN** that net stays uncovered and the issues hold one `testpoints.no-site` naming the body
