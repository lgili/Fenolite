## ADDED Requirements

### Requirement: Copper locks on boards
Beside the fields of "Modelled board content", the board reader SHALL map the `locked` child of a `segment`, an `arc` and a `via` to `locked` (`design-model`, "Copper locks in the board model"): `(locked yes)` gives `True`; no child gives `False`. The writer SHALL write `(locked yes)` for a locked item, after `width` in a `segment` and an `arc` and after `layers` in a `via`, for targets 9 and 10, and nothing for an unlocked item (`H-K-LOCK-FORM`).
- `(locked no)` MUST give `False`. The writer would not write it, so "Modelled children are reproducible" keeps it as written, with its `kicad.board.kept-opaque` info. Any other value reads as locked, as for a footprint.
- "Same-version rebuild" MUST hold for boards with locked items: a board read and written for its own major keeps its bytes.
- `docs/formats/kicad/board.md` MUST move `locked` of `segment`, `arc` and `via` from the opaque column to the modelled one, with the measured order and `H-K-LOCK-FORM`.

#### Scenario: Locks read
- **GIVEN** a board holding a segment, an arc and a via with `(locked yes)` after `width` or `layers`, and one unlocked segment
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pcb_locks.py -k read` reads it
- **THEN** the three items have `locked == True` and the other segment `locked == False`

#### Scenario: Locks written where KiCad writes them
- **GIVEN** a design with a locked track, a locked arc and a locked via
- **WHEN** it is written with `write_board` for target 9 and for target 10
- **THEN** in both texts the children are `start end width locked layer net uuid` for the segment, `start mid end width locked layer net uuid` for the arc and `at size drill layers locked net uuid` for the via, and an unlocked item has no `locked` child

#### Scenario: A board with locks keeps its bytes
- **GIVEN** the corpus row `kicad-demo-10-0-6-pcb-16`, which holds 7 locked segments and 5 locked vias
- **WHEN** `uv run pytest tests/corpus/test_board_rt1.py -k pcb-16` reads and rebuilds it
- **THEN** the design holds 7 locked tracks and 5 locked vias, and RT1 passes as before this change
