## ADDED Requirements

### Requirement: Practice checks
`fenolite analyze` SHALL offer the kinds `decoupling`, `connectivity`, `bodies`, `relief`, `necks`, `loops`, `balance` and `dead`, each read-only and run on request, each reporting facts, and each giving a finding only against a row of the user's requirements file. The requirements file MUST accept the optional tables `[[decoupling]]` (`parts` glob, `max_distance_nm`), `[[body_copper]]` (`netclass`, `parts` glob, `layers`), `[[neck]]` (`select`, `min_width_nm`) and `[[loop]]` (`name`, `pads` in order, `max_area_nm2`), without a schema step; no table has a default value.
- **Copper states.** Every row of these kinds MUST say which copper it used: `outline`, `saved_fill` or `simulated`. A zone whose file holds no fill, or whose fill is older than its outline when the backend can tell, MUST be simulated: the outline, less other nets' copper grown by the clearance in force, less earlier zones by priority, less cut-outs and keep-outs, less islands joined to no pad of the zone's net.
- **`decoupling`.** For each pad of a part whose pin type is a power input, the nearest capacitor pad on the same net, the distance along copper, and the area of the loop pin–capacitor–return. 
- **`connectivity`.** Each net whose copper, with every cut-out, keep-out and rule area applied, falls into more than one group, with the pads of each group.
- **`bodies`.** For each `[[body_copper]]` row, the copper of the class inside the plan view of the bodies of the selected parts, per forbidden layer, as `analysis.body-copper` (error).
- **`relief`.** For each pad joined to a zone by spokes, the total width of copper that crosses a ring at the pad's edge, and the capacity of that width for the pad's net current when a `[[current]]` row gives one.
- **`necks`.** Along each selected zone or band, places where the copper is narrower than `min_width_nm`, slivers narrower than the clearance in force, and acute tips.
- **`loops`.** The area enclosed by the copper path through the pads of each `[[loop]]` row, on the layers the path uses.
- **`balance`.** For each two-pad SMD part, the copper area joined to each pad within a ring of one pad size, and their ratio.
- **`dead`.** Zone islands joined to no pad, and copper of a net further than a given distance (`--dead-distance`) from every pad of that net.

#### Scenario: A pin left open by a cut-out
- **GIVEN** an authored board whose only copper joining `D1-2` to `BUS` crosses a zone cut-out, with the saved fill made before the cut-out was drawn
- **WHEN** `uv run pytest tests/unit/analysis/test_practice.py -k cutout` runs `fenolite analyze <board> --kinds connectivity --json`
- **THEN** the row of `BUS` says `simulated`, holds two groups, and `D1-2` is alone in one of them

#### Scenario: Copper of a class under a can
- **GIVEN** an authored board with `C1` (a cylindrical body of 10 mm diameter) and a `BUS` track on `F.Cu` under it, and a requirements row `[[body_copper]]` with `netclass = "HV"`, `parts = "C*"`, `layers = ["F.Cu"]`
- **WHEN** `fenolite analyze <board> --kinds bodies --requirements <file> --json` runs
- **THEN** the exit code is 5 and the issues hold one `analysis.body-copper` naming `C1`, the track and `F.Cu`

#### Scenario: Decoupling distance reported without a finding
- **GIVEN** an authored board with `U1` pin 4 on `+3V3` and `C1` 1.5 mm away along copper, and no `[[decoupling]]` row
- **WHEN** `fenolite analyze <board> --kinds decoupling --json` runs
- **THEN** the row of `U1-4` names `C1-1` with a distance of 1 500 000 nm, and no issue is reported

### Requirement: Coupling screen
`--kinds coupling --aggressor GLOB --victim GLOB` SHALL rank pairs of aggressor and victim nets by a coupling score and report each victim's reference coverage, and SHALL say that the score is a ranking, not a voltage.
- For each pair on the same layer: the parallel length (where the two nets run within a distance of three times the largest of their widths and their gap), the narrowest gap `s`, and the score `Σ ℓ / (1 + (s/h)²)` over the parallel stretches, with `h` the depth to the nearest plane of the stack-up, or the board thickness when there is none.
- For each pair on adjacent layers: the broadside overlap length.
- For each victim: the share of its track length that has copper of a plane or zone net directly under it on the nearest layer.
- Rows MUST be sorted by score; no finding MUST be reported without a requirements row.

#### Scenario: A sense net beside a phase track
- **GIVEN** an authored board where `ISENSE` runs 10 mm beside `PHASE_U` at 0.5 mm, and 30 mm beside `LED` at 3 mm
- **WHEN** `fenolite analyze <board> --kinds coupling --aggressor 'PHASE_*' --aggressor LED --victim ISENSE --json` runs
- **THEN** the first row is `PHASE_U` against `ISENSE`, and the reply's summary says that the score ranks pairs

## MODIFIED Requirements

### Requirement: Analyze command
`fenolite analyze PATH` SHALL be a read-only command (`mutates` false, schema `fenolite.analyze.v0`) in `src/fenolite/cli/cmd_analyze.py`. `PATH` is a board file that a registered backend reads (`backends.registry.for_path`); an Altium board needs no option of its own once a backend reads it.
- Options: `--kinds current,clearance,creepage` (default: all three; on request also `power`, `insulation`, `length`, `ties`, `domains`, `crossings`, `decoupling`, `connectivity`, `bodies`, `relief`, `necks`, `loops`, `balance`, `dead` and `coupling`); `--requirements FILE`; `--temp-rise KELVIN` (a decimal number of at most three decimals); `--copper-thickness LENGTH` and `--copper-thickness LAYER=LENGTH` (repeatable); `--via-plating LENGTH`; `--board-thickness LENGTH`; `--pair NET_A NET_B` (repeatable); `--within LENGTH`; `--arc-tol LENGTH`; and the options of the kinds that need them: `--tie REF`, `--tie-item ID`, `--domains A=GLOB,B=GLOB`, `--sense NET_A,NET_B`, `--barrier REFS`, `--cut X1,Y1,X2,Y2`, `--width LENGTH`, `--render FILE`, `--dead-distance LENGTH`, `--aggressor GLOB` and `--victim GLOB`. Lengths are parsed by `core.units.parse_length` and need a unit.
- Pads MUST come from the backend that read the file when it satisfies c0028's `BoardFrame`; otherwise `pads` is `None`.
- `result` MUST hold `current` and `distances` (the rows of the selected kinds, as JSON objects with the field names of the records), one key per other selected kind holding its rows, `summary`, and `inputs` (the option values in force and `boundary.source`). The rows of `clearance` and `creepage` come from one `analyze_distances` call; an unselected kind is left out of each row.
- The issues of the reports MUST be the envelope's `issues`. An issue of severity `error` gives exit code 5, as "Exit-code vocabulary" says of findings. An unknown kind, a malformed option, `--pair` with one name, or an option of a kind that is not selected MUST be a usage error (`FEN-2001`, exit 2). An unreadable requirements file MUST be `FEN-3004`, exit 3.
- The command MUST run no external tool. It MUST write no file, except the drawing of `--render`, which follows the mutation protocol. `docs/cli-contract.md` MUST document it under the heading `analyze`, with every code.

#### Scenario: Capacity of the example board
- **WHEN** `uv run pytest tests/unit/cli/test_analyze_cmd.py -k example` runs `fenolite analyze tests/data/kicad/board/two_layer.kicad_pcb --kinds current --temp-rise 10 --copper-thickness 35um --json`
- **THEN** the exit code is 0, `result.current` holds one row per track and arc of the board, each `capacity_ma` an integer, and `evidence.level` is `INFERRED` or `UNVERIFIED`

#### Scenario: Requirement not met exits 5
- **GIVEN** an authored board in `tmp_path` with the slot of "Around a slot" and a requirements file asking 12 mm of creepage
- **WHEN** `fenolite analyze <board> --kinds creepage --requirements <file> --json` runs
- **THEN** the exit code is 5 and `issues` holds one `analysis.creepage-below` error

#### Scenario: Read-only and hermetic
- **GIVEN** `subprocess.run` patched to raise and a snapshot of the folder of the board
- **WHEN** `uv run pytest tests/unit/cli/test_analyze_cmd.py -k readonly` runs the command for every kind except with `--render`
- **THEN** it succeeds and the folder is unchanged

#### Scenario: Usage error
- **WHEN** `fenolite analyze <board> --kinds thermal` runs, and `fenolite analyze <board> --kinds current --cut 0mm,0mm,1mm,1mm` runs
- **THEN** each exit code is 2 and stderr holds `FEN-2001`
