## ADDED Requirements

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
