## ADDED Requirements

### Requirement: Region placement
`placement.regions.place_regions(regions, members, barriers, *, occupied, …)` SHALL first centre each barrier box across the boundary of the regions of its two sides, then pack each region's boxes with `placement.grid.place`, in region order.
- A barrier whose sides share no boundary MUST be packed in its first side's region, with status `inside`.
- A box that fits nowhere MUST get no position and be listed in its row's `unplaced`.
- Equal inputs MUST give equal results.

#### Scenario: A barrier across the boundary
- **GIVEN** two 20 × 10 mm regions side by side, two 4 × 1 mm boxes for the first, one for the second, and a barrier box joining them
- **WHEN** `uv run pytest tests/unit/placement/test_regions.py -k straddles` calls `place_regions` twice
- **THEN** both results are equal, the barrier's position lies on the boundary x 20 mm, each box lies in its region, and the first row's `fill_permille` is 40

#### Scenario: A barrier between regions that do not touch
- **GIVEN** three regions in a row and a barrier joining the outer two
- **WHEN** `uv run pytest tests/unit/placement/test_regions.py -k without_a_boundary` runs
- **THEN** the barrier's status is `inside` and it lies in the first region

#### Scenario: A region too small
- **GIVEN** a 5 × 5 mm region and a 4 × 1 mm box, with the default margin of 1 mm
- **WHEN** `uv run pytest tests/unit/placement/test_regions.py -k no_room` runs
- **THEN** the box has no position, is the row's only `unplaced` path, and a region name that is not given raises `ValueError`

### Requirement: Region bands
`placement.regions.split(box, weights, *, axis, minimums)` SHALL cut `box` into one band per weight along `axis`: each band first gets its minimum, the rest MUST be shared in proportion to the weights (a weight below 1 counts as 1), cuts rounded down to whole nanometres, the last band taking the rest. `band_order(names, links)` SHALL order domains so that the two names of each link are neighbours where a chain allows it.

#### Scenario: Bands and their order
- **WHEN** `uv run pytest tests/unit/placement/test_regions.py -k "split or band_order or boundary"` runs
- **THEN** a 60 mm box with equal weights gives two 30 mm bands, minimums that do not fit leave the weights alone, the links `A-C` and `C-B` give the order `A, C, B`, and two regions with a third between them have no boundary

### Requirement: Region placement codes
`placement.ISSUE_CODES` SHALL hold `place.region-unassigned`, `place.region-barrier` and `place.region-crossing`, each with the severity `warning`; `docs/cli-contract.md` and `fenolite explain` MUST document each.

#### Scenario: Region codes in the table
- **WHEN** `uv run pytest tests/unit/placement/test_place_codes.py tests/unit/cli/test_explain_cmd.py` runs
- **THEN** each code has the severity `warning`, appears in `docs/cli-contract.md`, and has an entry in `explain.toml`
