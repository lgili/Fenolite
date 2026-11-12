## MODIFIED Requirements

### Requirement: Current split
`fenolite.analysis.split.analyze_split(design, *, pads, pour, power, ..., deadline=None)` SHALL solve each row of the power report on an adaptive mesh of its net's copper (`analysis.mesh`, change c0503): a quadtree per layer whose leaves are large inside plain copper and of the cell size `h` (the pour grid) along copper edges, holes, pads and vias, pads and vias as contacts, solved coarse to fine. It SHALL give each track, arc, fill and via its share of the path's current in permille, and `cell_nm`, the cell size of the finest level solved. With a resistivity it MUST give the path's resistance and whether it lies in the interval of the power row. A missing thickness, plating or stack-up MUST be `analysis.input-missing`. Zones without a saved fill MUST take the cells of `pour_copper` at size `h`.

#### Scenario: Two strips share by thickness
- **GIVEN** `two_strips()` of `tests/_power.py` with 70 µm of copper on `F.Cu` and 35 µm on `B.Cu`
- **WHEN** `uv run pytest tests/unit/analysis/test_power_split.py` solves the path `J1-1` to `U1-1`
- **THEN** the strips carry 667 and 333 permille, and the resistance lies within the interval of `power`

#### Scenario: Vias in parallel
- **GIVEN** `via_array(4)` with a stack-up and a plating of 25 µm
- **WHEN** `uv run pytest tests/unit/analysis/test_power_split.py` solves it, then without the plating
- **THEN** the four vias carry the whole current between them, the resistance lies within the interval of `power`, and without the plating the row is not solved and the issues name `via plating`

#### Scenario: Fewer cells than the raster
- **GIVEN** the bench `plane_board(holes=48)` of `tests/_power.py` (100 mm × 80 mm, ground fills on both layers)
- **WHEN** `uv run pytest tests/unit/analysis/test_mesh.py -k count` meshes its ground net at 0.1 mm
- **THEN** the mesh has fewer than a tenth of the cells of the raster of the same copper, and every raster cell's centre lies in exactly one leaf

## ADDED Requirements

### Requirement: Staged region bounds
`analysis.power` SHALL bound each active region of a path in stages (change c0503): stage 0 with `ℓ₀`, the exact distance between its two port hulls, and `A₀`, the region's whole area, giving `low₀ = R_s·ℓ₀²/A₀`; stage 1 with the narrowest section `w`, giving the capacity and `high₀ = R_s·A₀/w²`; stage 2 with the exact `ℓ` and `A` of "Power path voltage drop". Without a deadline every region MUST reach stage 2, and the rows MUST equal those of the analysis before this change. With a deadline, stage 2 MUST run first for the regions of rows whose judgment is undecided at stage 1, widest interval first, then by `where`. Each interval MUST contain the stage-2 interval of the same region.

#### Scenario: Bounds contain the exact interval
- **GIVEN** the regions `strip`, `dumbbell`, `split4` and `spokes` of `tests/_power.py`
- **WHEN** `uv run pytest tests/unit/analysis/test_power_stages.py -k contain` computes each region at stage 0, 1 and 2
- **THEN** each stage's `low` is at most the next stage's, each `high` at least the next stage's, and stage 2 equals `region_bounds`

#### Scenario: No deadline, no change
- **WHEN** `uv run pytest tests/unit/analysis/test_power.py tests/unit/analysis/test_power_benches.py` runs
- **THEN** every existing scenario passes with the same values

### Requirement: Deadline of power and split
`analyze_power` and `analyze_split` SHALL take `deadline`, an `analysis.deadline.Deadline` or `None` (change c0503). When it passes, the report MUST keep the finished work: each power row its regions at the stage they reached with sound intervals, each split row its finest finished level with `cell_nm`; each row cut short MUST have `complete` false, and the report MUST hold one `analysis.deadline` warning naming the rows, the regions below stage 2 and the split level reached. A judgment MUST rest only on values that prove it: a cut row MUST NOT give `analysis.path-exceeded` or `analysis.drop-above` that the complete row would not give.

#### Scenario: A cut run is sound
- **GIVEN** the bench `plane_board(holes=48)` with a `[[path]]` row and a fake clock that passes the deadline after the first region
- **WHEN** `uv run pytest tests/unit/analysis/test_power_deadline.py -k sound` runs the analysis with and without the deadline
- **THEN** the cut row has `complete` false, its `resistance_uohm` contains the complete row's, the report holds `analysis.deadline`, and its errors are a subset of the complete run's

#### Scenario: A cut split keeps a coarse level
- **WHEN** the split of the same bench is cut after its second level
- **THEN** the row has shares, `cell_nm` is four times the grid or more, `complete` is false, and each share is within 50 permille of the complete run's

### Requirement: Deadline and planned bytes in analyze
`fenolite analyze` SHALL accept `--deadline SECONDS` (default 120, `0` for none), applied to the kind `power` and to `--split`, and `--after-plan PLAN_ID`, which analyzes the bytes that the staged plan would write to `PATH` instead of the file (change c0503). `inputs.deadline` MUST give the value in force and each `power` and `split` row its `complete`. With `--after-plan`, the plan's recorded digest of the file it would replace MUST equal the digest of `PATH`, else the command MUST exit 4 with `FEN-4002`; a plan that writes nothing to `PATH` MUST exit 2 with `FEN-2001`; the reply's `input` MUST hold `planned` (the plan id) and the digest of the planned bytes. The command MUST still write no file.

#### Scenario: Analyze a planned route before writing it
- **GIVEN** an authored two-layer board in `tmp_path` and a plan of `fenolite path <board> --net VBUS --from J1-1 --to U1-1 --width 1mm --dry-run` that adds a track
- **WHEN** `uv run pytest tests/unit/cli/test_analyze_cmd.py -k after_plan` runs `fenolite analyze <board> --kinds power --path J1-1:U1-1 --after-plan <id> --json`
- **THEN** the exit code is 0, the power row holds the planned track as an active element, the board file is unchanged, and `input.planned` is the id

#### Scenario: A stale plan
- **WHEN** the board is changed after the plan was made and the same command runs
- **THEN** the exit code is 4 and stderr holds `FEN-4002`

### Requirement: Power analysis time budget
The power analysis and the split SHALL finish the authored bench `plane_board(holes=300, round=True)` of `tests/_power.py` (100 mm × 80 mm, two layers, a ground fill on each with 300 round 2 mm clearance holes, 30 vias, 20 pads, a path between opposite corners) complete, without a deadline (change c0503): `analyze_power` in under 20 s and `analyze_split` at 0.1 mm in under 60 s on the GitHub Linux runner of the unit job. The test MUST record the measured times in its output.

#### Scenario: The plane bench in budget
- **WHEN** `uv run pytest tests/unit/analysis/test_power_speed.py -m slow` runs on CI
- **THEN** both rows are `complete`, `analyze_power` took under 20 s and `analyze_split` under 60 s, and the split's resistance lies in the power row's interval
