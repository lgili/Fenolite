## ADDED Requirements

### Requirement: Direction of a manual move
The help of `fenolite place --move` and of `--region`, and the guide page `placement`, SHALL state the
direction of Y in the frame of `place()` (change c0486): the origin is the top-left corner of the box of the
outline, X grows to the right, a larger Y moves the part down toward the bottom edge, and a position above
that corner has a negative Y. The guide MUST say that Altium shows Y up, so a position read there needs its
sign changed.

#### Scenario: A larger Y moves the part down
- **GIVEN** an authored board with R1 at `10mm,10mm` in the frame of `place()`
- **WHEN** `fenolite place --move R1=10mm,11mm --confirm` writes the board
- **THEN** R1's file `y` is 1 mm larger than before and its `x` is unchanged

#### Scenario: The help states the direction
- **WHEN** `fenolite place --help` is read
- **THEN** the text of `--move` says that a larger Y moves the part down
