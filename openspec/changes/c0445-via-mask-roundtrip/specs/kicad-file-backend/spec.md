## ADDED Requirements

### Requirement: Board mask margin in a written board
The KiCad board writer SHALL write `Board.mask_margin` as `(setup (pad_to_mask_clearance M))` of a board that it writes from the model. With the field `None` or 0 it SHALL write `0`, as before (S-2042; `H-K-VIAPROT-MASK`). A board read from a file keeps its own setup child.
- KiCad opens an untented via by this value: the opening is the via's diameter plus twice the margin, a negative margin included. A `solder_mask_expansion` rule in the rules file does not change it (KiCad 10.0.6, S-2042).

#### Scenario: A negative margin
- **GIVEN** a model board with `mask_margin=-101_600`
- **WHEN** `uv run pytest tests/unit/convert/test_via_mask_c0445.py -k kicad_board` writes it
- **THEN** its setup holds `(pad_to_mask_clearance -0.1016)`

#### Scenario: The opening KiCad plots
- **GIVEN** the via bench with one untented via, written with `mask_margin` `None`, 50 000 and -101 600 nm, and once with a rules file whose `solder_mask_expansion` rule selects vias
- **WHEN** `uv run pytest tests/kicad/vias/test_via_mask_margin_oracle.py` plots `F.Mask` with `kicad-cli pcb export gerbers` 10
- **THEN** the via's flash is a circle of its diameter, its diameter plus 0.1 mm, and its diameter minus 0.2032 mm, and the rule leaves it at its diameter
