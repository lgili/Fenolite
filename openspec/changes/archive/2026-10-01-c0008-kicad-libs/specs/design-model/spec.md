## ADDED Requirements

### Requirement: Library definitions
The model SHALL provide the module `fenolite.model.library`. It holds library definitions that are independent of any `Design`:
- `FootprintDef`: an entity with `name`, `library`, `description`, `keywords`, `kind`, `flags`, `properties`, `pads`, `graphics` and `models`
- `SymbolDef`: an entity with `name`, `library`, `extends`, `power`, `properties`, `in_bom`, `on_board`, `exclude_from_sim`, pin-name settings, `units` and `pins`
- `SymbolPin`, `SymbolUnit` and `PinAlternate`: value objects without the entity header
- `Library`: a container with `name`, `footprints` and `symbols`

Library definitions MUST obey these rules:
- They MUST be immutable.
- They MUST use integer nanometres and microdegrees.
- `FootprintDef.pads` and `FootprintDef.graphics` MUST reuse the board `Pad` and `Graphic` entities, with `net_id = None` and positions relative to the definition's origin. A pad with per-layer shapes MUST carry them in `Pad.padstack`.
- Every field other than `name` MUST have a default. The tuples `keywords`, `flags`, `pads`, `graphics`, `models`, `units`, `pins` and `alternates` MUST be marked ordered, so the canonical form keeps their order. `properties` is a mapping and its canonical form is sorted by key.
- Library definitions MUST NOT be part of `Design` or of the `.fenolite/` layer files.

#### Scenario: Definitions are immutable
- **GIVEN** a `FootprintDef`
- **WHEN** code assigns `fp.name = "X"`
- **THEN** a `FrozenInstanceError` is raised

#### Scenario: Pads are board pads without nets
- **GIVEN** every footprint of `tests/data/libs/Mini.pretty`, read with `read_footprint`
- **WHEN** their `pads` are inspected
- **THEN** every element is a `fenolite.model.board.Pad` whose `net_id` is `None`

#### Scenario: Pad order survives the canonical form
- **GIVEN** a `FootprintDef` whose pads are numbered `"2"`, `"1"`, `"3"` in that order
- **WHEN** it is dumped and loaded with `canonical.dumps` and `canonical.loads`
- **THEN** the pads keep the order `"2"`, `"1"`, `"3"`

#### Scenario: Minimal construction
- **WHEN** `FootprintDef(id=..., name="X")` and `SymbolDef(id=..., name="Y")` are constructed
- **THEN** both succeed, with empty `pads`, `graphics`, `properties`, `units` and `pins`

#### Scenario: Canonical layer files unchanged
- **GIVEN** a design whose components reference library items
- **WHEN** `canonical.dump_dir` writes it
- **THEN** the same six layer files are written and none of them contains a `FootprintDef`

### Requirement: Identifiers of library definitions
The closed prefix table SHALL include `fpd` (footprint definition) and `sym` (symbol definition).
- A definition imported by a backend MUST have the native id `"<library>:<name>"` (or `"<name>"` when the library is empty), stored in `native_ids[<backend>]`, and the id `derived_id(prefix, backend, native_id)`.
- Pads, padstacks and graphics inside a definition MUST be scoped to it. With a native uuid `U`, their id MUST be `derived_id(prefix, backend, "<native_id>:<U>")`. A uuid that occurs again inside the same definition (the official library copies graphics with their uuids) MUST keep that form for its first occurrence, and its k-th repetition MUST use `"<native_id>:<U>:<k>"`. Without a uuid, they MUST use a content id whose document is the definition's native id, whose section is `pad` or `gfx`, and whose digest includes an occurrence counter among identical contents.
- Ids MUST be unique within a `Library`. A consumer that places a definition more than once MUST derive new ids for the placed copies.

#### Scenario: Same item, same id
- **WHEN** the same footprint file is read twice under nickname `Mini`
- **THEN** both definitions have the same id with prefix `fpd`, and their pads have the same ids

#### Scenario: Same file under two nicknames
- **WHEN** one footprint file is read once with `library="A"` and once with `library="B"`
- **THEN** the two definition ids differ, and no pad id of the first equals a pad id of the second

#### Scenario: Identical pads get distinct ids
- **GIVEN** a footprint with two pads without uuid and with identical number, geometry and layers
- **WHEN** it is read
- **THEN** the two pads have different ids, and reading the file again reproduces both ids

#### Scenario: Repeated uuid inside one definition
- **GIVEN** a footprint with three graphics that carry the same uuid `U`
- **WHEN** it is read
- **THEN** the three graphics have different ids, the first is `derived_id("gfx", "kicad", "<native_id>:<U>")`, the third uses `"<native_id>:<U>:2"`, and all three keep `U` as native id

#### Scenario: Unknown prefix still rejected
- **WHEN** `new_id("fpx", rng)` is called
- **THEN** a `ValueError` is raised

### Requirement: Library schema
`tools/gen_schemas.py` SHALL generate `schemas/fenolite.model.v0/library.json` with schema id `fenolite.library.v0` from `fenolite.model.library.Library`. The schema drift test MUST cover that file, and `canonical.dumps`/`canonical.loads` MUST round-trip a `Library` idempotently.

#### Scenario: Library schema drift detected
- **GIVEN** a contributor adds a field to `SymbolPin` without regenerating schemas
- **WHEN** `uv run pytest tests/unit/test_schema_drift.py` runs
- **THEN** it fails naming `library.json`

#### Scenario: Float rejected in a library document
- **GIVEN** a `library.json` document where `footprints[0].pads[0].size.w` is `1.5`
- **WHEN** it is validated against the library schema
- **THEN** validation fails with the JSON pointer of that value

#### Scenario: Library canonical idempotence
- **GIVEN** the `Library` read from the mini library
- **WHEN** `dumps(loads(dumps(lib), Library))` is computed
- **THEN** it equals `dumps(lib)` byte for byte
