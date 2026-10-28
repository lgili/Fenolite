## ADDED Requirements

### Requirement: Region strategy in the place command
`fenolite place --strategy regions` SHALL place the staged parts, or those of `--only`, by domain: the islands of `isolation_islands` without the `--barrier` parts, or `--group NAME=GLOB[,GLOB...]`. A domain's region MUST be its `--region NAME=X1,Y1,X2,Y2` (needs `--group`, same names) or one band of the outline along `--split`. A part in no domain stays, with `place.region-unassigned`. These options without the strategy MUST be `FEN-2001`.

#### Scenario: Bands by isolation islands
- **GIVEN** the bench of `tests/_regionbench.py` written as a KiCad board: `R1`, `R3` on nets `A*`, `R2`, `R4` on nets `B*`, the isolator `U5` on `A1` and `B1`, and `H1` without a net, all staged
- **WHEN** `uv run pytest tests/unit/cli/test_place_regions.py -k islands` runs `fenolite place <board> --strategy regions --barrier U5 --confirm`
- **THEN** it exits 0, `D1` is x 0 to 30 mm with `R1` and `R3`, `D2` is x 30 to 60 mm with `R2` and `R4`, `U5` is at x 30 mm with status `boundary`, and `H1` stays with `place.region-unassigned`

#### Scenario: Region options without the strategy
- **WHEN** `uv run pytest tests/unit/cli/test_place_regions.py -k "usage or need_the_strategy"` runs malformed or inconsistent `--group` and `--region` values, and `--barrier` without `--strategy regions`
- **THEN** each exits 2 with `FEN-2001`

### Requirement: Region report
`result.regions` SHALL be `null` when nothing was staged, else hold per region its `box` (relative to the outline's top-left corner), `nets`, `parts`, `placed`, `unplaced`, `area`, `used` and `fill_permille`; the barriers with `sides` and `status`; `unassigned`; and `crossings`. A crossing MUST be an open connection of `analysis.connectivity` after the moves whose two ends lie in two regions; each pair MUST give one `place.region-crossing`.

#### Scenario: Crossings between groups
- **GIVEN** the same bench
- **WHEN** `uv run pytest tests/unit/cli/test_place_regions.py -k crossings` runs `--group a=R1,R2 --group b=R3,R4 --split y --dry-run`
- **THEN** `crossings` is one row between `a` and `b` with 2 open connections on `A2` and `B2`, and `issues` holds one `place.region-crossing` warning at `a|b`

#### Scenario: A region without room through the command
- **GIVEN** the same bench
- **WHEN** `uv run pytest tests/unit/cli/test_place_regions.py -k without_room` runs `--group a=R* --region a=0mm,0mm,5mm,5mm --dry-run`
- **THEN** it exits 0 with no plan, four `place.no-room` warnings and `fill_permille` 0
