## ADDED Requirements

### Requirement: Copper states of the practice checks
`fenolite.analysis.pour.pour_copper(design, *, pads, boundary, grid)` SHALL give each zone layer of a zone with a net one state: `saved_fill`, `simulated` (no fill, reason `no-fill`, or a stale fill, reason `stale: …`) or `outline` (reason `too-large`).
- A fill MUST be stale when a cell centre of it lies outside its zone outline, outside the board, in a cut-out, in a no-pour keep-out of its layer, or on a pad, track, arc or via of another net.

#### Scenario: A stale fill is simulated
- **GIVEN** the bench `cutout()` of `tests/_practicebench.py`, whose `BUS` fill was made before the keep-out `CUT`
- **WHEN** `uv run pytest tests/unit/analysis/test_practice.py -k cutout` pours it
- **THEN** the zone layer is `simulated` with the reason `stale: fill inside the keep-out CUT`

#### Scenario: Saved, unfilled and too large
- **GIVEN** `cutout(keepout=False)`, `cutout(keepout=False, fill=False)` and `cutout(fill=False)` with `MAX_CELLS` set to 100
- **WHEN** `uv run pytest tests/unit/analysis/test_practice.py -k states` pours them
- **THEN** the states are `saved_fill`, `simulated` (`no-fill`) and `outline` (`too-large`)

### Requirement: Simulated pour
The simulated pour SHALL be a raster of square cells of side `grid`, aligned on the board origin, poured by zone priority. A cell MUST be copper when its centre lies inside the zone outline and the board, at least the clearance from the board edge, outside no-pour keep-outs, and clear of other nets' copper and earlier zones by the clearance in force. Cells joined by a side are islands; an island no item of the net covers MUST be dropped.

#### Scenario: The cells of an unfilled zone
- **GIVEN** `cutout(keepout=False, fill=False)`, a zone of 52 mm by 36 mm with no copper of another net inside
- **WHEN** `uv run pytest tests/unit/analysis/test_practice.py -k states` pours it on a raster of 0.25 mm
- **THEN** the zone layer keeps 208 × 144 cells and its one island joins `J1-1` and `D1-2`

### Requirement: Connectivity kind
`fenolite.analysis.practice.analyze_groups(design, *, pads, pour)` SHALL give one row per net that owns a zone or whose copper falls into two or more groups of pads: `groups` (the sorted pads of each group), `split` and `copper` (the states of its zone layers).
- Items MUST join where they touch on a layer, and through the islands that they cover.
- A split net MUST be `analysis.net-split` (warning).

#### Scenario: A pin left open by a cut-out
- **GIVEN** `cutout()`, whose only copper joining `D1-2` to `J1-1` crosses the keep-out drawn after the fill
- **WHEN** `uv run pytest tests/unit/analysis/test_practice.py -k cutout` runs the kind
- **THEN** the row of `BUS` says `simulated`, holds the groups `D1-2` and `J1-1`, and the issues hold one `analysis.net-split`

### Requirement: Dead copper
`fenolite.analysis.practice.analyze_dead(design, *, pads, pour, distance)` SHALL report each fill polygon whose group holds no pad (`analysis.copper-dead`, warning) and, with `distance`, each track, arc, via and fill polygon whose gap to every pad of its net is larger (`analysis.copper-far`, warning), with that gap.

#### Scenario: An island and far copper
- **GIVEN** the bench `dead()`, with a fill island joined to nothing and a `B.Cu` track far from the pads
- **WHEN** `uv run pytest tests/unit/analysis/test_practice.py -k dead` runs the kind with 5 mm
- **THEN** the island is one `analysis.copper-dead`, and the track (14.375 mm) and the island are two `analysis.copper-far`

### Requirement: Decoupling distance
`fenolite.analysis.practice.analyze_decoupling(design, *, pads, pour, requirements)` SHALL give, for each pad of a pin of type power input, the nearest capacitor pad (reference `C` and a digit) on its net, the distance along copper and straight, the return pad and the loop area. A `[[decoupling]]` row of the part MUST make a larger distance, or none, `analysis.decoupling-far` (error).

#### Scenario: Decoupling distance reported without a finding
- **GIVEN** the bench `decoupling()`, with `U1` pin 4 on `+3V3` and `C1` 1.5 mm away along a track
- **WHEN** `uv run pytest tests/unit/analysis/test_practice.py -k decoupling` runs the kind without and with a row of 1 mm
- **THEN** the row of `U1-4` names `C1-1` at 1 500 000 nm with a loop of 3 mm², no issue without the row, and `analysis.decoupling-far` with it

### Requirement: Copper under part bodies
`fenolite.analysis.practice.analyze_bodies(design, *, pads, pour, extents, requirements)` SHALL report, for each `[[body_copper]]` row, part and forbidden layer, the copper of the nets of its class inside the part's plan view (its bodies, else its courtyard), the part's own pads left out, as `analysis.body-copper` (error). Without a row it MUST report `analysis.input-missing`.

#### Scenario: Copper of a class under a can
- **GIVEN** the bench `bodies()`, with an `HV` track on `F.Cu` and a `Default` track on `B.Cu` under the 10 mm body of `C1`, and a row `netclass = "HV"`, `parts = "C*"`, `layers = ["F.Cu", "B.Cu"]`
- **WHEN** `uv run pytest tests/unit/analysis/test_practice.py -k bodies` runs the kind
- **THEN** one `analysis.body-copper` names `C1`, the track and `F.Cu`, with the plan `body`, and `courtyard` once the body is removed

### Requirement: Thermal relief width
`fenolite.analysis.practice.analyze_relief(design, *, pads, pour, requirements, copper_thickness)` SHALL give, for each pad joined to a zone of its net by thermal relief, the spokes of stored fill crossing the box of its copper grown by half the thermal gap, and their width. With a `[[current]]` row and a thickness, a capacity below the current MUST be `analysis.relief-exceeded` (error).

#### Scenario: Four spokes of 0.5 mm
- **GIVEN** the bench `relief()`, a 2 mm pad in a 0.5 mm gap crossed by four spokes of 0.5 mm
- **WHEN** `uv run pytest tests/unit/analysis/test_practice.py -k relief` runs the kind with 35 um of copper and a row of one milliampere above the capacity
- **THEN** the row holds 4 spokes and 2 000 000 nm, the issues one `analysis.relief-exceeded`, and the unfilled zone a `simulated` row without width

### Requirement: Coupling screen
`fenolite.analysis.coupling.analyze_coupling(design, *, pads, aggressors, victims, board_thickness)` SHALL rank the pairs of aggressor and victim nets by `Σ ℓ / (1 + (s/h)²)` over their parallel stretches on one layer, with their parallel length, narrowest gap and broadside overlap, and give each victim's referenced share. It MUST judge nothing and say that the score ranks pairs, not a voltage.

#### Scenario: A sense net beside a phase track
- **GIVEN** the bench `coupling()`, where `ISENSE` runs 10 mm beside `PHASE_U` at 0.5 mm and 30 mm beside `LED` at 3 mm, with h 1.6 mm
- **WHEN** `uv run pytest tests/unit/analysis/test_coupling.py` runs the screen for `PHASE_*` and `LED` against `ISENSE`
- **THEN** the first row is `PHASE_U` against `ISENSE` with the score 9 110 320, and the summary says that the score ranks pairs

### Requirement: Practice requirement tables
The requirements file SHALL accept the optional tables `[[decoupling]]` (`parts`, a glob; `max_distance_nm`) and `[[body_copper]]` (`netclass` and `parts`, globs; `layers`, a non-empty array of names or globs), neither with a default value; a float, an empty array or an unknown key MUST be refused with the key named.

#### Scenario: The two tables load
- **WHEN** `uv run pytest tests/unit/analysis/test_practice.py -k tables` loads a row of each, a float distance and an empty layer list
- **THEN** the rows load, and the two faulty files are refused naming `max_distance_nm` and `layers`

### Requirement: Practice kinds in the analyze command
`fenolite analyze` SHALL accept `decoupling`, `connectivity`, `bodies`, `relief`, `dead` and `coupling` in `--kinds`, none in the default set, with `--pour-grid LENGTH`, `--dead-distance LENGTH`, `--aggressor GLOB` and `--victim GLOB`. `result` MUST hold one key per kind, `pours` and the summaries. An option without its kind, or `coupling` without both globs, MUST be `FEN-2001` (exit 2).

#### Scenario: Practice kinds through the command
- **GIVEN** the benches written as KiCad boards in `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_analyze_practice.py` runs each kind
- **THEN** `connectivity` exits 0 with the split `BUS`, `bodies` and `relief` exit 5 with their errors, the folder is unchanged, and the usage errors exit 2

### Requirement: Practice check codes
The table of analysis issue codes SHALL hold `analysis.net-split`, `analysis.copper-dead` and `analysis.copper-far` with severity `warning`, and `analysis.decoupling-far`, `analysis.body-copper` and `analysis.relief-exceeded` with severity `error`.

#### Scenario: Practice codes in the table
- **WHEN** `uv run pytest tests/unit/analysis/test_findings.py -k practice_codes` runs
- **THEN** each code has its one severity
