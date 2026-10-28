## ADDED Requirements

### Requirement: Region renders
`fenolite render BOARD --region X1,Y1,X2,Y2 -o DIR` SHALL write `DIR/region.svg` under the mutation protocol, drawn by Fenolite from the model with no tool.
- It MUST hold, clipped to the rectangle, the pads, tracks, arcs, vias, holes, slots, zone copper and board edge whose box meets it, and a grid labelled in board millimetres.
- `--nets` MUST add one net label per pad with a net in the rectangle; `--open` the open connections as lines.

#### Scenario: Open connections in a region
- **GIVEN** the authored bench of `tests/_regionviewbench.py`, with two open connections and five pads with a net inside 0..20 mm
- **WHEN** `uv run pytest tests/unit/cli/test_render_region.py -k open_connections` runs `fenolite render <board> --region 0mm,0mm,20mm,20mm --nets --open -o views --confirm`
- **THEN** the exit code is 0 and `views/region.svg` holds two lines of the class `open` and one `net-label` per pad, no tool having run

### Requirement: Region render elements
Every element of a region render SHALL carry a `class` and `data-*` attributes naming its net, layer and item, and SHALL give its coordinates in millimetres with the exact digits of their nanometres; the same board SHALL give the same bytes.

#### Scenario: Items of the region
- **WHEN** `uv run pytest tests/unit/analysis/test_region_render.py -k items` draws the bench
- **THEN** the slot is `M9.25 10 L10.75 10` of width `0.5`, the via a circle of radius `0.3` at 10,18, the saved fill `M2 17 L18 17 L18 19 L2 19 Z`, and no item of the parts outside the region is drawn

### Requirement: Region render copper
A region render SHALL draw each zone layer in its state of `analysis.pour`: a saved fill as its polygons, a simulated pour as its cells, an outline-state zone as its outline. `result.region.copper` MUST list the states used, and a zone not drawn from a saved fill MUST give `render.copper-simulated` (info). The open connections MUST follow that copper.

#### Scenario: An unfilled zone
- **GIVEN** the bench with its `GND` zone unfilled
- **WHEN** `uv run pytest tests/unit/cli/test_render_region.py -k unfilled` renders the region
- **THEN** the zone is drawn with `data-state="simulated"`, `copper` is `["simulated"]`, and the only issue is `render.copper-simulated`

### Requirement: Region render cut overlay
`render --region` SHALL take `--cut X1,Y1,X2,Y2` (repeatable) with `--cut-width` and `--cut-clearance` and SHALL draw each cut and its ways per copper layer as `analyze --kinds crossings` gives them, each way with its number of tracks; `result.region.cuts` MUST hold each cut's supply and demand.

#### Scenario: A cut and its ways
- **GIVEN** the row bench of `tests/_crossbench.py` with two links
- **WHEN** `uv run pytest tests/unit/cli/test_render_region.py -k cut` renders 5..35 mm with the cut along the row at 0.25 mm and 0.2 mm
- **THEN** the SVG holds one `cut` and fourteen `way` lines of two tracks, the first on `F.Cu` from 10.7 mm, and the supply is 28

### Requirement: Region render refusals
A region without area or units, `--region` with `--svg` or `--png`, a region option without `--region`, a cut option without `--cut`, and a grid of more than 200 lines on one axis SHALL exit 2 (`FEN-2001`) naming the option, and nothing is written.

#### Scenario: Region options refused
- **WHEN** `uv run pytest tests/unit/cli/test_render_region.py -k usage` runs each refused form with `--dry-run`
- **THEN** each exits 2 with `FEN-2001` and `where` naming the option, and no folder is made
