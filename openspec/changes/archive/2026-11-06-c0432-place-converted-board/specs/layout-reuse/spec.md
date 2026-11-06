## MODIFIED Requirements

### Requirement: Copper of a moved group
A group move SHALL move with the parts the tracks, arcs and vias of each joined group of a net (without fills) that holds a pad of the group and no other pad, and each zone whose stored fill joins pads of the group only. It SHALL drag the copper on the group's pads (change c0432): a via whose copper touches a pad of the group and no pad of a part outside the group MUST move with the group, and each end of a track that touches a pad of the group or such a via MUST move with them, the other end staying. An arc that joins a pad of the group to another pad MUST stay (`place.copper-left`). A new copper-check finding MUST be `place.group-failed`, and nothing is written.

#### Scenario: A track to a part outside the group stretches
- **GIVEN** the board of "A module turned with its satellites" with a track from `C1` to `R9`, which is not in the group
- **WHEN** `uv run pytest tests/unit/cli/test_place_group.py -k shift` shifts the group by 1 mm
- **THEN** that track's end on `C1` moves by 1 mm and its end on `R9` stays, there is no `place.copper-left`, and the tracks to `U1` move by 1 mm

#### Scenario: A via in a pad and a track to another part
- **GIVEN** the authored Altium `routed` sample converted to KiCad, whose part R1 has a via in one pad and a track from each pad to another part
- **WHEN** `fenolite place --shift R1 --by 1mm,0mm` runs
- **THEN** the via moves with R1, the tracks' ends on R1 move with it and their other ends stay, there is no `place.copper-left` and no `place.group-failed`, and the command exits 0
