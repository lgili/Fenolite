## ADDED Requirements

### Requirement: Board mask margin in the model
`fenolite.model.board.Board` SHALL hold `mask_margin: Nm | None = None`, placed last, so that documents written before it still load: the board's solder-mask margin, the growth of the mask opening of an untented via, and of a pad that holds no margin of its own, beyond its copper. It may be negative. `None` MUST mean the backend's own default.
- The model MUST NOT compute an opening; backends do.
- `tools/gen_schemas.py` MUST regenerate `schemas/fenolite.model.v1/board.json` with the field, an integer or `null`. The canonical JSON of a board whose `mask_margin` is `None` MUST be the text written before this change, because default values are omitted.
- The field is set by a conversion (change c0445). A KiCad board read from a file leaves it `None` and keeps its setup in its slots.

#### Scenario: Default and old documents
- **GIVEN** a `board.json` written before this change
- **WHEN** `canonical.loads` reads it into a `Board` and `to_data` writes it again
- **THEN** the board has `mask_margin is None` and the written text equals the read one

#### Scenario: Schema regenerated
- **WHEN** `uv run python tools/gen_schemas.py --check` runs after this change
- **THEN** it exits 0 and `board.json` lists `mask_margin` on the board
