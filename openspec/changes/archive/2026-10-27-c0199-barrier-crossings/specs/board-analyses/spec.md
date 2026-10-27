## ADDED Requirements

### Requirement: Barrier crossings
`fenolite.analysis.crossings.analyze_crossings(design, *, pads, cuts, width=None, clearance=None)` SHALL count the free ways across each cut on each copper layer.
- `width` and `clearance` are those of a new track; by default the narrowest class width and its class's clearance. Without either, no way MUST be counted, with `analysis.input-missing`.
- A way is a free interval of the cut between obstacles. It MUST fit `⌊(L + c) / (w + c)⌋` tracks for its length `L`.

#### Scenario: Ways counted by hand
- **GIVEN** the authored board `row()` of `tests/_crossbench.py`: eight through-hole pads of 1 mm at a pitch of 2.54 mm, a clearance of 0.2 mm, and a width of 0.25 mm
- **WHEN** `uv run pytest tests/unit/analysis/test_crossings.py -k row` runs the analysis with the cut from the centre of the first pad to the centre of the last
- **THEN** each of the seven gaps fits two tracks on each layer, as counted by hand in the bench, and the supply is 28

### Requirement: Crossing obstacles
`analyze_crossings` SHALL block the cut, on each copper layer, where a new track may not lie.
- Item copper MUST grow by the larger of `clearance` and the item's class clearance.
- The board edge and the cut-outs MUST grow by the board-wide edge clearance, else `clearance`; the cut outside the outline is blocked.
- Holes without copper MUST grow by `clearance`, and rule areas that forbid tracks block their layers.

#### Scenario: A cut that leaves the board
- **GIVEN** the board `row()` and a cut from x −5 mm to x 65 mm at y 5 mm, beyond the 60 mm board
- **WHEN** `uv run pytest tests/unit/analysis/test_crossings.py -k edge` runs the analysis
- **THEN** each layer holds one way, from 0.2 mm inside the left edge to 0.2 mm inside the right edge

### Requirement: Crossing ways and demand
`analyze_crossings` SHALL give one `CrossingRow` per cut with its ways, its supply and its demand.
- Each layer MUST list its ways and its obstacles; `supply` is the tracks of all layers.
- The demand MUST list, per net, the open connections whose line meets the cut and the tracks and arcs that touch it.
- When the open connections exceed the supply, the report MUST hold `analysis.crossings-short` (warning) naming the cut and both counts.

#### Scenario: More nets than ways
- **GIVEN** the board `row(links=20, top_only=True)`: twenty open connections across the row, and a rule area that forbids tracks on `B.Cu`
- **WHEN** `uv run pytest tests/unit/analysis/test_crossings.py -k more_nets` runs the analysis
- **THEN** `B.Cu` has no way, and the report holds one `analysis.crossings-short` naming 20 and 14

### Requirement: Crossings kind in the analyze command
`fenolite analyze` SHALL accept `crossings` in `--kinds` as a kind that is not in the default set.
- It needs `--cut X1,Y1,X2,Y2` (repeatable, lengths with units); `--width` and `--clearance` are optional.
- `result.crossings` MUST hold the rows and `result.summary.crossings` the counts; `result.inputs` gains the options.
- An option without the kind, the kind without `--cut`, or a malformed cut MUST be `FEN-2001` (exit 2).

#### Scenario: Ways through the command
- **GIVEN** the board `row()` written as a KiCad board in `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_analyze_crossings.py -k row` runs `fenolite analyze <board> --kinds crossings --cut 10mm,20mm,27.78mm,20mm --width 0.25mm --clearance 0.2mm --json`
- **THEN** the exit code is 0, the row's supply is 28, and the folder is unchanged

#### Scenario: Usage errors of the crossings kind
- **WHEN** `fenolite analyze <board> --kinds crossings` or `fenolite analyze <board> --kinds crossings --cut 10mm,20mm,27mm` runs
- **THEN** the exit code is 2 and stderr holds `FEN-2001`

### Requirement: Crossings analysis code
The table of analysis issue codes SHALL hold `analysis.crossings-short` with severity `warning`.

#### Scenario: Crossings code in the table
- **WHEN** `uv run pytest tests/unit/analysis/test_findings.py -k crossings_code` runs
- **THEN** the code has severity `warning`, and `issue("analysis.crossings-short", ..., severity="error")` raises `ValueError`
