## ADDED Requirements

### Requirement: Copper locks in the board model
`fenolite.model.board` SHALL add `locked: bool = False` as the last field of `Track`, `Arc` and `Via`. A locked item is one that tools must not move or remove: `routing.select.rip` keeps it (`routing`, "Net selection"), and the KiCad backend reads and writes it (`kicad-file-backend`, "Copper locks on boards"). Documents written before this field MUST still load, with `locked == False`, and a design without a locked item MUST serialise to the bytes it had before (the key is written only when true, as every default of the model). The other direction does not hold and MUST be said in `docs/design-model.md` and in the changelog: releases 0.2.x and 0.3.x cannot read a model document that carries the key `locked` on a track, an arc or a via, because their reader refuses an unknown key. `tools/gen_schemas.py` MUST regenerate `schemas/fenolite.model.v0/board.json` with the three fields.

#### Scenario: Default is unlocked
- **WHEN** `Track(id=…, start=…, end=…, width=250_000, layer="F.Cu")`, an `Arc` and a `Via` are constructed without `locked`
- **THEN** each has `locked == False`, and an item built with `locked=True` compares unequal to the same item without it

#### Scenario: Old documents still load
- **GIVEN** a `board.json` written before this change, without the field
- **WHEN** `uv run pytest tests/unit/model -k copper_lock` loads it with `canonical.loads`
- **THEN** every track, arc and via has `locked == False`

#### Scenario: A design without locks keeps its bytes
- **GIVEN** `tests/data/model/v0.2.0/blink_2layer.board.json` (the fixture of c0126)
- **WHEN** `uv run pytest tests/unit/model -k copper_lock` loads it and serialises it with `canonical.dumps`
- **THEN** the bytes are those of the file, and `grep -n "cannot read a model document that carries the key" docs/design-model.md` prints the sentence

#### Scenario: Schemas regenerated
- **WHEN** `uv run python tools/gen_schemas.py --check` runs after this change
- **THEN** it exits 0, and `board.json` lists `locked` for tracks, arcs and vias as a boolean
