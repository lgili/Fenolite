## ADDED Requirements

### Requirement: Neck kind
`fenolite.analysis.shapes.analyze_necks(design, *, pour, requirements)` SHALL measure the copper of each net with a zone, per layer, on the raster of `pour`: the width of a cell is its shortest run of copper along the two axes and the two diagonals. A cell that joins two sets of wide cells, adding cells widest first, MUST be a neck of its width, and a neck below the `[[neck]]` row of its net MUST be `analysis.neck-narrow` (error).

#### Scenario: A neck of a pour
- **GIVEN** the bench `neck()` of `tests/_shapebench.py`, whose `GND` fill narrows to 0.3 mm between two keep-outs, and a row `[[neck]]` with `min_width_nm = 500000`
- **WHEN** `uv run pytest tests/unit/analysis/test_shapes.py -k necks` measures it on a raster of 0.05 mm
- **THEN** one row is a `neck` of 300 000 nm between x 20 mm and 22 mm, and the issues hold one `analysis.neck-narrow`

#### Scenario: Neck rows missing or unmatched
- **WHEN** `uv run pytest tests/unit/analysis/test_shapes.py -k necks` measures `neck()` without a row, and with a row for the net `VBUS`
- **THEN** the first reports `analysis.input-missing` and the second `analysis.requirement-unmatched`, with no row

### Requirement: Tips and slivers
In an island with wide cells, thin cells joined by a side whose wide neighbours form one patch MUST be a `tip` when they reach at least the row's width from it. An island without a wide cell MUST be a `sliver` of the width of its widest cell. Both below the row SHALL be `analysis.neck-narrow`.

#### Scenario: A finger and a strip
- **GIVEN** the bench `tips()`, a 10 mm square fill with a finger 0.3 mm wide and 3 mm long, and a separate fill 0.3 mm by 5 mm
- **WHEN** `uv run pytest tests/unit/analysis/test_shapes.py -k tips` measures it with a row of 0.5 mm
- **THEN** the rows are one `tip` and one `sliver`, each 300 000 nm wide, and no corner of the square is a tip

### Requirement: Loop kind
`fenolite.analysis.shapes.analyze_loops(design, *, pads, pour, requirements, baseline)` SHALL give, for each `[[loop]]` row, the area of the closed path through its pads in order: a leg between pads of one net that copper joins follows the shortest path along copper, any other leg is straight. An area above `max_area_nm2` MUST be `analysis.loop-area` (error); `baseline` adds the area on another board and the change.

#### Scenario: Two decoupling loops
- **GIVEN** the bench `loop()`, with `U1-4` and `C1-1` 1.5 mm apart along a track, `C2` 10 mm away, the `GND` pads 2 mm below, and rows `C1` and `C2` with `max_area_nm2` of 10 mm²
- **WHEN** `uv run pytest tests/unit/analysis/test_shapes.py -k loops` runs the kind, then with the baseline of `loop(far=25)`
- **THEN** `C1` holds 3 mm² and `C2` 20 mm² with one `analysis.loop-area`, and the change of `C2` is +10 mm²

### Requirement: Balance kind
`fenolite.analysis.shapes.analyze_balance(design, *, pads, pour)` SHALL give, for each part with exactly two SMD pads on one layer, the area of the copper of each pad's net joined to the pad inside the box of the pad grown by its larger side, the pad left out, and the ratio of the larger to the smaller in permille. It MUST judge nothing.

#### Scenario: A pad on a pour and a pad on a track
- **GIVEN** the bench `balance()`, `R1` with pad 1 in a `GND` fill and pad 2 on a 0.5 mm track
- **WHEN** `uv run pytest tests/unit/analysis/test_shapes.py -k balance` runs the kind on a raster of 0.25 mm
- **THEN** the row of `R1` holds 8 mm² and 0.5 mm², the ratio 16 000 permille, and no issue

### Requirement: Current split
`fenolite.analysis.split.analyze_split(design, *, pads, pour, power, ...)` SHALL solve each row of the power report on a raster of its net's copper, pads and vias as contacts, and give each track, arc, fill and via its share of the path's current in permille. With a resistivity it MUST give the path's resistance and whether it lies in the interval of the power row. A missing thickness, plating or stack-up MUST be `analysis.input-missing`.

#### Scenario: Two strips share by thickness
- **GIVEN** `two_strips()` of `tests/_power.py` with 70 µm of copper on `F.Cu` and 35 µm on `B.Cu`
- **WHEN** `uv run pytest tests/unit/analysis/test_power_split.py` solves the path `J1-1` to `U1-1`
- **THEN** the strips carry 667 and 333 permille, and the resistance lies within the interval of `power`

#### Scenario: Vias in parallel
- **GIVEN** `via_array(4)` with a stack-up and a plating of 25 µm
- **WHEN** `uv run pytest tests/unit/analysis/test_power_split.py` solves it, then without the plating
- **THEN** the four vias carry the whole current between them, the resistance lies within the interval of `power`, and without the plating the row is not solved and the issues name `via plating`

### Requirement: Pour shape tables
The requirements file SHALL accept the optional tables `[[neck]]` (`select`, a net or net-class glob table; `min_width_nm`) and `[[loop]]` (`name`; `pads`, two or more pad names; optional `max_area_nm2`), neither with a default value; a float, a short pad list, a repeated loop name or an unknown key MUST be refused with the key named.

#### Scenario: The two tables load
- **WHEN** `uv run pytest tests/unit/analysis/test_shapes.py -k tables` loads a row of each and three faulty files
- **THEN** the rows load, and the faulty files are refused naming `min_width_nm`, `pads` and `name`

### Requirement: Pour shape kinds in the analyze command
`fenolite analyze` SHALL accept `necks`, `loops` and `balance` in `--kinds`, none in the default set, `--split` with `power` and `--loop-baseline FILE` with `loops`; `--pour-grid` serves them. `result` MUST hold `necks`, `loops`, `balance` and `split`. An option without its kind MUST be `FEN-2001` (exit 2).

#### Scenario: Pour shape kinds through the command
- **GIVEN** the benches written as KiCad boards in `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_analyze_shapes.py` runs each kind and `--split`
- **THEN** `necks` and `loops` exit 5 with their errors, `balance` and `power --split` exit 0, the folder is unchanged, and the usage errors exit 2

### Requirement: Pour shape codes
The table of analysis issue codes SHALL hold `analysis.neck-narrow` and `analysis.loop-area`, each with the severity `error`.

#### Scenario: Pour shape codes in the table
- **WHEN** `uv run pytest tests/unit/analysis/test_findings.py -k shape_codes` runs
- **THEN** each code has the one severity `error`
