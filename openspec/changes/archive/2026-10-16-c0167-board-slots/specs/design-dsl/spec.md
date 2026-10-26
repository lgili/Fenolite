## ADDED Requirements

### Requirement: Slots in the DSL
`Design.slot(x, y, *, length, width, rot=0, name=None) -> str` SHALL add one slot (`design-model`, "Board slots") after `board()` and return its name, `S<n>` in call order by default; `shape.stadium(x, y, length, width, rot=0)` SHALL return the same ring as a path. A bad size or a repeated name MUST raise `DslError` at the call. `to_model` MUST give the id `key_id("slot", name)`, from the new key row `slot` (prefix `slt`).

#### Scenario: A slot in the model
- **GIVEN** `board(mm(40), mm(30))` and `d.slot(mm(15), mm(10), length=mm(12), width=mm(2), rot=30)`
- **WHEN** `uv run pytest tests/unit/dsl/test_slots.py` runs `to_model`
- **THEN** `Outline.slots` holds one slot `S1` at (115 mm, 110 mm) with rotation 30 000 000 µdeg and the id `key_id("slot", "S1")`, and `Outline.cutouts` is empty

#### Scenario: Refused slots
- **WHEN** `d.slot(mm(5), mm(5), length=mm(2), width=mm(2))`, `d.slot(mm(5), mm(5), length=mm(4), width=nm(3))` and a second `d.slot(…, name="S1")` are called after `board()`
- **THEN** each raises `DslError`
