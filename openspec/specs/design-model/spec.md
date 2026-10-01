# design-model Specification

## Purpose
Specify the neutral in-memory design model every backend, check and export reads and writes: entity header, integer units, identifiers, provenance, extension bags, layers, slots and layout authority.
## Requirements
### Requirement: Common entity header
Every model entity MUST be an immutable dataclass carrying `id: str`, `native_ids: dict[str, str]`, `provenance: Provenance | None` and `ext: dict[str, ExtBag]`, where `ExtBag` holds `min_version: str | None` and an ordered tuple of opaque text fragments.

#### Scenario: Entities are immutable
- **GIVEN** a `Component` instance
- **WHEN** code assigns `component.ref = "R2"`
- **THEN** a `FrozenInstanceError` is raised

#### Scenario: Extension bag survives a copy
- **GIVEN** a `Track` with `ext = {"kicad": ExtBag(min_version="20241229", payload=(("locked", "yes"),))}`
- **WHEN** `dataclasses.replace(track, width=300000)` is called
- **THEN** the new track carries the same `ext`

### Requirement: Integer units
Lengths MUST be integers in nanometres and angles MUST be integers in microdegrees; no model field MAY be a float.

#### Scenario: Float rejected by the schema
- **GIVEN** a JSON document where `position.x` is `1.5`
- **WHEN** it is validated against `schemas/fenolite.model.v0/board.json`
- **THEN** validation fails

#### Scenario: Ninety-degree rotation is exact
- **WHEN** a rotation of 90 degrees is stored
- **THEN** the stored value is `90000000` microdegrees

### Requirement: Identifier derivation
`id` MUST be `<prefix>_<uuid>` with the prefix table from the design. For imported objects with a native id, the uuid MUST be `uuid5(FENOLITE_NS, "<backend>:<native_id>")`; for imported objects without native id, `uuid5(FENOLITE_NS, "<backend>:<doc_native_id>:<section>:<content_hash>")`; for created objects, `uuid4` from an injectable seeded generator. A file hash MUST NOT participate in any id.

#### Scenario: Same native id, same Fenolite id
- **GIVEN** two imports of the same file
- **WHEN** ids of a footprint with native uuid `a81c…` are compared
- **THEN** they are equal

#### Scenario: Editing another object keeps the id
- **GIVEN** a track without native id in a board
- **WHEN** a different track in the same board is moved and the board is re-imported
- **THEN** the first track's id is unchanged

#### Scenario: Seeded creation is reproducible
- **WHEN** two `Design` objects are created with `seed=7` and the same operations
- **THEN** all ids are identical

### Requirement: Provenance record
`Provenance` MUST contain `backend`, `file`, `file_sha256`, `locator` and `evidence`, and `locator` MUST be treated as an opaque string by everything except the originating backend.

#### Scenario: Provenance attached on import
- **WHEN** any backend imports an object
- **THEN** `provenance.backend` names the backend and `provenance.file_sha256` equals the SHA-256 of the source file

### Requirement: Model layers for v0.1
The model SHALL provide the `circuit` layer (`Component`, `Pin`, `Net`, `NetClass`, `Interface`, `Module`), the `board` layer (`Board`, `Layer`, `Stackup`, `StackLayer`, `FootprintInstance`, `Pad`, optional minimal `Padstack`, `Track`, `Arc`, `Via`, `Zone`, `Keepout`, `Text`, `Graphic`, `Hole`, `Outline`), the `rules` layer (`Rule`, `RuleSet`, selector algebra `all | net | netclass | ref | layer | item_kind | and | or | not`, kinds `clearance`, `track_width`, `via_diameter`, `via_drill`, `hole_size`, `edge_clearance`), the `manufacturing` layer (`Manifest`, `PnpRow`) and the `findings` layer (`Issue`), aggregated by `Design` with read-only indexes `by_id`, `by_ref`, `by_net`, `by_layer`.

#### Scenario: Indexes resolve
- **GIVEN** a design with component `R1` on net `GND`
- **WHEN** `design.by_ref["R1"]` and `design.by_net["GND"]` are read
- **THEN** the component and the set of pads on `GND` are returned

#### Scenario: Duplicate reference is a finding
- **GIVEN** two components with `ref = "R1"`
- **WHEN** `design.validate()` runs
- **THEN** an `Issue` with code `model.duplicate-ref` and severity `error` is produced

### Requirement: Slots for lossless round-trip
Backends MUST represent every typed node they read as an ordered list of children, each `Modeled(field)` or `Opaque(fragment, min_version)`, and MUST re-emit opaque children verbatim in their original position on write.

#### Scenario: Unknown child survives
- **GIVEN** a node with an opaque child unknown to the model
- **WHEN** the design is read, unchanged, and written by the same backend
- **THEN** the opaque child appears in the output at its original position

### Requirement: Layout authority
For a design authored in Fenolite the exported tool project MUST be the source of truth for layout; `.fenolite/` MUST be a regenerable cache; `native/` MUST hold only immutable copies of imported third-party files keyed by SHA-256.

#### Scenario: Cache is regenerable
- **GIVEN** `.fenolite/` is deleted
- **WHEN** the design is rebuilt from the same sources
- **THEN** the regenerated `.fenolite/` is byte-identical to the deleted one

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

