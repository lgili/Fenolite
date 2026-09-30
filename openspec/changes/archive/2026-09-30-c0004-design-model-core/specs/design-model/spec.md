## ADDED Requirements

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
