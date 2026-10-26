## ADDED Requirements

### Requirement: Ground ties
`fenolite.analysis.ties.analyze_ties(design, pads, ties, *, domains=None) -> TieReport` SHALL prove whether named tie items are the only connections between parts of one net's copper.
- A tie MUST be given as a net-tie part (`--tie REF`) or as copper items by id (`--tie-item ID`, repeatable). The items MUST be removed by their ids alone; no item MUST be removed because its copper touches or overlaps a tie.
- The copper graph of a net MUST join pads, tracks, arcs, vias and filled zone regions whose copper overlaps on a layer, and through-hole pads and vias across layers. Zone regions MUST be the filled regions of the file, or the simulated pour of "Practice checks" when the file holds none, and the row MUST say which.
- One `TieRow(tie, net, groups, split)` per tie: `groups` the connected groups after the removal, each a sorted list of `REF-PIN`, and `split` true when there are two or more.
- A tie whose removal leaves one group MUST be `analysis.tie-parallel` (error), with the shortest other path between the tie's two ends given as item ids.
- With `domains` (`--domains A=GLOB,B=GLOB`, globs on `REF-PIN`), a pad of domain A in a group that holds a pad of domain B and not the tie's A end MUST be `analysis.tie-extra` (error), naming the pad.

#### Scenario: A single tie splits the net
- **GIVEN** an authored board whose `GND` copper is a power area and a control area joined only by the track `t1`
- **WHEN** `uv run pytest tests/unit/analysis/test_ties.py -k single` runs `fenolite analyze <board> --kinds ties --tie-item t1 --json`
- **THEN** the row holds two groups, `split` is true, and no issue is reported

#### Scenario: A parallel tie through a via
- **GIVEN** the same board with a via that also joins the two areas
- **WHEN** the same command runs
- **THEN** the row holds one group, and the issues hold one `analysis.tie-parallel` whose path names the via

#### Scenario: Removal by area is not used
- **GIVEN** the same board with a second track `t2` of the power area that crosses the bounding box of `t1` without touching its copper
- **WHEN** the command runs with `--tie-item t1`
- **THEN** `t2` stays in the graph and its pads stay in the power group

### Requirement: Sense nets and isolation islands
`--kinds ties --sense NET_A,NET_B` SHALL check the sense connection of a sense element, and `--kinds domains --barrier REF[,REF...]` SHALL report the isolation islands of the net graph.
- For each sense net, copper that overlaps copper of another net on the same layer, other than at a pad of the element through a net-tie part, MUST be `analysis.sense-shared` (error), naming both items. A sense net whose copper reaches the element's pad from outside the pad's outline before joining it MUST be `analysis.sense-entry` (warning).
- `domains` MUST remove the barrier parts from the net graph of the schematic model (parts as nodes joining their nets) and report the islands of nets that remain, sorted, with the barrier parts that bound each island. It MUST read no copper.

#### Scenario: A sense track that leaves from a pour
- **GIVEN** an authored board where `ISENSE_P` starts on the pour of `DC_BUS` beside the shunt pad
- **WHEN** `fenolite analyze <board> --kinds ties --sense ISENSE_P,ISENSE_N --json` runs
- **THEN** the issues hold one `analysis.sense-shared` naming the track and the pour

#### Scenario: Islands across an isolator
- **GIVEN** an authored design whose nets on the two sides of `U5` are joined only through `U5`
- **WHEN** `fenolite analyze <design> --kinds domains --barrier U5 --json` runs
- **THEN** the result holds two islands, each bounded by `U5`

### Requirement: Barrier crossings
`fenolite.analysis.crossings.analyze_crossings(design, pads, cuts, *, width=None) -> CrossingReport` SHALL count the free ways across each cut segment on each copper layer and the connections that must cross it.
- A cut MUST be given as `--cut X1,Y1,X2,Y2` with units (repeatable). `width` (`--width`) is the track width to fit, by default the narrowest width of the board's net classes.
- On each copper layer, the obstacles along the cut MUST be: every item's copper grown by the clearance in force against a track of `width` on any net; the board edge, cut-outs and slots grown by the edge clearance; drills; and rule areas that forbid tracks on that layer. A way is a free interval of the cut; it fits `⌊(L + c) / (w + c)⌋` tracks for its length `L`, the clearance `c` and the width `w`.
- The demand MUST list, per net, the open connections whose straight line crosses the cut and the routed copper that crosses it.
- When the open demand of a cut exceeds the tracks its ways fit on all layers together, the report MUST hold `analysis.crossings-short` (warning) naming the cut and both counts.
- `--render FILE.svg` MUST draw the cut, the ways and the obstacles; it is the only write of the kind and follows the mutation protocol.

#### Scenario: Ways counted by hand
- **GIVEN** an authored board with a row of eight pads of 1 mm at a pitch of 2.54 mm across the board, a clearance of 0.2 mm and a width of 0.25 mm
- **WHEN** `uv run pytest tests/unit/analysis/test_crossings.py -k row` runs the analysis with a cut along the row
- **THEN** each of the seven gaps between pads fits two tracks on each layer, as counted by hand in the test

#### Scenario: More nets than ways
- **GIVEN** the same board with twenty open connections across the row and only the top layer allowed
- **WHEN** the analysis runs
- **THEN** the report holds one `analysis.crossings-short` naming 20 and 14

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
