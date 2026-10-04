## MODIFIED Requirements

### Requirement: Board read issue codes
`read_board` SHALL report problems only with the codes of this closed table, plus the `kicad.version.*` codes of `kicad-version-gating`. `pcb.ISSUE_CODES` MUST map each code to its severity. On boards, the shared footprint mapping MUST report `kicad.board.kept-opaque` instead of `kicad.lib.kept-opaque`. The `ReadResult.issues` of a board also hold the `model.*` codes of `Design.validate()` (`backend-protocol` "Read results"); they are model findings, not reader codes, and are not in this table.

#### Scenario: Oval drill on a board pad
- **GIVEN** a board pad with `(drill oval 1.2 2.0)`
- **WHEN** the board is read with an `issues` list
- **THEN** `pad.drill == 1_200_000`, its padstack has `hole_shape == "slot"` and `hole_length == 2_000_000`, and the reader may report a kept-opaque info when its emitter check finds a byte-level projection difference
