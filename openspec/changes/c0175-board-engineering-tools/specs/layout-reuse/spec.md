## ADDED Requirements

### Requirement: Block copy by pad fit
`fenolite.reuse.fit_block(reference, target, parts, *, anchor=None, mapping=None, tolerance=50_000) -> BlockFit` SHALL place each named target part so that its pads land on the pads of its reference part, and SHALL decide each part's side from the fit.
- The block transform MUST be fitted on the anchor's pads (the first part when `anchor` is absent), over the four quarter turns and both sides, by least squares on pads matched by number; the fit with the smallest residual wins.
- Each part MUST then be placed by fitting its own pads onto its reference part's pads (`mapping` gives `TARGET=REFERENCE` when the references differ), with the same search. A pad that has no match by number MUST be matched by net partition: the pads of corresponding nets.
- `BlockFit` MUST hold, per part, the placement, the matched pads, the largest residual, and `side_changed` when its side differs from its reference part's.
- A part whose best fit has a residual above `tolerance` MUST be left unplaced with `reuse.no-fit` (error). A part whose fit needs the side opposite to the one the block transform gives MUST be reported with `reuse.mirror-suspected` (warning).

#### Scenario: A mirrored reference is found
- **GIVEN** an authored reference board whose block `U1`, `R1`–`R4` is drawn with the Y axis up, and a target board with the same parts
- **WHEN** `uv run pytest tests/unit/reuse/test_fit.py -k mirror` fits the block
- **THEN** every pad of every part matches within 1 µm, and no part is placed by the reference's raw coordinates

#### Scenario: A part without a fit
- **GIVEN** the same block where the target's `R3` has a footprint of another pitch
- **WHEN** the block is fitted
- **THEN** `R3` stays unplaced and the result holds one `reuse.no-fit` naming it

### Requirement: Copper of a copied block
With `--copper`, `fenolite.reuse.copy_copper(fit, reference, target) -> CopperCopy` SHALL copy the reference copper of the block's nets through the block transform, joined to the target's nets.
- Each reference net MUST map to the target net of its matched pads. A reference item on a net that maps to two target nets MUST be left out with a reason.
- Branches that end on no matched pad MUST be removed, first tracks with a free end and then vias joined on fewer than two layers, until nothing changes.
- An island MUST be kept only when it joins two or more matched pads that are all on one target net.
- A zone whose reader output holds a fill and no outline MUST be given the outline of its fill.
- The copied copper MUST pass the copper check against the target; an item that adds a finding MUST be left out and reported with its finding. The written copper MUST be locked.

#### Scenario: Copper that ends nowhere is pruned
- **GIVEN** the reference block with a track of `R2`'s net that ends on a test pad not in the block
- **WHEN** the copper is copied
- **THEN** that track is not written, and the result names it with the reason `free-end`

### Requirement: Reuse command
`fenolite reuse TARGET --from REFERENCE --parts REFS [--anchor REF] [--map TARGET=REFERENCE ...] [--copper] [--tolerance LENGTH]` SHALL be a writing command under the mutation protocol, with schema `fenolite.reuse.v0`. TARGET is a KiCad board. REFERENCE is any board that a backend reads.
- `result` MUST hold the transform, the per-part fit, the copied and the dropped items with reasons.
- The written board MUST be judged by `kicad-cli` DRC when it is present, and every new finding MUST be an issue.

#### Scenario: Dry run of a block
- **WHEN** `fenolite reuse target.kicad_pcb --from reference.kicad_pcb --parts U1,R1,R2 --copper --dry-run --json` runs on authored boards
- **THEN** the exit code is 0, `result.plan` names the target board, and nothing is written

### Requirement: Group moves
`fenolite place BOARD --turn REFS --about X,Y --angle DEGREES` and `--shift REFS --by DX,DY` SHALL move a group of parts rigidly with the copper, zones and texts that belong to them: copper whose every connection is among the group's pads, and locked or scripted copper that the group's parts own. Each part's new angle MUST come from its pads, so that a part on either side keeps its pads on the moved pad positions.
- `--pose-search` with `--turn` MUST try the four turns and a grid of shifts within `--within LENGTH`, and report for each pose the routing demand across the group's border (the length of the open and broken connections), without writing.

#### Scenario: A module turned with its satellites
- **GIVEN** an authored board with `U1` and four capacitors joined to it by tracks, two on the top and two on the bottom
- **WHEN** `fenolite place <board> --turn U1,C1,C2,C3,C4 --about 20mm,20mm --angle 90 --confirm` runs
- **THEN** every pad lies on its old position turned by 90° about the point, the tracks among the group's pads are turned with them, and DRC reports nothing new
