## ADDED Requirements

### Requirement: Items on undeclared layers are refused
`write_board` SHALL raise `LossyWriteError` with one `kicad.board.layer-undeclared` error per layer name when a modelled item of the board (a footprint's item, a track, an arc, a via, a zone, a graphic, a text, a dimension) names a layer that no row of the board's layer table declares; the message MUST name the layer and the count of items, and `droppable` MUST be false. A board without such an item MUST be written as before, byte for byte.

#### Scenario: Line on an unknown layer
- **GIVEN** the two-layer design with one graphic line on the layer `Mech.1`, which its layer table does not hold
- **WHEN** `write_board(design, target=10)` runs
- **THEN** it raises `LossyWriteError` with one `kicad.board.layer-undeclared` error naming `Mech.1` and 1 item

#### Scenario: Committed boards unchanged
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_layer_undeclared.py -k census` writes every committed KiCad board, built example and test script board
- **THEN** none raises the error, and every written text equals the text before the change
