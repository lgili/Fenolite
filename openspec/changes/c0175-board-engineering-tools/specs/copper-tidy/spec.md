## ADDED Requirements

### Requirement: Prune dangling copper
`fenolite.tidy.prune(design, *, nets=None) -> TidyResult` SHALL remove, repeatedly until nothing changes, the unlocked copper of the selected nets that has a free end (a track or arc end that touches no pad, via, zone or other copper of its net) and the unlocked vias joined on fewer than two copper layers.
- Locked copper and copper written by the design script MUST never be removed.
- After the prune, the connected groups of every net MUST equal the groups before it; an item whose removal changes them MUST be kept.

#### Scenario: A stub after routing
- **GIVEN** an authored board with a routed net and a 2 mm stub of the same net that ends in the air, and a via joined only on the top layer
- **WHEN** `uv run pytest tests/unit/tidy/test_prune.py -k stub` prunes the board
- **THEN** the stub and the via are removed, and every net keeps its groups

### Requirement: Straighten runs
`fenolite.tidy.straighten(design, *, nets=None) -> TidyResult` SHALL replace a single-layer run of unlocked tracks between fixed points by a shape on the 0/45/90° lattice with fewer weighted turns, when one exists that keeps every clearance in force.
- Fixed points are pads, vias, joints of three or more items, locked items and the ends of the run.
- Turns MUST be weighted: a 45° turn costs less than a 90° turn, an acute turn is forbidden, and a turn inside the run's own pad costs nothing.
- A shape MUST keep the clearance in force to all other copper, the board edge, slots and drills, and MUST stay on the run's layer.
- Runs of a net that is in a differential pair, has a length rule, or is locked MUST be left as they are. Runs MUST be processed in a deterministic order, each against the copper of the runs before it.

#### Scenario: A staircase becomes one corner
- **GIVEN** an authored track that steps eight times between two pads, with free room around it
- **WHEN** the run is straightened
- **THEN** the result has at most two turns, both of 45°, and the copper check finds nothing

### Requirement: Chamfer joints
`fenolite.tidy.chamfer(design, *, nets=None, leg=None) -> TidyResult` SHALL replace each 90° joint of two unlocked tracks of one net, layer and width by a 45° segment, and each T-joint by a 45° entry, keeping the clearance in force; a chamfer that adds a copper-check finding MUST be undone and reported.
- The chamfer leg MUST be `leg`, or twice the track width, and MUST be shortened to half of the shorter leg of the joint when the leg would pass it.
- Zone outlines of the selected nets MUST be chamfered the same way when `--zones` is given, keeping every pad that the zone joined.

#### Scenario: A right angle
- **GIVEN** an L of two 0.3 mm tracks of one net
- **WHEN** the board is chamfered
- **THEN** the joint is a 45° segment with legs of 0.6 mm, and the net keeps its groups

### Requirement: Style report
`fenolite tidy BOARD --report [--compare REFERENCE]` SHALL report, per net class and copper layer, the counts of joints at 45°, at 90° and acute, the jogs (runs shorter than three track widths between two turns), the track widths with their lengths, and the via count, and SHALL report each acute joint as `tidy.acute` (warning) with its place. With `--compare`, the same table MUST be given for the reference board.

#### Scenario: Acute joints reported
- **GIVEN** an authored board with one 30° joint
- **WHEN** `fenolite tidy <board> --report --json` runs
- **THEN** the exit code is 0 and the issues hold one `tidy.acute` at the joint

### Requirement: Tidy command
`fenolite tidy BOARD [--nets GLOB] [--prune] [--straighten] [--chamfer [--zones]] [--leg LENGTH]` SHALL be a writing command under the mutation protocol (schema `fenolite.tidy.v0`) that runs the selected steps in the order prune, straighten, chamfer, on a KiCad board; with none of the step options it MUST run all three. `--report` MUST write nothing.
- `result` MUST list each removed, replaced and added item with its step and reason, and the counts of the style report before and after.
- The written board MUST pass `kicad-cli` DRC with no new finding when `kicad-cli` is present; otherwise the reply's evidence MUST stay below `KICAD-VERIFIED`.

#### Scenario: Dry run of the three steps
- **WHEN** `fenolite tidy board.kicad_pcb --dry-run --json` runs on an authored routed board
- **THEN** the exit code is 0, `result.plan` names the board, and `result.steps` names `prune`, `straighten` and `chamfer` in that order
