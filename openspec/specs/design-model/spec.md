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

Placed copies of library definitions are a third case: their ids MUST follow "Placed copies of library definitions", derived from the caller's key and never from the seeded generator, even though the copy is created in memory.

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

#### Scenario: Placed copies ignore the seed
- **GIVEN** two designs created with `seed=7` and `seed=8`
- **WHEN** `Mini_R_0603` is placed in each with key `R1`
- **THEN** the two placed copies have equal ids, while the other created objects of the two designs have different ids

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

On a write, the only changes a backend makes to an opaque child MUST be those that one of its own requirements names, and every other opaque child MUST be re-emitted unchanged. The KiCad writer's changes are listed in the `kicad-slots` requirement "Slot source for model entities": `net` nodes rewritten into the target's form, also on a same-target write, where nets are renumbered by name; nodes of rows the target no longer writes; slots removed under `allow_lossy`; the value atom of a Reference or Value property; and projections re-emitted from changed model values.

#### Scenario: Unknown child survives
- **GIVEN** a node with an opaque child unknown to the model
- **WHEN** the design is read, unchanged, and written by the same backend
- **THEN** the opaque child appears in the output at its original position

#### Scenario: Named changes only
- **GIVEN** `tests/data/kicad/tokens/skeleton.kicad_pcb` read with `read_board`
- **WHEN** it is written for target 9 with `write_board`
- **THEN** every opaque child of the text is tree-equal to its source node, except `net` nodes, whose numbers follow the code-point order of the net names

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

### Requirement: Board entities read from file backends
The board layer SHALL carry these fields, each with a default, so that documents written before them still load:
- `FootprintInstance.attributes: tuple[FootprintAttribute, ...]`, ordered, from the closed vocabulary `smd`, `through_hole`, `board_only`, `exclude_from_pos_files`, `exclude_from_bom`, `dnp`, `allow_missing_courtyard` and `allow_soldermask_bridges`;
- `Via.via_type`, one of `through`, `blind`, `buried` and `micro`, default `through`;
- `ZoneFill.island: bool = False`;
- `Zone.name: str = ""`.

Several `ZoneFill`s per layer are allowed, in the order of the source file.

Entities imported by a file backend MUST follow these rules:
- **Pad frame.** `Pad.position` is footprint-local, such that the absolute position is `instance.position + R(instance.rotation)·pad.position` with no further mirror. A bottom footprint therefore keeps its stored, mirrored coordinates. `Pad.rotation` is relative to the footprint. `Pad.layers` are the actual board layers, without wildcards.
- **Outlines.** `Zone.outline == ()` or `Keepout.outline == ()` means that the outline is kept by the backend as an opaque slot. `Board.outline` is `None` for an imported board, whose edge graphics are authoritative.
- **Layers.** `Layer.ordinal` is the stack position. The backend's own layer number, type and user name go in `Layer.ext[<backend>]`.

`tools/gen_schemas.py` MUST regenerate `schemas/fenolite.model.v0/board.json` with the new fields.

#### Scenario: Old documents still load
- **GIVEN** a `board.json` written before this change, without the new fields
- **WHEN** `canonical.loads` reads it into a `Board`
- **THEN** every footprint has `attributes == ()`, every via `via_type == "through"`, every fill `island == False` and every zone `name == ""`

#### Scenario: Unknown attribute rejected by the schema
- **GIVEN** a `board.json` document where `footprints[0].attributes[0]` is `"glued"`
- **WHEN** it is validated against `schemas/fenolite.model.v0/board.json`
- **THEN** validation fails with the JSON pointer of that value

#### Scenario: Absolute pad position of a bottom footprint
- **GIVEN** the design read from `tests/data/kicad/board/two_layer.kicad_pcb`
- **WHEN** `Transform.placement(D1.position, D1.rotation).apply(pad.position)` is computed for pads `"1"` and `"2"` of `D1`, and the offset of pad `"2"` from pad `"1"` is taken
- **THEN** it equals the offset between the `D1` pin 2 and pin 1 records of `kicad-cli pcb export ipcd356`, converted from the export's Y-up frame, within ±2 export units per axis (the export origin is not known)

#### Scenario: Schemas regenerated
- **WHEN** `uv run python tools/gen_schemas.py --check` runs after this change
- **THEN** it exits 0, and `board.json` lists `attributes`, `via_type`, `island` and `name`

### Requirement: Components synthesised from a board
A backend that reads a board without a schematic SHALL synthesise its circuit:
- **Components.** One `Component` per footprint instance, referenced by `FootprintInstance.component_id`:
  - `ref` and `value` come from the footprint's reference and value;
  - `properties` holds every footprint property, `lib_footprint_ref` is the footprint's library id, and `path` is the footprint's schematic path when it has one;
  - `dnp` is true when `attributes` contains `dnp`.
- **Pins.** `Component.pins` holds one `Pin` per distinct non-empty pad number, in pad order:
  - `name` is the pad's pin function;
  - `etype` comes from a closed table of the backend's pin types, and a value outside the table gives `unspecified` with the original text kept in `Pin.ext[<backend>]`.
- **Nets.** One `Net` per board net, with members `PinRef(component id, pad number)` for every numbered pad on it, without duplicates.

`Design.validate()` MUST report `model.duplicate-ref` with severity `warning`, instead of `error`, in two cases:
- every component that shares the reference is placed only by footprints whose `attributes` contain `board_only`;
- the reference ends in `**`.

Every other duplicate reference stays an error.

#### Scenario: Components of the authored board
- **GIVEN** the design read from `tests/data/kicad/board/two_layer.kicad_pcb`
- **WHEN** `design.by_ref["D1"]` is read
- **THEN** it has `lib_footprint_ref == "Fenolite_Test:LED_THT_3mm"`, and pins `"1"` and `"2"` named `K` and `A` with `etype == "passive"`

#### Scenario: Net members from pads
- **WHEN** the net `LED_A` of the same design is read
- **THEN** its members are `PinRef(<R1 id>, "2")` and `PinRef(<D1 id>, "2")`, and `design.by_net["LED_A"]` holds the two pads

#### Scenario: Unmapped pin type keeps its text
- **GIVEN** a board pad with `(pintype "passive+no_connect")`
- **WHEN** the board is read
- **THEN** the pin has `etype == "unspecified"`, and its `kicad` bag holds the pair `("pintype", "passive+no_connect")`

#### Scenario: Board-only duplicates are warnings
- **GIVEN** two components with `ref = "LOGO"`, each placed by a footprint whose `attributes` contain `board_only`, and two plain components with `ref = "R1"`
- **WHEN** `design.validate()` runs
- **THEN** `LOGO` gives `model.duplicate-ref` with severity `warning` and `R1` gives it with severity `error`

#### Scenario: Unannotated references are warnings
- **GIVEN** two components with `ref = "REF**"`
- **WHEN** `design.validate()` runs
- **THEN** `model.duplicate-ref` is reported with severity `warning`

### Requirement: Placed copies of library definitions
A backend that places a library definition into a design SHALL derive every id of the placed copy from a caller key, never from the seeded generator and never from the definition's own ids.
- The caller MUST pass a `key` that names the placement stably and is unique within the design. c0011 passes the component path.
- Every native id the backend creates for the copy MUST depend only on the key and on the locator of the node inside the definition. For KiCad it is `uuid5(FENOLITE_NS, f"kicad-place:{key}:{locator}")`.
- The Fenolite ids of the copy MUST follow "Identifier derivation" for imported objects with a native id, applied to those native ids, so that a design read back from the written file has the same ids.
- Placing the same definition again with the same key MUST give the same ids and native ids. Two keys MUST share no id and no native id. Adding or removing another placement MUST NOT change any id of a placed copy.
- The copy MUST record its definition in `FootprintInstance.lib_ref` (the definition's `lib_id`), its `component_id` MUST be the caller's component, and its pads MUST have `net_id = None` until the caller assigns nets.
- The definition MUST stay unchanged, so it can be placed again.

This is the third case of "Identifier derivation", next to imported and created objects, which this change modifies to name it.

#### Scenario: Same key, same ids
- **GIVEN** `Mini_R_0603` read from `tests/data/libs/Mini.pretty`
- **WHEN** it is placed twice with key `R1`, once in a design created with `seed=1` and once with `seed=2`
- **THEN** the two copies have equal footprint ids, pad ids and native ids, although every seeded id of the two designs differs

#### Scenario: Distinct keys share nothing
- **GIVEN** the same definition placed with keys `R1` and `R2`
- **WHEN** the ids and native ids of both copies are collected
- **THEN** the two sets are disjoint

#### Scenario: Ids survive a write and a read
- **GIVEN** a created design holding `Mini_R_0603` placed with key `R1`
- **WHEN** it is written for target 10 with `write_board` and the text is read with `read_board`
- **THEN** the re-read footprint and its pads have the ids of the placed copy

#### Scenario: Inserting a part shifts nothing
- **GIVEN** a design with placements keyed `R1` and `R3`
- **WHEN** a placement keyed `R2` is added
- **THEN** every id of the `R1` and `R3` copies is unchanged

