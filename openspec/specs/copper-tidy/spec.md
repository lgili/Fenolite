# copper-tidy Specification

## Purpose
Copper left behind by routers, rips and hand edits is cleaned by `fenolite tidy`: dangling copper pruned, joints chamfered (and, from c0214, runs straightened), each edit kept only when its net keeps its connected groups and the copper check finds nothing new, with `--drc` to judge the result by KiCad's DRC.

## Requirements

### Requirement: Prune dangling copper
`fenolite.tidy.prune(design, *, pads, nets=None, keep=()) -> TidyResult` SHALL remove, pass after pass until one removes nothing, each unlocked track or arc of the selected nets with a free end (the disc of its width at that end touches no other copper and no zone outline of its net on its layer) and each unlocked via joined on fewer than two copper layers. Items of `keep` MUST stay.

#### Scenario: A stub after routing
- **GIVEN** an authored board with a routed net, a 2 mm stub of it that ends in the air, and a lead to a via joined only on the top layer
- **WHEN** `uv run pytest tests/unit/tidy/test_prune.py -k stub` prunes the board
- **THEN** the stub, the via and then the lead are removed, and every net keeps its groups

### Requirement: Prune keeps the groups
A removal SHALL be kept only when the remaining copper of its net is grouped exactly as before (two items touch on one layer, as in "Open connections of a net"). A track or an arc with a free end whose removal would split its net MUST stay, with `tidy.kept` (info). A net with copper that could not be shaped MUST be left as it is, with `tidy.net-skipped` (warning).

#### Scenario: A bridge with a free end
- **GIVEN** an authored net whose only path between two pads is a track that runs on to a free end
- **WHEN** `uv run pytest tests/unit/tidy/test_prune.py -k bridge` prunes the board
- **THEN** nothing is removed and one `tidy.kept` names that track

### Requirement: Chamfer right-angle joints
`fenolite.tidy.chamfer(design, *, pads, check, nets=None, keep=(), leg=None) -> TidyResult` SHALL replace each point where exactly two unlocked horizontal or vertical tracks of one net, layer and width end at 90°, with nothing else of the net there, by a 45° track between the two ends moved back by the leg: `leg`, or twice the width, at most half of the shorter track. A track cut to nothing MUST be removed.

#### Scenario: A right angle
- **GIVEN** an L of two 0.3 mm tracks of one net
- **WHEN** `uv run pytest tests/unit/tidy/test_chamfer.py -k right_angle` chamfers the board
- **THEN** the joint is a 45° track with legs of 0.6 mm, and the net keeps its groups

### Requirement: Chamfers are checked
A chamfer SHALL be kept only when its net keeps its groups and `check`, a copper check of the whole design, finds nothing that the design before lacks (a new pair of items, or a smaller gap). A chamfer whose tracks a new finding names MUST be undone, and the check run again, until it finds nothing new; a new finding that names no chamfer MUST undo them all. Each undone chamfer gives `tidy.chamfer-undone` (info).

#### Scenario: A chamfer too close
- **GIVEN** an authored corner with a pad of another net inside it, clear of both tracks but not of their chamfer
- **WHEN** `uv run pytest tests/unit/tidy/test_chamfer.py -k too_close` chamfers the board with the copper check
- **THEN** the design is unchanged and one `tidy.chamfer-undone` names `copper.clearance`

### Requirement: Tidy command
`fenolite tidy PATH [--nets GLOB]... [--prune] [--straighten] [--chamfer] [--zones] [--leg LENGTH] [-o FILE]` SHALL be a writing command under the mutation protocol (schema `fenolite.tidy.v0`) on a KiCad board that runs the selected steps in the order prune, straighten, chamfer, all three when none is given; `--zones` needs chamfer. Locked items and script copper MUST stay. `result` MUST list each edit with its step, reason, net, layer, point and the ids it removed, replaced and added.

#### Scenario: Dry run of the steps
- **WHEN** `uv run pytest tests/unit/cli/test_tidy_cmd.py -k dry_run` runs `fenolite tidy tidy.kicad_pcb --dry-run --json` on the authored bench
- **THEN** the exit code is 0, `result.plan` names the board, and `result.steps` is `prune`, `straighten`, `chamfer`

### Requirement: Tidy command checks the result
`fenolite tidy` SHALL judge each edit with the copper check and the rules of the project beside the board, and the tidied board once more: a finding it lacked before gives `tidy.check-failed` (error) and no write. With `--drc`, `kicad-cli` DRC MUST run on copies of both boards; a violation type that grows gives `tidy.drc-new` (error) and no write, else the evidence is `KICAD-VERIFIED`. Without it the evidence MUST stay `INFERRED` or lower.

#### Scenario: KiCad finds nothing new
- **GIVEN** the authored bench written for the running `kicad-cli` with a project that holds its clearance
- **WHEN** `uv run pytest tests/kicad/tidy -k no_drc` runs `fenolite tidy <board> --drc --confirm`
- **THEN** the exit code is 0, the evidence is `KICAD-VERIFIED`, and no DRC violation type has more entries than before

### Requirement: Tidy codes
The codes `tidy.check-failed`, `tidy.drc-new` (error), `tidy.acute`, `tidy.net-skipped`, `tidy.project-unread` (warning), `tidy.chamfer-undone`, `tidy.fill-stale`, `tidy.kept` and `tidy.straighten-skipped` (info) SHALL be the table `fenolite.tidy.codes.ISSUE_CODES`, each explained by `fenolite explain` and listed under "tidy" in `docs/cli-contract.md`.

#### Scenario: Every code is explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs
- **THEN** every `tidy.*` code has an entry whose `see` is the heading `tidy`

### Requirement: Straighten runs
`fenolite.tidy.straighten(design, *, pads, check, nets=None, keep=()) -> TidyResult` SHALL replace each run (a chain of two or more unlocked tracks of one net, layer and width whose inner joints join nothing else) by a shape of at most three segments at 0°, 45° or 90° between the run's two ends, when the shape weighs fewer turns, touches only what the run's ends touched, keeps the net's groups and adds no finding of `check`.

#### Scenario: A staircase becomes one corner
- **GIVEN** an authored track that steps eight times between two pads, with free room around it
- **WHEN** `uv run pytest tests/unit/tidy/test_straighten.py -k staircase` straightens the board
- **THEN** the run has at most two turns, both of 45°, the net keeps its groups and the copper check finds nothing

### Requirement: Turn costs
A turn SHALL weigh 1 at 45° and 3 at 90°; a turn inside a pad that the run ends on MUST weigh nothing, and the joints with other tracks that end at or pass through the run's ends MUST count as turns. A new shape MUST NOT make an acute angle. The shapes that weigh less than the run MUST be tried lightest first, then shortest, then in a fixed order.

#### Scenario: A blocked shape is passed over
- **GIVEN** a staircase whose lightest shape passes a pad of another net too closely
- **WHEN** `uv run pytest tests/unit/tidy/test_straighten.py -k blocked` straightens it
- **THEN** a heavier shape that keeps the clearance replaces the run, and the copper check finds nothing

### Requirement: Runs left alone
A net in a differential pair (an interface of a pair kind, or the KiCad name rule) or selected by a rule of kind `length`, `skew` or `diff_pair_skew` MUST NOT be straightened, with `tidy.straighten-skipped` (info). Locked tracks and items of `keep` MUST end runs. Runs MUST be processed by net name, layer and smallest track id, each against the copper of the runs before it.

#### Scenario: A pair stays
- **GIVEN** a staircase of net `D_P` on a board that also has the net `D_N`
- **WHEN** `uv run pytest tests/unit/tidy/test_straighten.py -k pair` straightens the board
- **THEN** nothing changes and one `tidy.straighten-skipped` names `D_P`

### Requirement: Chamfer T-joints
`fenolite.tidy.chamfer` SHALL also turn each T-joint into a 45° entry: an unlocked horizontal or vertical track (the stem) that ends at 90° on the middle of a track of its net, layer and width, or on the joint of two collinear ones, with nothing else there, gets its end moved back by the leg and joined by a 45° track to the bar, on the side with more bar. Entries MUST be kept under "Chamfers are checked".

#### Scenario: A T-joint
- **GIVEN** a track of one net that ends at 90° on the middle of another track of that net
- **WHEN** `uv run pytest tests/unit/tidy/test_chamfer.py -k tee` chamfers the board
- **THEN** the joint is a 45° entry, and the net keeps its groups and adds no copper-check finding

### Requirement: Chamfer zone outlines
With `zones=True`, `chamfer` SHALL cut each convex right-angle corner of a horizontal and a vertical edge of the outline of an unlocked zone of a selected net by a 45° edge, with legs of `leg`, else 1 mm, at most half of each edge. A cut that leaves a pad, via, track or arc of the net that touched the outline without contact MUST be undone. A cut zone MUST lose its fill.

#### Scenario: A zone corner
- **GIVEN** a rectangular zone of a net with a pad of that net in one corner only
- **WHEN** `uv run pytest tests/unit/tidy/test_chamfer.py -k zone` chamfers it with `zones=True`
- **THEN** three corners are cut by 45° edges, the corner with the pad stays, and the zone has no fill

### Requirement: Style report
`fenolite.tidy.style(design, *, nets=None)` SHALL count, per net class and copper layer, the joints of two tracks at 45°, at 90°, acute and at other angles, the jogs (a track shorter than three widths between two turns) and the length per track width, and per net class the vias. Each acute joint MUST give `tidy.acute` (warning) with its place.

#### Scenario: Acute joints reported
- **GIVEN** an authored board with one 30° joint
- **WHEN** `fenolite tidy <board> --report --json` runs
- **THEN** the exit code is 0 and the issues hold one `tidy.acute` at the joint

### Requirement: Tidy report option
`fenolite tidy PATH --report [--compare REFERENCE]` SHALL run no step, plan nothing and give the style report in `result.report`; `--compare` MUST imply `--report` and give the report of the KiCad board REFERENCE in `result.compare`. A step option or `--zones` with it MUST be a usage error. A run of steps MUST give `result.style`, the counts of the report before and after.

#### Scenario: A style compared
- **WHEN** `uv run pytest tests/unit/cli/test_tidy_cmd.py -k compare` runs `fenolite tidy tidy.kicad_pcb --compare ref.kicad_pcb --json`
- **THEN** the exit code is 0, nothing is planned, and `result.compare.board` is `ref.kicad_pcb`
