# board-annotations-view Specification

## Purpose
The board view of `fenolite view` draws what the copper alone does not show: keep-outs and rule areas, dimensions, and the placement checks (overlapping courtyards, parts in keep-outs) as marks on the parts they name (change c0183).

## Requirements

### Requirement: Keep-outs in the board scene
The board scene SHALL draw each keep-out of the model on its layers, hatched, with what it forbids in its label, and SHALL draw the regions of Altium's Keep-Out Layer hatched.

#### Scenario: An authored keep-out
- **GIVEN** the test board `two_layer.kicad_pcb`, whose rule area forbids tracks and vias on `F.Cu`
- **WHEN** `uv run pytest tests/unit/view/test_board_annotations.py -k keepout` builds its scene
- **THEN** the scene holds one hatched outline, on `F.Cu`, whose label names tracks and vias

### Requirement: Courtyard overlaps
The board scene SHALL mark each pair of overlapping courtyards, judged by `placement.legality`, on a `Checks` view layer with both parts named; overlaps of extents made from pad copper SHALL be counted in the notes instead.

#### Scenario: Two overlapping parts
- **GIVEN** a test board with one part moved onto another, with exact courtyards
- **WHEN** `uv run pytest tests/unit/view/test_board_annotations.py -k overlap` builds its scene
- **THEN** the `Checks` layer holds one mark naming both parts
