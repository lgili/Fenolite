## ADDED Requirements

### Requirement: Test-point placement
`fenolite testpoints BOARD --place --side top|bottom` SHALL add one probe, the generated test point of `design.test_point`, for each eligible net (`Test-point coverage`) that the side does not reach and `--nets` matches, under the mutation protocol, and SHALL report the coverage before and after in `result.place`. A net without a site MUST give `testpoint.no-site` with the nearest site and its blocker.

#### Scenario: Coverage raised to every net
- **GIVEN** an authored two-layer board with six eligible nets and room around each, none with a bottom test point
- **WHEN** `uv run pytest tests/unit/exports/test_testpoint_place.py -k cover` runs `fenolite testpoints <board> --place --side bottom --confirm --json`
- **THEN** `result.place.before.covered` is 0, `result.place.after.covered` is 6, and Fenolite's copper check finds nothing new on the written board

#### Scenario: A net without room
- **GIVEN** the same board with one more net whose copper lies only under a bottom part's courtyard
- **WHEN** `uv run pytest tests/unit/exports/test_testpoint_place.py -k no_site` runs the command
- **THEN** that net stays uncovered and the issues hold one `testpoint.no-site` naming the courtyard of that part

### Requirement: Probe sites
A site SHALL lie on a grid of `--grid` (2.54 mm) within `--reach` (5 mm) of an anchor of the net on the side's outer layer (pad centre, via, track or arc end), nearest first, joined by one straight track of the net's class width. Probe and track MUST keep the clearance in force from other copper, holes and earlier probes, the edge clearance from the edge, and miss the side's courtyards, silkscreen and forbidding rule areas; probes keep `--min-pitch` (1.27 mm).

#### Scenario: Sites nearest first
- **WHEN** `uv run pytest tests/unit/exports/test_testpoint_place.py -k sites` lists the sites of one anchor
- **THEN** they come by distance, then by y and x, each within the reach

### Requirement: Placed test points checked
Before writing, Fenolite's copper check SHALL judge the board with and without the probes, and a probe whose pad or track a new finding names MUST NOT be written (`testpoint.check-failed`). With `--drc`, `kicad-cli` DRC SHALL run on the board before and after; a type that grows, the footprint-library types aside, MUST give `testpoint.drc-new` and nothing is written; without one the reply is `KICAD-VERIFIED`.

#### Scenario: KiCad finds nothing new
- **GIVEN** the authored benches, probed from the bottom and from the top
- **WHEN** `uv run pytest tests/kicad/assembly/test_testpoint_place_oracle.py` runs the command with `--drc --confirm`
- **THEN** no DRC type grows but `lib_footprint_issues`, the unconnected items stay as they were, and the evidence is `KICAD-VERIFIED`

### Requirement: Placed test points kept by a rebuild
A probe SHALL be written as a footprint without `fenolite.path` and its track as board copper, so that a rebuild of the design script keeps both as a board-only footprint (`layout.board-only`) and a kept track. The reply SHALL hold `testpoint.board-only` (info) naming the probes.

#### Scenario: A rebuild keeps the probes
- **GIVEN** the built blink with probes placed from the top
- **WHEN** `uv run pytest tests/unit/exports/test_testpoint_place.py -k rebuild` builds the script again over that board
- **THEN** every probe and its track are on the rebuilt board and the build reports `layout.board-only`

### Requirement: Test-point placement codes
`testpoint.no-site` (warning), `testpoint.check-failed` (warning), `testpoint.drc-new` (error) and `testpoint.board-only` (info) SHALL be registered with `fenolite explain`. `--grid`, `--reach`, `--size`, `--nets`, `--drc` and `--kicad-cli` without `--place`, and `--place` with `--side both`, MUST be refused with `FEN-2001`.

#### Scenario: Options refused
- **WHEN** `uv run pytest tests/unit/exports/test_testpoint_place.py -k refusals` runs the command with `--grid 1mm` alone or `--place` with no side
- **THEN** the exit code is 2 with `FEN-2001` naming the option
