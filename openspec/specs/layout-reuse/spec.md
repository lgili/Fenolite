# layout-reuse Specification

## Purpose
A block of a reference board is copied onto a target by a rigid fit over its pads (`place --strategy reuse`), with its tracks, vias and zones when asked, every copy checked; groups of parts are turned, shifted or posed with the copper they own (`place --strategy group`).

## Requirements

### Requirement: Rigid fit of a block
`fenolite.reuse.fit_block(reference, target, parts, *, anchor=None, mapping=None, tolerance=50_000) -> BlockFit` SHALL fit the block transform on the anchor's pads (the first part by default), paired by numbers found once in both footprints, over four quarter turns and both mirrors by least squares; the fit within `tolerance` with the mirror the anchor's sides give wins, then the smallest residual. The anchor MUST keep its placement.

#### Scenario: A mirrored reference is found
- **GIVEN** an authored reference block `U1`, `R1`–`R4` read with the Y axis up, and a target board with the same parts
- **WHEN** `uv run pytest tests/unit/reuse/test_fit.py -k mirror` fits the block
- **THEN** the block transform holds a mirror, every pad lands within 1 µm of its goal, and the placements equal those from the Y-down reference

### Requirement: Parts placed by their pads
Each part SHALL be fitted by its own pads onto the block transform of its reference part's pads (`mapping` gives `TARGET=REFERENCE` when the references differ), and its new placement MUST be that fit composed with its placement, its side decided by the fit. `PartFit` MUST hold the pads paired, the count within the tolerance, the largest distance and `side_changed`; a part placed on the side opposite to the block's gives `reuse.mirror-suspected`.

#### Scenario: A mirrored footprint is suspected
- **GIVEN** a block whose part `U2` has, on the target board, the mirror image of its reference footprint
- **WHEN** `uv run pytest tests/unit/reuse/test_fit.py -k "suspected or other_side"` fits the block
- **THEN** `U2` is placed on the bottom with one `reuse.mirror-suspected`, its pads on their goals, and a block whose anchor lies on the bottom places every part on the other side without a warning

### Requirement: A part without a fit
A part with no pad paired by number, or whose best fit leaves a pad farther than `tolerance` from its goal, MUST stay unplaced with `reuse.no-fit` (error). An anchor without a fit MUST give no block transform and place nothing. A part missing from either board MUST give `reuse.unknown-part` (error).

#### Scenario: A part without a fit
- **GIVEN** the block where the target's `R3` has a footprint of another pitch
- **WHEN** `uv run pytest tests/unit/reuse/test_fit.py -k without_a_fit` fits the block
- **THEN** `R3` stays unplaced, the result holds one `reuse.no-fit` naming it, and the other parts are placed

### Requirement: Placement of a copied block
The command SHALL move each placed part with its library definition when its angle or side changes, then measure every moved pad on the board frame against its goal (`reuse.check-failed` beyond the tolerance), and run the copper check with the project's rules on the board before and after the moves: a new finding MUST be `reuse.check-failed` (error), and nothing is written.

#### Scenario: A part moved onto copper
- **GIVEN** the target board with a track of another net under the place of `R1-1`
- **WHEN** `uv run pytest tests/unit/cli/test_place_reuse.py -k onto_copper` runs the strategy
- **THEN** the exit code is 5, one `reuse.check-failed` names `copper.short`, and no write is planned

### Requirement: Copper of a copied block
`fenolite.reuse.copy_copper(fit, reference, target, *, items=None) -> CopperCopy` SHALL map the reference tracks, arcs and vias of the block's nets through the block transform, each net to the target net of the pads paired with its pads, each layer to its name or, when the anchor changed side, to its mirror in the stack. An item whose net two target nets claim (`net-ambiguous`) or whose layer has no image (`layer-unknown`) MUST be dropped.

#### Scenario: Nets and layers of the copy
- **GIVEN** the block copied onto a target whose anchor lies on the bottom, and a target where `R2-2` is on another net than the other ground pads
- **WHEN** `uv run pytest tests/unit/reuse/test_copper.py -k "flips or claimed"` copies the copper
- **THEN** the copies lie on `B.Cu` on their pads, and the ground copper is dropped as `net-ambiguous`

### Requirement: Settling the copied copper
With `--copper`, the copy SHALL be the copper joined to paired pads through tracks, arcs, vias and paired pads, settled pass after pass: `tidy.prune` removes copies with a free end or vias joined on fewer than two layers; a group holding neither two pads nor one pad with a fill or board copper is an `island`; a copy a new copper-check finding names goes with its code. Kept copies MUST be locked.

#### Scenario: Copper that ends nowhere is pruned
- **GIVEN** the reference block with a track of `R2`'s net that ends on a test pad not in the block, and a lead to a via that joins nothing on `B.Cu`
- **WHEN** `uv run pytest tests/unit/reuse/test_copper.py -k "nowhere or island or clashes"` settles the copy
- **THEN** that track is not written and is named with `free-end`, the lead and its via go, the two tracks between paired pads stay locked, a loop without pads goes as `island`, and a track that would short goes with its code

### Requirement: Reuse strategy of place
`fenolite place BOARD --strategy reuse --from REFERENCE --only REFS [--anchor REF] [--map TARGET=REFERENCE]... [--copper] [--tolerance L] [--drc]` SHALL copy the block under the protocol, legality check and placement rules of `place`; `--from` implies the strategy. `result.reuse` MUST hold the transform, the per-part fit and the copied and dropped copper. `--force` and the options with another strategy MUST be `FEN-2001`.

#### Scenario: Dry run of a block
- **WHEN** `uv run pytest tests/unit/cli/test_place_reuse.py -k dry_run` runs `fenolite place target.kicad_pcb --from reference.kicad_pcb --only U1,R1,R2 --copper --dry-run --json` on authored boards
- **THEN** the exit code is 0, `result.plan` names the target board, `result.reuse.copper.copied` is 2, and nothing is written

### Requirement: Reuse with DRC
With `--drc`, `kicad-cli` DRC SHALL run on copies of the board as it is and as it would be written, with the project files; a violation type with more entries MUST give `reuse.drc-new` (error) and no write, else the evidence cites `H-K-REUSE-DRC` at `KICAD-VERIFIED`, combined with the evidence of the reference read. Without `--drc` the evidence MUST stay `INFERRED` or lower.

#### Scenario: KiCad finds nothing new
- **GIVEN** the authored bench written for the running `kicad-cli` with its project and library
- **WHEN** `uv run pytest tests/kicad/reuse -k no_drc_finding` runs `fenolite place target.kicad_pcb --from reference.kicad_pcb --only U1,R1,R2,R3,R4 --copper --drc --confirm`
- **THEN** the exit code is 0, no DRC violation type has more entries than before, and two unconnected items fewer remain

### Requirement: Reuse codes
The codes `reuse.no-fit`, `reuse.unknown-part`, `reuse.check-failed`, `reuse.drc-new` (error), `reuse.mirror-suspected`, `reuse.project-unread` (warning), `reuse.copper-dropped` and `reuse.fill-stale` (info) SHALL be the table `fenolite.reuse.codes.ISSUE_CODES`, each explained by `fenolite explain` and listed in `docs/cli-contract.md`, "Layout reuse".

#### Scenario: Every code is explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs
- **THEN** every `reuse.*` code has an entry whose `see` is the heading `place`

### Requirement: Pads matched by net partition
`fenolite.reuse.fit_block` SHALL also pair a pad that numbers cannot pair, by its net: the reference net maps to the target net through the pads paired by number. In one part, a net with one such pad on each side pairs them; with more, a pad pairs with the reference pad whose goal lies nearest its image under the fit by number, both ways and within the tolerance. Any other pad MUST stay unpaired.

#### Scenario: Ground pads paired by their nets
- **GIVEN** an authored block whose regulator has three pads numbered `GND` beside its numbered pins
- **WHEN** `uv run pytest tests/unit/reuse/test_fit.py -k partition` fits the block
- **THEN** the three `GND` pads are paired by net and lie within 1 µm of their goals, and a net whose pads cannot be told apart leaves them unpaired

### Requirement: Zones of a copied block
With `--copper`, `place --strategy reuse` SHALL also copy, through the block transform, each zone of a block net whose stored fill joins paired pads only, with its outline and fill, its layers mapped as tracks. A zone that also joins an unpaired pad MUST be left out (`zone-beyond-block`). A copied zone MUST pass the settling of the copper and still join the images of its pads (`pad-lost`), or be left out with its reason.

#### Scenario: A zone copied with the block
- **GIVEN** a reference block with a ground zone whose fill joins `R1-2` and `R2-2`, and a zone of `OUT` whose fill also joins the test pad `TP1`, outside the block
- **WHEN** `uv run pytest tests/unit/reuse/test_copper.py -k zone` copies the copper
- **THEN** the ground zone is copied onto the images of the two pads and kept locked, and the other is dropped as `zone-beyond-block`

### Requirement: A zone read without its outline
A copied zone whose reader output holds a fill and no outline MUST get the outline of its fill: the fill's polygon when it has one, else the convex hull of its fills. The copy MUST say `outline rebuilt from its fill`.

#### Scenario: A zone read without its outline
- **GIVEN** the reference block whose ground zone the reader gives as a fill without an outline
- **WHEN** `uv run pytest tests/unit/reuse/test_copper.py -k outline` copies the copper
- **THEN** the copied zone has the image of the fill as its outline, joins the block's ground pads, and the copper check finds nothing new

### Requirement: Group moves
`fenolite place BOARD --turn REFS --about X,Y --angle DEGREES`, or `--shift REFS --by DX,DY`, SHALL move a group of parts rigidly (the strategy `group`, which either option implies): each part's new placement is the move composed with its placement, so a part on either side keeps its pads on the moved pad positions. `X,Y` is in the frame of `--move`. A moved pad farther than 1 µm from its moved position MUST be `place.group-failed`.

#### Scenario: A module turned with its satellites
- **GIVEN** an authored board with `U1` and four capacitors joined to it by tracks, two on the top and two on the bottom
- **WHEN** `uv run pytest tests/unit/cli/test_place_group.py -k turn` runs `fenolite place board.kicad_pcb --turn U1,C1,C2,C3,C4 --about 20mm,20mm --angle 90 --confirm`
- **THEN** every pad lies on its old position turned by 90° about the point, the tracks among the group's pads are turned with them, and the copper check finds nothing new

### Requirement: Copper of a moved group
A group move SHALL move with the parts the tracks, arcs and vias of each joined group of a net (without fills) that holds a pad of the group and no other pad, and each zone whose stored fill joins pads of the group only. Copper that joins a pad of the group to another pad MUST stay (`place.copper-left`). A new copper-check finding MUST be `place.group-failed`, and nothing is written.

#### Scenario: A track to a part outside the group stays
- **GIVEN** the board of "A module turned with its satellites" with a track from `C1` to `R9`, which is not in the group
- **WHEN** `uv run pytest tests/unit/cli/test_place_group.py -k shift` shifts the group by 1 mm
- **THEN** that track stays with one `place.copper-left` naming `C1`, and the tracks to `U1` move by 1 mm

### Requirement: Pose search
`--pose-search` with `--turn REFS --about X,Y --within LENGTH` SHALL try the four quarter turns about the point with every shift of a grid of step `--pitch` within `--within` on each axis, and report for each pose the demand across the group's border: per net with a pad in the group and one outside, the shortest distance between them. It MUST write nothing and refuse `--angle`.

#### Scenario: Poses of a module
- **GIVEN** the board of "A module turned with its satellites" with `R9` joined to `C1`
- **WHEN** `uv run pytest tests/unit/cli/test_place_group.py -k pose` runs `--pose-search --within 1mm --pitch 1mm`
- **THEN** `result.group.poses` holds the best poses sorted by demand, 36 poses were tried, and no write is planned

### Requirement: Group move codes
`place.group-failed` (error) and `place.fill-stale` (info, a moved zone keeps its moved fill) SHALL be codes of `placement.codes.ISSUE_CODES`, each explained by `fenolite explain` and listed in `docs/cli-contract.md`, "Group moves".

#### Scenario: Every group code is explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs
- **THEN** both codes have an entry whose `see` is the heading `place`
