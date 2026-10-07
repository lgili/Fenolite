## ADDED Requirements

### Requirement: Via protection in the board model
`fenolite.model.board` SHALL describe how a via is protected with the value object `ViaProtection`, which has no entity header, and SHALL add these fields, each with a default, so that documents written before them still load:
- `Via.protection: ViaProtection = ViaProtection()`, the via's own values;
- `Board.via_protection: ViaProtection | None = None`, the board's default for every via.

`ViaProtection` MUST be a frozen dataclass of eight fields, in this order, each of type `bool | None` with the default `None`: `tenting_front`, `tenting_back`, `covering_front`, `covering_back`, `plugging_front`, `plugging_back`, `capping`, `filling`. `True` means that the feature is applied on that side, or to the via for `capping` and `filling`; `False` that it is not.
- On a via, `None` MUST mean that the field follows the board's default.
- In `Board.via_protection`, `None`, whole or for one field, MUST mean the backend's own default; `kicad-file-backend` "Via protection defaults on boards" states KiCad's (tented on both sides, nothing else), and `altium-build` "Via protection in an Altium build" the Altium backend's (clear tenting flags).
- The model MUST NOT compute effective values; backends do.
- `tools/gen_schemas.py` MUST regenerate `schemas/fenolite.model.v0/board.json` with both fields, each value a boolean or `null`. The canonical JSON of a via whose `protection` equals `ViaProtection()` and of a board whose `via_protection` is `None` MUST be the text written before this change, because default values are omitted.
- `docs/design-model.md` MUST describe the two fields and say that Fenolite 0.2.x and 0.3.0 cannot read a `board.json` that carries `protection` or `via_protection`: their reader of the canonical form is strict.

#### Scenario: Defaults
- **WHEN** `Via(id=..., position=..., diameter=600_000, drill=300_000)` and `Board(id=...)` are constructed
- **THEN** the via has `protection == ViaProtection()`, every field of which is `None`, and the board has `via_protection is None`

#### Scenario: Old documents still load
- **GIVEN** a `board.json` written before this change, holding vias and no `protection` or `via_protection` key
- **WHEN** `canonical.loads` reads it into a `Board` and `to_data` writes it again
- **THEN** every via has `protection == ViaProtection()`, the board has `via_protection is None`, and the written text equals the read one

#### Scenario: Not a boolean
- **GIVEN** a `board.json` document where `vias[0].protection.filling` is `"yes"`
- **WHEN** it is validated against `schemas/fenolite.model.v0/board.json`
- **THEN** validation fails with the JSON pointer of that value

#### Scenario: Schema regenerated
- **WHEN** `uv run python tools/gen_schemas.py --check` runs after this change
- **THEN** it exits 0, and `board.json` lists `protection` on vias, `via_protection` on the board, and the eight fields of `ViaProtection`
