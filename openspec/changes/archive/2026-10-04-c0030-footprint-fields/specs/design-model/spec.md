## ADDED Requirements

### Requirement: Footprint fields
The board layer SHALL model the text fields of a placed footprint as `fenolite.model.board.FootprintField` entities in `FootprintInstance.fields: tuple[FootprintField, ...]`, ordered, with the default `()`, so documents written before them still load.
- A field MUST hold placement and appearance only: `name: str`, `position: Point`, `layer: str`, `size: Size`, `rotation: Udeg = 0`, `thickness: Nm | None = None`, `visible: bool = True`, `h_justify: FieldJustifyH = "center"` (one of `left`, `center`, `right`), `v_justify: FieldJustifyV = "center"` (one of `top`, `center`, `bottom`) and `mirrored: bool = False`.
- Its text MUST stay in the component of the footprint: `Component.ref` for `Reference`, `Component.value` for `Value`, and `Component.properties[name]` for every field. No field holds a copy of it.
- Names MUST be unique within one footprint.
- **Frame.** `position` and `rotation` MUST follow the pad frame of "Board entities read from file backends": the field's anchor on the board is `instance.position + R(instance.rotation)·position`, with no further mirror on the bottom side, and `rotation` is relative to the footprint, so the field's angle on the board is `(rotation + instance.rotation) mod 360°`.
- `size.w` is the glyph width and `size.h` the glyph height. `thickness = None` means the backend's default stroke. `h_justify` and `v_justify` are given in the reading frame of the text, and `mirrored` mirrors the text horizontally.
- Field ids MUST derive from the footprint's native id and the field name, so a placed copy and the board read back from it give equal ids ("Placed copies of library definitions").
- The closed prefix table SHALL include `fld`.
- `tools/gen_schemas.py` MUST regenerate `schemas/fenolite.model.v0/board.json` with `FootprintField` and `fields`.

#### Scenario: Old documents still load
- **GIVEN** a `board.json` written before this change, without `fields`
- **WHEN** `canonical.loads` reads it into a `Board`
- **THEN** every footprint has `fields == ()`

#### Scenario: Unknown justification rejected by the schema
- **GIVEN** a `board.json` document where `footprints[0].fields[0].h_justify` is `"middle"`
- **WHEN** it is validated against `schemas/fenolite.model.v0/board.json`
- **THEN** validation fails with the JSON pointer of that value

#### Scenario: Float rejected in a field
- **GIVEN** a `board.json` document where `footprints[0].fields[0].position.x` is `1.5`
- **WHEN** it is validated against the board schema
- **THEN** validation fails with the JSON pointer of that value

#### Scenario: Field order survives the canonical form
- **GIVEN** a footprint whose fields are `Value` then `Reference`
- **WHEN** its board is dumped and loaded with `canonical.dumps` and `canonical.loads`
- **THEN** the fields keep the order `Value`, `Reference`

#### Scenario: Field prefix
- **WHEN** `new_id("fld", rng)` and `derived_id("fld", "kicad", "x:field:Reference")` are called
- **THEN** both return ids that start with `fld_`, and `new_id("fldx", rng)` raises `ValueError`

#### Scenario: Schemas regenerated
- **WHEN** `uv run python tools/gen_schemas.py --check` runs after this change
- **THEN** it exits 0, and `board.json` lists `fields`, `h_justify`, `v_justify` and `mirrored`
