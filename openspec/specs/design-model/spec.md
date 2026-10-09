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

Objects created from a design script are a fourth case. `fenolite.dsl.to_model` and the build of the `design-dsl` capability MUST give each object they create the id `derived_id(prefix, "dsl", "<kind>:<key>")`, with the kind and key taken from the closed table `fenolite.dsl.KEYS`, and MUST NOT use the seeded generator:

| object | prefix | kind and key |
|---|---|---|
| design header | `dsn` | `design` |
| board | `brd` | `board` |
| outline | `out` | `outline` |
| rule set | `rst` | `rules` |
| manifest | `mfn` | `manifest` |
| module | `mod` | `module:<module path>` |
| component | `cmp` | `component:<component path>` |
| pin | `pin` | `pin:<component path>:<pin number>` |
| net | `net` | `net:<net name>` |
| net class | `cls` | `netclass:<class name>` |
| interface | `itf` | `interface:<kind>:<interface name>` |
| layer | `lay` | `layer:<KiCad layer name>` |
| zone | `zon` | `zone:<zone name>` |
| rule | `rul` | `rule:<rule kind>` for a board minimum, `rule:<rule kind>:<class name>` for a class minimum, `rule:named:<rule name>` for a rule of `rule()` |
| rule area | `kpo` | `area:<area name>` |
| board text | `txt` | `text:<drawing key>` |
| board graphic | `gfx` | `graphic:<drawing key>` |
| dimension | `dim` | `dimension:<drawing key>` |

- Footprints and pads placed by a build MUST follow the third case, with the component path as the key.
- Tracks and vias created from copper intents, by a build or by any other caller, MUST follow the fifth case.
- Every key names its object by a name or a path, never by a position in a list, so inserting, removing or reordering one object MUST NOT change the id of any other object, nor any KiCad uuid derived from those ids.
- The values of `--seed` and `PYTHONHASHSEED` MUST NOT change any id of the fourth case.
- The KiCad uuid of a rule area, text, graphic or dimension of the fourth case is derived from its id by the build (`kicad-file-backend`, "Board items of a script are written"); it is not an input of the id.

Copper created from copper intents is a fifth case. Each track and via that `fenolite.backends.kicad.copper.resolve_copper` creates MUST take as its native id the KiCad uuid `copper_uuid(key, locator)` of `manual-copper` ("Copper uuids and ids"), derived from the caller's intent key and the item's locator in the intent, and MUST take the Fenolite id that imported objects with that native id get, so a design read back from the written file has the same ids. These ids MUST NOT use the seeded generator, and `--seed` and `PYTHONHASHSEED` MUST NOT change them. A locator numbers an item inside its own intent, so changing one intent MUST NOT change the id of an item of another intent, and adding, removing or reordering intents MUST NOT change any id.

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

#### Scenario: DSL ids ignore the seed
- **GIVEN** the DSL design of `examples/blink_2layer/design.py`
- **WHEN** `uv run pytest tests/unit/dsl/test_ids.py -k seed` runs `dsl.to_model` on it in two processes whose other created `Design` objects use `seed=7` and `seed=8`
- **THEN** the two models have equal ids, and the component `R1` has the id `derived_id("cmp", "dsl", "component:R1")` in both

#### Scenario: Inserting a part keeps other ids
- **GIVEN** the blink design built for target 10
- **WHEN** a part `R2` is added to the script and the design is built again
- **THEN** every id and every KiCad uuid of `U1`, `R1` and `D1`, their pins, pads and nets, the board, the outline and the layers is unchanged

#### Scenario: Keys, not order
- **GIVEN** two DSL designs that add the same parts, nets and modules with their `add()` calls in different orders
- **WHEN** `dsl.to_model` runs on both
- **THEN** each object has the same id in both models, so the two sets of ids are equal

#### Scenario: Script copper ignores the seed
- **GIVEN** the routed blink of `examples/blink_routed/design.py`
- **WHEN** `uv run pytest tests/unit/lens/test_build_copper.py -k ids` builds it in two processes with `--seed 7` and `--seed 8`, and once more after adding a second stitch intent
- **THEN** every track and via of the first intents has the same id and native id in all three builds, and the native id of the segment `seg[0]` of `led_a` is `copper_uuid("led_a", "seg[0]")`

#### Scenario: Zone ids from the zone name
- **GIVEN** two DSL designs that declare the zones `GND` and `VIN_POUR` with their `zone()` calls in opposite orders
- **WHEN** `uv run pytest tests/unit/dsl/test_zones.py -k ids` runs `dsl.to_model` on both
- **THEN** in both models the zone `GND` has the id `derived_id("zon", "dsl", "zone:GND")` and the zone `VIN_POUR` the id `derived_id("zon", "dsl", "zone:VIN_POUR")`

#### Scenario: Rule ids from the kind and the class
- **GIVEN** two DSL designs that declare a board `clearance` minimum and a `track_width` minimum for the class `PWR` with their `minimum()` calls in opposite orders
- **WHEN** `uv run pytest tests/unit/dsl/test_minimums.py -k ids` runs `dsl.to_model` on both
- **THEN** in both models the rules have the ids `derived_id("rul", "dsl", "rule:clearance")` and `derived_id("rul", "dsl", "rule:track_width:PWR")`

#### Scenario: Area and drawing ids from names and keys
- **GIVEN** two DSL designs that declare the rule areas `ANT` and `HV`, the text `rev` and the dimension `width` in opposite orders
- **WHEN** `uv run pytest tests/unit/dsl/test_ids.py -k board_items` runs `dsl.to_model` on both
- **THEN** in both models the keep-out `ANT` has the id `derived_id("kpo", "dsl", "area:ANT")`, the text `derived_id("txt", "dsl", "text:rev")` and the dimension `derived_id("dim", "dsl", "dimension:width")`

### Requirement: Provenance record
`Provenance` MUST contain `backend`, `file`, `file_sha256`, `locator` and `evidence`, and `locator` MUST be treated as an opaque string by everything except the originating backend.

#### Scenario: Provenance attached on import
- **WHEN** any backend imports an object
- **THEN** `provenance.backend` names the backend and `provenance.file_sha256` equals the SHA-256 of the source file

### Requirement: Model layers for v0.1
The model SHALL provide the `circuit` layer (`Component`, `Pin`, `Net`, `NetClass`, `Interface`, `Module`), the `board` layer (`Board`, `Layer`, `Stackup`, `StackLayer`, `FootprintInstance`, `Pad`, optional minimal `Padstack`, `Track`, `Arc`, `Via`, `Zone`, `Keepout`, `Text`, `Graphic`, `Hole`, `Outline`), the `rules` layer (`Rule`, `RuleSet`, selector algebra `all | net | netclass | ref | layer | item_kind | and | or | not`, kinds `clearance`, `track_width`, `via_diameter`, `via_drill`, `hole_size`, `edge_clearance`), the `manufacturing` layer (`Manifest`, `PnpRow`) and the `findings` layer (`Issue`), aggregated by `Design` with read-only indexes `by_id`, `by_ref`, `by_net`, `by_layer`.

The model SHALL also provide the `presentation` module `fenolite.model.presentation`:
- the value objects `TitleBlock` (`title`, `date`, `revision`, `organization`, `doc_id`, `responsible`, `approver`, all `""` by default, and `params`, a mapping of parameter name to text, empty by default) and `SheetFrameRef` (`paper`, one of `A0` … `A5`, `Letter`, `Legal`, `Tabloid` and `custom`, default `A4`; `portrait`, default false; `width` and `height` in nm, used only by `custom`; `drawing_sheet`, a project-relative path or `None`);
- `Board.title_block: TitleBlock | None` and `Board.sheet: SheetFrameRef | None`, both defaulting to `None`, stored in `board.json`;
- the definition `DrawingSheet` and its items, which are not part of `Design` and not stored in the `.fenolite/` layer files (requirement "Drawing sheet definitions").

The six layer files keep their names, and the circuit, rules, manufacturing and findings layers and the `Design` indexes are unchanged.

#### Scenario: Indexes resolve
- **GIVEN** a design with component `R1` on net `GND`
- **WHEN** `design.by_ref["R1"]` and `design.by_net["GND"]` are read
- **THEN** the component and the set of pads on `GND` are returned

#### Scenario: Duplicate reference is a finding
- **GIVEN** two components with `ref = "R1"`
- **WHEN** `design.validate()` runs
- **THEN** an `Issue` with code `model.duplicate-ref` and severity `error` is produced

#### Scenario: Board carries the sheet and title block
- **GIVEN** a `Board` with `sheet = SheetFrameRef("A3", drawing_sheet="frame.kicad_wks")` and `title_block = TitleBlock(title="Bench", params={"LOT": "7"})`
- **WHEN** the design is written with `canonical.dump_dir` and loaded again with `canonical.load_dir`
- **THEN** the loaded board's `sheet` and `title_block` equal the originals, and `board.json` holds both under the keys `sheet` and `title_block`

#### Scenario: Board documents without presentation fields load
- **GIVEN** a `board.json` written before this change, without the keys `sheet` and `title_block`
- **WHEN** it is loaded with `canonical.loads` and validated against the regenerated `board.json` schema
- **THEN** loading succeeds, validation passes, and `board.sheet` and `board.title_block` are `None`

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
- `SymbolDef`: an entity with `name`, `library`, `extends`, `power`, `properties`, `in_bom`, `on_board`, `exclude_from_sim`, pin-name settings, `units`, `pins` and ordered symbol-local `graphics`
- `SymbolPin`, `SymbolUnit` and `PinAlternate`: value objects without the entity header
- `Library`: a container with `name`, `footprints` and `symbols`

Library definitions MUST obey these rules:
- They MUST be immutable.
- They MUST use integer nanometres and microdegrees.
- `FootprintDef.pads` and `FootprintDef.graphics` MUST reuse the board `Pad` and `Graphic` entities, with `net_id = None` and positions relative to the definition's origin. A pad with per-layer shapes MUST carry them in `Pad.padstack`.
- Every field other than `name` MUST have a default. The tuples `keywords`, `flags`, `pads`, `graphics`, `models`, `units`, `pins` and `alternates` MUST be marked ordered, so the canonical form keeps their order. `properties` is a mapping and its canonical form is sorted by key.
- Library definitions MUST NOT be part of `Design` or of the `.fenolite/` layer files.

`SymbolGraphic` MUST be an immutable value object with a supported primitive kind, ordered `Point` coordinates in symbol-local nanometres, integer stroke width and fill state. The graphics tuple MUST keep drawing order in the canonical form.

#### Scenario: Symbol body graphics keep order
- **GIVEN** a `SymbolDef` with a rectangle followed by two line graphics
- **WHEN** it is dumped and loaded with `canonical.dumps` and `canonical.loads`
- **THEN** the kinds remain `rect`, `line`, `line` in that order

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

### Requirement: Drawing sheet definitions
`fenolite.model.presentation` SHALL provide the drawing-sheet definition `DrawingSheet(name, setup, items)`, an entity with the common header, and its value objects:
- `SheetSetup(text_size, line_width, text_line_width, left_margin, right_margin, top_margin, bottom_margin)`;
- `SheetPoint(corner="rb", x=0, y=0)`: an offset from the named corner (`lt`, `lb`, `rt`, `rb`) of the margin box, which is the page minus the setup margins, positive toward the interior;
- `SheetRepeat(count=1, step_x=0, step_y=0, label_step=1)`: `label_step` defaults to 1, the value KiCad uses when `incrlabel` is absent (`H-K-WKS-REPEAT`);
- the items `SheetShape` (`kind` in `line | rect`, required, `start`, `end`, `width=None`), `SheetText` (`text`, `pos`, `size=None`, `bold`, `italic`, `justify` in `left | center | right`, `vjustify` in `top | center | bottom`, `rotation` in µdeg, `max_len`, `max_height`) and `SheetBitmap` (`pos`, `png` as base64 text, `scale_ppm=1_000_000`), each with `repeat`, `scope` in `all | first_only | not_first`, `name` and `comment`.

These rules MUST hold:
- Every definition and value object MUST be immutable. Lengths MUST be integer nm, angles integer µdeg and the bitmap scale integer parts per million; no field MAY be a float.
- `DrawingSheet.items` MUST be marked ordered, so the canonical form keeps the drawing order.
- The item union MUST decode without ambiguity, because `canonical.loads` takes the first union member that decodes and the canonical form leaves out default values. `SheetShape.kind` MUST have no default, as `Graphic.kind` has none, so it is always written; `SheetText` and `SheetBitmap` differ by their required fields (`text`, `png`).
- A `DrawingSheet` MUST NOT be part of `Design` or of the `.fenolite/` layer files: one sheet serves many boards and sizes.
- Texts MUST hold only neutral tokens. `SHEET_TOKENS` SHALL be `title`, `doc_id`, `revision`, `sheet`, `sheets`, `date`, `organization`, `responsible`, `approver`, `filename` and `paper`. `split_tokens(text)` SHALL split a text into literal strings and `SheetToken(name, param=False)` values, reading `{name}` for a name of `SHEET_TOKENS`, `{param:NAME}` for a name matching `[A-Za-z_][A-Za-z0-9_]*`, and `{{` and `}}` as literal braces. It MUST raise `ValueError` for an unknown or malformed token. Every `SheetText.text` that a builder or reader produces MUST be accepted by `split_tokens`.
- `PAPER_SIZES` SHALL map `A0` … `A5`, `Letter`, `Legal` and `Tabloid` to their portrait width and height in nm: A0 to A4 from S-0077, A5 and the US sizes from S-0079, with inches converted at exactly 25.4 mm.

#### Scenario: Tokens split
- **WHEN** `split_tokens("Rev {revision} lot {param:LOT_NO} {{x}}")` is called
- **THEN** it returns `("Rev ", SheetToken("revision"), " lot ", SheetToken("LOT_NO", param=True), " {x}")`

#### Scenario: Unknown token refused
- **WHEN** `split_tokens("{owner}")` and `split_tokens("{param:9X}")` are called
- **THEN** each raises `ValueError` naming the token

#### Scenario: Paper sizes are exact
- **WHEN** `PAPER_SIZES["A4"]`, `PAPER_SIZES["Letter"]` and `PAPER_SIZES["Tabloid"]` are read
- **THEN** they are `(210_000_000, 297_000_000)`, `(215_900_000, 279_400_000)` and `(279_400_000, 431_800_000)`

#### Scenario: Item order survives the canonical form
- **GIVEN** a `DrawingSheet` whose items are a `SheetText`, a `SheetShape` of kind `rect`, a `SheetShape` of kind `line` and a `SheetBitmap`, in that order, each with only its required fields set
- **WHEN** it is dumped and loaded with `canonical.dumps` and `canonical.loads`
- **THEN** the items keep that order, each loaded item has the type and `kind` of its original, and the loaded sheet equals the original

#### Scenario: Sheets are not layer content
- **GIVEN** a design whose board has `sheet = SheetFrameRef("A4", drawing_sheet="frame.kicad_wks")`
- **WHEN** `canonical.dump_dir` writes it
- **THEN** the same six layer files are written and none of them contains a `DrawingSheet`

### Requirement: Identifiers of drawing sheets
The closed prefix table SHALL include `wks` (drawing sheet).
Both ids below are the case "imported objects with a native id" of "Identifier derivation", which this change does not modify: the `<backend>` part names the source format, and the native id is a name that the source file declares, as library names are for definitions read from a library.
- A sheet built from a `*.sheet.toml` specification comes from that file, whose `sheet.name` is its native id: its id MUST be `derived_id("wks", "template", <sheet.name>)`.
- A sheet read from a KiCad file MUST have the id `derived_id("wks", "kicad", <name>)`, where `<name>` is the `name` argument of the reader or, when it is `None`, the file stem (`""` for text read without a file name).
- Sheet items, `TitleBlock` and `SheetFrameRef` MUST carry no ids.

#### Scenario: Same name, same id
- **WHEN** `tests/data/kicad/sheets/all_items.kicad_wks` is read twice
- **THEN** both sheets have the id `derived_id("wks", "kicad", "all_items")`

#### Scenario: Prefix accepted
- **WHEN** `new_id("wks", random.Random(1))` is called
- **THEN** it returns an id starting with `wks_`, and `new_id("wkx", random.Random(1))` raises `ValueError`

### Requirement: Drawing sheet schema
`tools/gen_schemas.py` SHALL generate `schemas/fenolite.model.v0/drawing_sheet.json` with schema id `fenolite.drawing_sheet.v0` from `fenolite.model.presentation.DrawingSheet`, and SHALL regenerate `board.json` with the optional `sheet` and `title_block` fields. The schema drift test MUST cover `drawing_sheet.json`, and `canonical.dumps`/`canonical.loads` MUST round-trip a `DrawingSheet` idempotently.

#### Scenario: Schema drift detected
- **GIVEN** a contributor adds a field to `SheetText` without regenerating schemas
- **WHEN** `uv run pytest tests/unit/test_schema_drift.py` runs
- **THEN** it fails naming `drawing_sheet.json`

#### Scenario: Float rejected in a sheet document
- **GIVEN** a `drawing_sheet.json` document where `items[0].pos.x` is `1.5`
- **WHEN** it is validated against the drawing-sheet schema
- **THEN** validation fails with a message naming `/items/0`, the pointer of the union item that matches no alternative (the repository validator `tests/_schema.py` reports an `anyOf` failure at the union node)

#### Scenario: Schemas up to date
- **WHEN** `uv run python tools/gen_schemas.py --check` runs
- **THEN** it exits 0

### Requirement: Presentation values are validated
`Design.validate()` SHALL report these errors for the presentation fields of the board:

| code | severity | when |
|---|---|---|
| `model.sheet-path` | error | `Board.sheet.drawing_sheet` is an absolute path (a leading `/` or `\`, or a drive letter) or holds a `..` segment |
| `model.sheet-size` | error | `custom` without both `width` and `height`; `width` or `height` set on a named size; `portrait` set on `custom`; or a `custom` size equal, in either orientation, to `Letter`, `Legal` or `Tabloid` |
| `model.param-name` | error | a key of `TitleBlock.params` that does not match `[A-Za-z_][A-Za-z0-9_]*` |

`drawing_sheet` MAY be a POSIX path relative to the project or start with `${KIPRJMOD}/`.

#### Scenario: Absolute sheet path
- **GIVEN** a board with `sheet = SheetFrameRef("A4", drawing_sheet="/srv/frames/frame.kicad_wks")`
- **WHEN** `design.validate()` runs
- **THEN** an `Issue` with code `model.sheet-path` and severity `error` is produced

#### Scenario: Custom size equal to Letter
- **GIVEN** a board with `sheet = SheetFrameRef("custom", width=279_400_000, height=215_900_000)`
- **WHEN** `design.validate()` runs
- **THEN** an `Issue` with code `model.sheet-size` is produced

#### Scenario: Bad parameter name
- **GIVEN** a board with `title_block = TitleBlock(params={"LOT NO": "7"})`
- **WHEN** `design.validate()` runs
- **THEN** an `Issue` with code `model.param-name` naming `LOT NO` is produced

#### Scenario: Valid presentation
- **GIVEN** a board with `sheet = SheetFrameRef("A3", drawing_sheet="${KIPRJMOD}/frame.kicad_wks")` and `title_block = TitleBlock(params={"LOT_NO": "7"})`
- **WHEN** `design.validate()` runs
- **THEN** no `model.sheet-*` or `model.param-name` issue is produced

### Requirement: No-connect marks in the circuit model
The circuit layer SHALL record the pins that a design leaves unconnected on purpose as `Circuit.no_connects: tuple[PinRef, ...]`, the last field of `Circuit`, empty by default. A mark is a `PinRef(component_id, pin)` in the form of a net member: `pin` holds a designator as written until a build resolves it, and a pin number afterwards.
- The mark is a fact of the connection, not of the library pin: `Pin` and `PinType` are unchanged, and `Pin.etype == "no_connect"` keeps its meaning (the pin type that the symbol declares).
- A mark has no id and no entity header; `KEYS` and "Identifier derivation" are unchanged.
- `to_model` and the builds MUST store the marks in `PinRef` order without duplicates.
- The change MUST be additive. `canonical` omits the default, so a design without marks gives the `circuit.json` bytes it gave before; a `circuit.json` without the key `no_connects` MUST load with `no_connects == ()`. `SCHEMA_VERSION` stays `"0"`, and `schemas/fenolite.model.v0/circuit.json` MUST be regenerated with `tools/gen_schemas.py`, with `no_connects` as an optional array of pin references.
- `Design.validate()` MUST report, for each mark, with `where` set to `<ref>-<pin>` (or `<component id>-<pin>` when the component is unknown):
  - `model.no-connect-on-net` (error) when a net lists the same `PinRef`, the message naming the net;
  - `model.unknown-component` (error) when no component has the id;
  - `model.unknown-pin` (error) when the component holds pins and none has the number.
- A marked pin MUST NOT be counted as a member of any net: `by_net` and the net findings (`model.single-pin-net`, `model.dangling-net`) are unchanged.
- `docs/design-model.md` MUST describe the field, the two forms of `pin` and the three findings, and `docs/cli-contract.md` MUST list `model.no-connect-on-net` with the model findings.

#### Scenario: Marks survive the canonical round trip
- **GIVEN** a design whose `Circuit.no_connects` holds `PinRef(<U1 id>, "11")` and `PinRef(<U1 id>, "12")`
- **WHEN** it is written with `canonical.dump_dir`, loaded with `canonical.load_dir` and its `circuit.json` validated against the regenerated schema
- **THEN** the loaded marks equal the originals, validation passes, and `circuit.json` holds them under the key `no_connects`

#### Scenario: Circuits without marks are unchanged
- **GIVEN** a `circuit.json` written before this change, and the same design dumped after it
- **WHEN** the old file is loaded and the two texts are compared
- **THEN** loading succeeds with `no_connects == ()`, and the texts are equal byte for byte

#### Scenario: Schema is regenerated
- **WHEN** `uv run python tools/gen_schemas.py --check` and `uv run pytest tests/unit/test_schema_drift.py` run
- **THEN** both pass, and `schemas/fenolite.model.v0/circuit.json` names `no_connects` outside its `required` list

#### Scenario: Marked pin on a net
- **GIVEN** a design whose net `EN` lists `PinRef(<U1 id>, "11")` and whose `Circuit.no_connects` holds the same reference
- **WHEN** `design.validate()` runs
- **THEN** it reports one `model.no-connect-on-net` of severity `error` whose `where` is `U1-11` and whose message names `EN`

#### Scenario: Mark on a pin the component does not hold
- **GIVEN** a component `U1` with the pins `1` and `2`, and a mark `PinRef(<U1 id>, "9")`
- **WHEN** `design.validate()` runs
- **THEN** it reports one `model.unknown-pin` of severity `error` whose `where` is `U1-9`

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

### Requirement: Zone settings in the board model
`fenolite.model.board` SHALL describe the settings of a copper zone with two value objects without the entity header, `ZoneSettings` and `ZoneHatch`, and SHALL add these fields, each with a default, so that documents written before them still load:
- `Zone.settings: ZoneSettings = ZoneSettings()`;
- `Zone.filled: bool = False`, the board's own fill flag (KiCad's `(fill yes)`), kept apart from `Zone.fills`;
- `Zone.locked: bool = False`;
- `Pad.zone_connection: ZoneConnection | None = None`, where `None` means that the pad follows its footprint and the zone.

`ZoneSettings` MUST be a frozen dataclass with these fields. The defaults are the values KiCad gives a new zone (design Decision 3):

| field | type | default |
|---|---|---|
| `clearance` | `Nm` | 500 000 |
| `min_thickness` | `Nm` | 250 000 |
| `connection` | `ZoneConnection`: `solid`, `thermal`, `none`, `thru_hole_only` | `thermal` |
| `thermal_gap` | `Nm` | 500 000 |
| `thermal_spoke_width` | `Nm` | 500 000 |
| `island_removal` | `IslandRemoval`: `always`, `never`, `below_area` | `always` |
| `min_island_area` | `int`, in square nanometres | 10 000 000 000 000 (10 mm²) |
| `smoothing` | `ZoneSmoothing`: `none`, `chamfer`, `fillet` | `none` |
| `smoothing_radius` | `Nm` | 0 |
| `fill_mode` | `ZoneFillMode`: `solid`, `hatched` | `solid` |
| `hatch` | `ZoneHatch` | `ZoneHatch()` |

`ZoneHatch` MUST be a frozen dataclass with `thickness: Nm = 1_000_000`, `gap: Nm = 1_500_000`, `orientation: Udeg = 0`, `smoothing_level: int = 0`, `smoothing_value: str = "0.1"`, `border: HatchBorder = "hatch_thickness"` (`HatchBorder`: `hatch_thickness`, `min_thickness`) and `min_hole_area: str = "0.15"`. Ratios MUST be decimal strings, never floats.

`ZoneSettings.effective()` MUST return a copy in which every value that cannot change the fill is at its default: `hatch` when `fill_mode` is `solid`, `smoothing_radius` when `smoothing` is `none`, and `min_island_area` when `island_removal` is not `below_area`.

`tools/gen_schemas.py` MUST regenerate `schemas/fenolite.model.v0/board.json`, and `library.json`, whose pads are board `Pad`s, with the new fields and their closed vocabularies.

#### Scenario: Defaults of a new zone
- **WHEN** `Zone(id=..., outline=())` and `Pad(id=..., number="1", shape="rect", size=..., position=...)` are constructed
- **THEN** the zone has `settings == ZoneSettings()`, `settings.clearance == 500_000`, `settings.connection == "thermal"`, `filled == False` and `locked == False`, and the pad has `zone_connection is None`

#### Scenario: Old documents still load
- **GIVEN** a `board.json` written before this change, without the new fields
- **WHEN** `canonical.loads` reads it into a `Board`
- **THEN** every zone has `settings == ZoneSettings()`, `filled == False` and `locked == False`, and every pad has `zone_connection is None`

#### Scenario: Unknown connection rejected
- **GIVEN** a `board.json` document where `zones[0].settings.connection` is `"partial"`
- **WHEN** it is validated against `schemas/fenolite.model.v0/board.json`
- **THEN** validation fails with the JSON pointer of that value

#### Scenario: Float rejected in settings
- **GIVEN** a `board.json` document where `zones[0].settings.clearance` is `0.3`
- **WHEN** it is validated against `schemas/fenolite.model.v0/board.json`
- **THEN** validation fails

#### Scenario: Values without effect are dropped
- **GIVEN** `ZoneSettings(fill_mode="solid", hatch=ZoneHatch(gap=2_000_000), smoothing="none", smoothing_radius=1_000_000, island_removal="never", min_island_area=5_000_000_000_000)`
- **WHEN** `effective()` is called
- **THEN** the result equals `ZoneSettings(island_removal="never")`

#### Scenario: Schemas regenerated
- **WHEN** `uv run python tools/gen_schemas.py --check` runs after this change
- **THEN** it exits 0, `board.json` lists `settings`, `filled`, `locked` and `zone_connection`, and `library.json` lists `zone_connection`

### Requirement: Persist per-component pin-to-pad maps
`Component` SHALL carry a canonical `pin_pad_map` of ordered `(symbol pin number, physical pad number)` pairs. Each source and target SHALL be non-empty and unique within its side. An empty map SHALL mean identity assignment.

#### Scenario: Serialize an explicit map
- **GIVEN** a component maps pin `1` to pad `2`
- **WHEN** the model is serialized and read back
- **THEN** the pair remains `("1", "2")` in `pin_pad_map`

#### Scenario: Preserve identity default
- **GIVEN** a component with no explicit map
- **WHEN** it is serialized and read back
- **THEN** `pin_pad_map` is empty and the build applies identity mapping

### Requirement: Buses in the circuit model
The circuit layer SHALL record a bus, an indexed vector of nets, as the entity `fenolite.model.circuit.Bus` in `Circuit.buses: tuple[Bus, ...]`, empty by default.
- `Bus` MUST carry the common entity header, `name: str` (the vector's name without its range, `D` for `D[0..7]`) and `members: tuple[BusMember, ...]`, ordered. `BusMember` MUST be a frozen value object with `index: int` and `net_id: str`. A member that has no net is left out, so indexes may have gaps.
- A bus differs from an `Interface`, which maps role names to nets: a bus is ordered and indexed. A group of nets with different names (a harness, a KiCad group bus) stays an `Interface`.
- The closed prefix table SHALL include `bus`.
- The change MUST be additive. `canonical` omits the default, so a design without buses gives the `circuit.json` bytes it gave before, and a `circuit.json` without the key `buses` MUST load with `buses == ()`. `SCHEMA_VERSION` stays `"0"`, and `schemas/fenolite.model.v0/circuit.json` MUST be regenerated with `buses` as an optional array.
- `Design.entities()` MUST yield buses, and `Design.validate()` MUST report, with `where` set to the bus name:
  - `model.unknown-net` (error) for a member whose `net_id` is no net of the circuit;
  - `model.duplicate-bus-index` (error) for an index used twice in one bus.
- A bus gives no net and no net member: `by_net` and the net findings are unchanged. No backend writes a bus in this change; the KiCad and Altium builds MUST keep it in `.fenolite/` and MUST NOT depend on it.
- `docs/design-model.md` MUST describe the entity and its two findings, and `docs/cli-contract.md` MUST list `model.duplicate-bus-index` with the model findings.

#### Scenario: Buses survive the canonical round trip
- **GIVEN** a design whose circuit holds the bus `D` with the members `(0, <D0 id>)` and `(1, <D1 id>)`
- **WHEN** it is written with `canonical.dump_dir`, loaded with `canonical.load_dir` and its `circuit.json` validated against the regenerated schema
- **THEN** the loaded bus equals the original with its member order, and validation passes

#### Scenario: Circuits without buses are unchanged
- **GIVEN** a `circuit.json` written before this change, and the same design dumped after it
- **WHEN** the old file is loaded and the two texts are compared
- **THEN** loading succeeds with `buses == ()`, and the texts are equal byte for byte

#### Scenario: Member without a net
- **GIVEN** a bus with a member whose `net_id` names no net, and a bus with the index 3 twice
- **WHEN** `design.validate()` runs
- **THEN** it reports one `model.unknown-net` and one `model.duplicate-bus-index`, both of severity `error`, each with the bus name as `where`

#### Scenario: Bus prefix
- **WHEN** `new_id("bus", rng)` and `new_id("busx", rng)` are called
- **THEN** the first returns an id that starts with `bus_` and the second raises `ValueError`

### Requirement: Padstack holes and offsets
The board layer SHALL describe a pad's hole and its copper offsets in `Padstack`, with fields that all have defaults, so that documents written before them still load. The three hole fields were already added by change c0056 (slotted pads of the DSL and of the KiCad footprint reader) when this change was implemented; this change adds `PadstackLayer.offset` and restates the others.
- `Padstack.hole_shape: HoleShape = "round"`, one of `round`, `square` and `slot`.
- `Padstack.hole_length: Nm | None = None`: the length of a slot along its axis, ends included. `Pad.drill` stays the hole's size: the diameter of a round hole, the side of a square hole and the width of a slot.
- `Padstack.hole_rotation: Udeg = 0`: the angle of the hole's axis relative to the footprint.
- `PadstackLayer.offset: Point = Point(0, 0)`: where the copper's centre lies on that layer relative to `Pad.position`, the centre of the hole, in the footprint frame.
- `Padstack.layers` MAY be empty: a pad with one shape on all its layers and a hole that is not round has a padstack without layer entries. `Pad.padstack is None` MUST still mean one shape on all layers, a round hole or no hole, and no offset.
- In a library definition, `PadstackLayer.layer` MAY be the wildcard `In*.Cu`, every inner copper layer, as `Pad.layers` of a definition may hold `*.Cu`. On a board it MUST be a real layer.
- `tools/gen_schemas.py` MUST regenerate `schemas/fenolite.model.v0/board.json` and `library.json` with the new fields and the closed vocabulary of `hole_shape`.
- No reader or writer of the KiCad backend changes in this change: the KiCad backend reads and writes a slotted hole since c0056, and a KiCad offset drill stays in the pad's opaque slots, as today.

#### Scenario: Old documents still load
- **GIVEN** a `board.json` written before this change that holds a pad with a padstack of two layers
- **WHEN** `canonical.loads` reads it into a `Board`
- **THEN** the padstack has `hole_shape == "round"`, `hole_length is None` and `hole_rotation == 0`, and each layer `offset == Point(0, 0)`

#### Scenario: Unknown hole shape rejected
- **GIVEN** a `board.json` document where a padstack's `hole_shape` is `"oval"`
- **WHEN** it is validated against `schemas/fenolite.model.v0/board.json`
- **THEN** validation fails with the JSON pointer of that value

#### Scenario: Slot without layer entries
- **GIVEN** `Padstack(id=…, hole_shape="slot", hole_length=2_500_000, hole_rotation=90_000_000)` on a pad with `drill == 1_000_000`
- **WHEN** the board is dumped and loaded with `canonical.dumps` and `canonical.loads`
- **THEN** the loaded padstack equals the original and has `layers == ()`

#### Scenario: Schemas regenerated
- **WHEN** `uv run python tools/gen_schemas.py --check` runs after this change
- **THEN** it exits 0, and `board.json` and `library.json` list `hole_shape`, `hole_length`, `hole_rotation` and `offset`

### Requirement: Component bodies
The board layer SHALL describe the physical body of a part as the entity `fenolite.model.board.ComponentBody`, in `FootprintInstance.bodies: tuple[ComponentBody, ...]` and `FootprintDef.bodies: tuple[ComponentBody, ...]`, both ordered and empty by default.
- `ComponentBody` MUST carry the common entity header and: `kind: BodyKind` (`extruded` or `model`); `height: Nm`, the distance from the board surface to the top of the body; `standoff: Nm = 0`, the distance from the board surface to its underside; `outline: tuple[Point, ...] = ()`, ordered, the body's footprint as a polygon in the footprint frame of "Board entities read from file backends" (empty when the source gives none); `layer: str = ""`, the layer the body is drawn on; `model: str = ""`, the name of a 3D model for the kind `model`; and `name: str = ""`. Optional `z_min: Nm | None = None` and `z_max: Nm | None = None` MUST form a signed authoritative interval in the mounted-face frame, positive outwards from that board surface. `projection_unknown: bool = False` SHALL mark retained source geometry with unproved projection; analysis MUST not project such a body. Both MUST be absent or both present with z_min <= z_max; no float enters the model.
- A legacy body without signed bounds states a volume above the side the footprint is placed on. A body with signed bounds may cross that surface; its interval and documented footprint/side transform state that extent without zero-clamping native source values. It carries no model data: `FootprintDef.models` keeps its meaning (the model references of a definition), and no file is embedded.
- The outward height of a part is the largest authoritative upper bound of its known bodies (`z_max` when present, legacy `height` otherwise). Below-surface extent MUST remain available to volume analysis. A part without known body extents has unknown height.
- The closed prefix table SHALL include `bdy`.
- `Design.validate()` MUST report `model.body-height` (error), with `where` set to the body's id, for a body without signed bounds and without projection_unknown whose `height` is below its `standoff` or whose `standoff` is negative. A half-specified or reversed signed interval MUST report `model.body-volume` (error) at the body's id. When the interval is present it is authoritative; legacy source height/standoff values may remain as provenance and MUST NOT override it.
- No reader or writer of the KiCad backend changes: definitions read from KiCad files hold no body, so a placed copy has none, and a KiCad build MUST keep the bodies of a design in `.fenolite/` only.
- `tools/gen_schemas.py` MUST regenerate `board.json` and `library.json` with `ComponentBody` and `bodies`. `docs/design-model.md` MUST describe the entity, and `docs/cli-contract.md` MUST list `model.body-height` and `model.body-volume` and document the mounted-face frame and authoritative-interval precedence.

#### Scenario: Old documents still load
- **GIVEN** a `board.json` and a `library.json` written before component bodies were introduced, with no bodies keys
- **WHEN** `canonical.loads` reads them
- **THEN** every footprint and every definition has `bodies == ()`

#### Scenario: Body survives the canonical round trip
- **GIVEN** a footprint with one `ComponentBody(kind="extruded", height=1_016_000, outline=<four points>, layer="Mech.13")`
- **WHEN** its board is dumped and loaded with `canonical.dumps` and `canonical.loads`
- **THEN** the loaded body equals the original, and the outline keeps its point order

#### Scenario: Height below standoff
- **GIVEN** a body with `height == 500_000` and `standoff == 800_000`
- **WHEN** `design.validate()` runs
- **THEN** it reports one `model.body-height` of severity `error` whose `where` is the body's id

#### Scenario: Unknown body kind rejected
- **GIVEN** a `board.json` document where a body's `kind` is `"sphere"`
- **WHEN** it is validated against `schemas/fenolite.model.v0/board.json`
- **THEN** validation fails with the JSON pointer of that value

#### Scenario: Body prefix
- **WHEN** `derived_id("bdy", "altium", "x")` and `derived_id("bdyx", "altium", "x")` are called
- **THEN** the first returns an id that starts with `bdy_` and the second raises `ValueError`

#### Scenario: Signed interval validation
- **GIVEN** an authored body has both signed bounds in order and crosses its mounting plane
- **WHEN** canonical serialization and Design.validate run
- **THEN** both bounds survive and the legacy negative-standoff rule does not invalidate the authoritative interval

#### Scenario: Incomplete interval refused
- **GIVEN** an authored body specifies only one signed bound or supplies them in reverse order
- **WHEN** Design.validate runs
- **THEN** it reports model.body-volume at that body instead of inferring or reordering the interval

#### Scenario: Legacy body document compatibility
- **GIVEN** a body document generated by the model at tag v0.2.0
- **WHEN** canonical.loads and canonical.dumps run
- **THEN** z_min and z_max default to None, projection_unknown defaults to False, and the bytes are unchanged; legacy height validation still applies until source reimport

### Requirement: Schematic sheet definitions
`fenolite.model.schematic` SHALL provide the schematic-sheet definition `SchematicSheet`, an entity with the common header, and the entities and value objects it holds:
- `SchematicSheet(name, paper, title_block, lib_symbols, symbols, labels, no_connects, wires, sheets, pages)`: `paper` is a `SheetFrameRef` (default `SheetFrameRef("A4")`), `title_block` a `TitleBlock` or `None`, `lib_symbols` a tuple of `SymbolDef`, and the other collections tuples of the types below;
- `SymbolInstance(lib_ref, position, rotation=0, mirror="", unit=1, body_style=1, ref="", value="", footprint="", properties={}, dnp=False, in_bom=True, on_board=True, exclude_from_sim=False, lib_name="", uses=())`, an entity: `mirror` in `"" | "x" | "y"`, and `uses` a tuple of `SymbolUse(project, path, ref, unit=1)`;
- `NetLabel(kind, name, position, rotation=0, shape="")`, an entity: `kind` in `local | global | hierarchical`, `shape` in `"" | input | output | bidirectional | tri_state | passive`;
- `NoConnectFlag(position)`, an entity;
- `Wire(start, end)`, an entity: two `Point`s;
- `SheetRef(name, file, position, size, uses=())`, an entity, with `uses` a tuple of `SheetUse(project, path, page)`;
- `SheetPage(path, page)`.

These rules MUST hold:
- Every entity and value object MUST be immutable. Positions MUST be `Point` in integer nm and rotations integer µdeg; no field MAY be a float.
- `SymbolInstance.rotation` MUST be 0, 90 000 000, 180 000 000 or 270 000 000.
- `NetLabel.kind` MUST have no default, so the canonical form always writes it.
- A `Wire` MUST be horizontal or vertical, with `start != end`; any other pair raises `ValueError`. Only created sheets hold wires: the KiCad reader leaves `wires` empty and keeps a file's wires as opaque slots (`kicad-schematic`, "Modelled schematic content").
- `lib_symbols`, `symbols`, `labels`, `no_connects`, `wires`, `sheets`, `pages` and `uses` MUST be marked ordered, so the canonical form keeps file order. `properties` MUST be sorted by key in the canonical form.
- A `SchematicSheet` MUST NOT be part of `Design` or of the `.fenolite/` layer files: a generated sheet is derived from the circuit, and a sheet read from a file is checked and compared, not imported.
- `fenolite.model.schematic` MUST import only `core` and `model`.

#### Scenario: Canonical round trip keeps order
- **GIVEN** a `SchematicSheet` built in the test with two symbol instances, three labels of the three kinds, one no-connect flag and one wire, each with only its required fields set
- **WHEN** it is dumped and loaded with `canonical.dumps` and `canonical.loads`
- **THEN** the loaded sheet equals the original, and every collection keeps its order

#### Scenario: Label kind is always written
- **WHEN** a `NetLabel("local", "N1", Point(0, 0))` is dumped with `canonical.dumps`
- **THEN** the text holds `"kind": "local"`

#### Scenario: Sheets are not layer content
- **GIVEN** a design built for the blink example
- **WHEN** `canonical.dump_dir` writes it
- **THEN** the same six layer files are written, and none of them contains a `SchematicSheet`

#### Scenario: Model stays backend-free
- **GIVEN** a version of `src/fenolite/model/schematic.py` that imports `fenolite.backends`
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it fails naming `model → backends`

#### Scenario: Slanted wire refused
- **WHEN** `Wire(Point(0, 0), Point(1_270_000, 1_270_000))` is created
- **THEN** `ValueError` is raised

### Requirement: Identifiers of schematic entities
The closed prefix table SHALL include `sch` (schematic sheet), `sci` (symbol instance), `lbl` (label), `ncf` (no-connect flag), `shr` (sheet reference) and `wir` (wire).
- An entity read from a file MUST have the id `derived_id(<prefix>, <backend>, <native id>)`, the native id being the one its backend names (`kicad-schematic`, "Identifiers of schematic items").
- An entity that Fenolite creates for a design MUST have an id derived from the design, so two builds of one design give equal ids: the sheet `derived_id("sch", "fenolite", "<design name>")`, and each entity `derived_id(<prefix>, "fenolite", "<design name>:<key>")`, where `<key>` is stated by the change that creates it.
- `SymbolUse`, `SheetUse` and `SheetPage` MUST carry no ids.

#### Scenario: Prefixes accepted
- **WHEN** `new_id` is called with each of `sch`, `sci`, `lbl`, `ncf`, `shr` and `wir` and `random.Random(1)`
- **THEN** each returns an id that starts with its prefix, and `new_id("scx", random.Random(1))` raises `ValueError`

#### Scenario: Same uuid, same id
- **WHEN** `tests/data/kicad/schematic/flat.kicad_sch` is read twice
- **THEN** both sheets have the id `derived_id("sch", "kicad", <the root uuid of the file>)`

### Requirement: Schematic sheet schema
`tools/gen_schemas.py` SHALL generate `schemas/fenolite.model.v0/schematic.json` with schema id `fenolite.schematic.v0` from `fenolite.model.schematic.SchematicSheet`. The schema drift test MUST cover it, and `canonical.dumps`/`canonical.loads` MUST round-trip a `SchematicSheet` idempotently.

#### Scenario: Schema drift detected
- **GIVEN** a contributor adds a field to `SymbolInstance` without regenerating schemas
- **WHEN** `uv run pytest tests/unit/test_schema_drift.py` runs
- **THEN** it fails naming `schematic.json`

#### Scenario: Float rejected in a sheet document
- **GIVEN** a `schematic.json` document where `symbols[0].position.x` is `1.5`
- **WHEN** it is validated against the schematic schema with `tests/_schema.py`
- **THEN** validation fails with a message naming `/symbols/0/position/x`

#### Scenario: Schemas up to date
- **WHEN** `uv run python tools/gen_schemas.py --check` runs
- **THEN** it exits 0

### Requirement: Outward height of a part
`fenolite.model.board.outward_height(footprint: FootprintInstance) -> Nm | None` SHALL return the height of a placed part above the board surface on its own side, as "Component bodies" defines it, and SHALL be the one place of the package that computes it.
- A body is known when its `projection_unknown` is false. The upper bound of a known body is its `z_max` when the body has signed bounds, and its `height` otherwise.
- The function MUST return the largest upper bound of the footprint's known bodies, and `None` when the footprint has no known body or that bound is not positive. It MUST NOT read the component, a footprint property, a 3D model reference or the footprint's definition, and it MUST NOT read `standoff` or `z_min`: what lies below the top of a body is the business of the volume analysis.
- It is pure: no file, no clock, integers only.
- A consumer that needs the height of a part (a placement rule, a checker, an exporter) MUST call this function. No other field of the model holds a part's height: `Component` has none, and a script states a height by giving the part a body (`design-dsl`, "Part heights and height limits in the DSL").
- `docs/design-model.md` MUST say this under "Component bodies".

#### Scenario: Largest known body
- **GIVEN** a footprint with three bodies: one with `height == 2_000_000`, one with `z_min == -500_000` and `z_max == 9_000_000` (and a legacy `height` of 3 mm kept as provenance), and one with `height == 30_000_000` and `projection_unknown` true
- **WHEN** `uv run pytest tests/unit/model/test_outward_height.py -k largest` calls `outward_height`
- **THEN** it returns `9_000_000`: the signed bound wins over that body's legacy height, and the body of unknown projection makes no claim

#### Scenario: No known height
- **WHEN** `outward_height` is called for a footprint without bodies, for one whose only body has `projection_unknown` true, and for one whose only body has `z_min == -4_000_000` and `z_max == 0`
- **THEN** each call returns `None`

#### Scenario: One reader
- **WHEN** `uv run pytest tests/unit/model/test_outward_height.py -k one_reader` searches `src/fenolite/checks/placement.py`, `src/fenolite/cli/cmd_place.py` and `src/fenolite/cli/cmd_build.py` for attribute reads of `.z_max` and for iteration over `.bodies`
- **THEN** it finds none: the placement rules reach a part's height only through `outward_height`

### Requirement: Height limits in the model
`fenolite.model.rules` SHALL define the frozen value object `HeightLimit(area, max, severity="error")`, and `RuleSet` SHALL gain the field `heights: tuple[HeightLimit, ...]`, empty by default and stored in `rules.json`. This is an addition to the rules layer of "Model layers for v0.1", beside the proximity rules of "Proximity rules in the model".
- `area` MUST be a non-empty name of a rule area; `max` a positive length in nm; `severity` a `PlacementSeverity`. `HeightLimit` MUST raise `ValueError` otherwise, and `RuleSet` MUST raise `ValueError` for two limits of one `area`.
- It is a value object, not an entity: it carries no id, and its area is its key. `to_model` writes the limits in area order.
- A height limit is not a rule of `RuleSet.rules` and has no `RuleKind`. No backend lowers it: the KiCad writer and `lower_rules` read only `RuleSet.rules`, the Altium rule table (`altium-pcb-writer`, "Rule lowering table") gains no row, and a board read from a file has none.
- `schemas/fenolite.model.v0/rules.json` MUST be regenerated. A `rules.json` without the key `heights` MUST load with an empty tuple, and a rule set without limits MUST be written without the key, so a design that declares none writes the bytes it wrote before this change. `SCHEMA_VERSION` stays `"0"`.
- `docs/design-model.md` MUST describe the value object and the field, and MUST say that 0.2.x and 0.3.0 cannot read a `rules.json` that carries `heights`.

#### Scenario: Limits round trip
- **GIVEN** a design whose `RuleSet.heights` holds `HeightLimit("LID", 5_000_000, "warning")` and `HeightLimit("FAN", 12_000_000)`
- **WHEN** it is written with `canonical.dump_dir` and loaded with `canonical.load_dir`
- **THEN** the loaded limits equal the originals, and `rules.json` holds them under `heights` with `FAN` before `LID`

#### Scenario: Files of an older build
- **GIVEN** a `rules.json` written before this change
- **WHEN** it is loaded and written again
- **THEN** `RuleSet.heights == ()` and the written bytes equal the input

#### Scenario: Refused values
- **WHEN** `HeightLimit("LID", 0)`, `HeightLimit("", 1_000_000)` and a `RuleSet` holding two limits on `LID` are built
- **THEN** each raises `ValueError`

#### Scenario: Compatibility is documented
- **WHEN** `uv run pytest tests/unit/model/test_rules.py -k documented` reads `docs/design-model.md`
- **THEN** the section on `heights` holds the sentence that 0.2.x and 0.3.0 cannot read a document that carries the key

### Requirement: Mechanical intent metadata
The model SHALL expose MechanicalIntent with stable key, board frame, integer tolerance, source,
input status (`measured`, `estimated` or `proposed`) and evidence. FootprintInstance.anchor, Hole.intent and Keepout.intent SHALL default
to None, preserving legacy canonical output. Intent MUST NOT change pad nets or create geometry.

#### Scenario: Legacy canonical output
- **GIVEN** a board contains no declared mechanical intent
- **WHEN** its canonical JSON is produced
- **THEN** the new default fields are omitted and existing geometry is unchanged

### Requirement: Board outline arcs
`Outline` SHALL hold `arcs: tuple[OutlineArc, ...]`, empty by default, and `fenolite.model.board.OutlineArc` SHALL be a frozen value with `ring: int`, `edge: int` and `mid: Point`.
- Ring 0 is `Outline.points` and ring k ≥ 1 is `Outline.cutouts[k − 1]`. Edge i of a ring of n vertices joins vertex i to vertex (i + 1) mod n. An `OutlineArc` makes that edge the circular arc from its first vertex through `mid` to its second vertex; every other edge is straight. `points` and `cutouts` keep their meaning: the vertices of each ring, in order.
- `arcs` MUST be sorted by `(ring, edge)` and MUST hold at most one entry per edge; `ring` and `edge` MUST name an edge of the outline; `mid` MUST differ from the edge's two vertices and MUST NOT lie on the line through them. A ring MUST hold three vertices or more, or two when one of its two edges is an arc. An outline that breaks one of these rules is refused by the build (`kicad-file-backend`, "Outline shape checks").
- The canonical writer omits `arcs` when it is empty, so a `board.json` written before this requirement loads unchanged and an outline without arcs keeps its bytes. `tools/gen_schemas.py` MUST regenerate `schemas/fenolite.model.v0/board.json` with `arcs`.
- The other direction does not hold, and MUST be said: release 0.2.x cannot read a model document that carries the key `arcs`, because its reader refuses an unknown key. `docs/design-model.md` and the changelog MUST hold that sentence. The `board.json` that release 0.2.0 wrote, `tests/data/model/v0.2.0/blink_2layer.board.json` ("Graphics and texts of a footprint instance"), MUST still load unchanged and serialise again to its own bytes.

#### Scenario: An outline with an arc round-trips
- **GIVEN** an `Outline` whose `points` are (0, 0), (10 mm, 0), (10 mm, 10 mm) and (0, 10 mm), whose one cut-out has the two vertices (6 mm, 5 mm) and (4 mm, 5 mm), and whose `arcs` are `OutlineArc(0, 1, Point(11_000_000, 5_000_000))`, `OutlineArc(1, 0, Point(5_000_000, 4_000_000))` and `OutlineArc(1, 1, Point(5_000_000, 6_000_000))`
- **WHEN** the design is written with `canonical.dump_dir` and loaded again with `canonical.load_dir`
- **THEN** the loaded outline equals the original, and `board.json` holds the three entries under `arcs` in that order

#### Scenario: Documents without arcs keep their bytes
- **GIVEN** the `.fenolite/board.json` of a blink build made before this change
- **WHEN** it is loaded with `canonical.loads` and dumped again
- **THEN** `board.outline.arcs == ()` and the dumped text equals the loaded one byte for byte

#### Scenario: A document of 0.2.0 still loads
- **GIVEN** `tests/data/model/v0.2.0/blink_2layer.board.json`, whose outline holds no `arcs`
- **WHEN** `uv run pytest tests/unit/model/test_outline_arcs.py -k v020` loads it with `canonical.loads` and dumps it again
- **THEN** the dumped text equals the file byte for byte, and `docs/design-model.md` and `CHANGELOG.md` each hold the sentence that release 0.2.x cannot read a model document that carries `arcs`

#### Scenario: Schemas regenerated
- **WHEN** `uv run python tools/gen_schemas.py --check` runs after this change
- **THEN** it exits 0, and `board.json` defines `arcs` with the integer fields `ring` and `edge` and the point `mid`

### Requirement: Assembly and test pad properties in the model
`Pad` SHALL carry `fab_property: PadFabProperty | None = None`, where `PadFabProperty` (`fenolite.model.board`) is `Literal["bga", "fiducial_global", "fiducial_local", "test_point", "heatsink", "castellated", "mechanical", "press_fit"]`: the fabrication mark of the pad, `None` when it has none.
- The field MUST be the last field of `Pad`, so that every existing construction keeps its meaning.
- The canonical form MUST omit it when it is `None`, so a document without a mark keeps the bytes it has today and a document of an earlier release loads as it is. The other direction does not hold, and MUST be said in `docs/design-model.md` and in the changelog: releases 0.2.x and 0.3.0 cannot read a model document that carries the key `fab_property`, because their reader refuses an unknown key. `schemas/fenolite.model.v0/` MUST list it as an optional property of a pad, for board pads and library pads alike.
- The model MUST NOT check the mark against the pad's kind or layers: the DSL refuses what it can tell at the call ("Assembly and test properties on authored pads"), and KiCad's DRC judges the rest.
- `docs/design-model.md` MUST list the eight values and say that a mark is what KiCad calls the fabrication property of a pad.

#### Scenario: No mark by default
- **WHEN** `Pad(id=..., number="1", shape="rect", size=..., position=...)` is constructed
- **THEN** `fab_property is None`, and the canonical texts of a design that holds the pad have no `fab_property` key

#### Scenario: A test-point pad in board.json
- **GIVEN** a design whose footprint instance holds a pad with `fab_property="test_point"`
- **WHEN** its canonical texts are dumped and loaded again
- **THEN** `board.json` holds `"fab_property": "test_point"` for that pad, and the loaded design equals the first

### Requirement: Stack-up in the board model
`Board.stackup` SHALL describe the board's build-up from its top face to its bottom face: `Stackup.layers` lists, in that order, every layer that its source keeps in a stack-up, and a board whose source states none has `stackup is None`.
- **Entries.** An entry of kind `copper` MUST be named after its copper layer in `Board.layers`. Entries of kind `soldermask`, `silkscreen` and `solderpaste` describe the outer layers and lie above the first copper entry or below the last. Every entry between two copper entries is of kind `dielectric`; a dielectric made of several sheets is one entry per sheet, consecutive, the sheets sharing a name. Silkscreen and paste entries have `thickness` 0.
- **New fields, with defaults.** `StackLayer.dielectric_kind: DielectricKind | None = None`, where `DielectricKind` is `core` or `prepreg` and `None` means not stated; `StackLayer.color: str = ""`, the colour as its source names it; `Stackup.impedance_controlled: bool = False`, true when the dielectric values are requirements for the fabricator. `material`, `epsilon_r` and `loss_tangent` keep their meaning, and `epsilon_r` and `loss_tangent` are plain decimal texts or empty; a `loss_tangent` may be `0`, which KiCad writes for a solder mask.
- The change MUST be additive: `canonical` omits the defaults, a `board.json` written before it MUST load with them, `SCHEMA_VERSION` stays `"0"`, and `schemas/fenolite.model.v0/board.json` MUST be regenerated with `DielectricKind` as a closed vocabulary.
- The other direction does not hold, and MUST be said: release 0.2.x cannot read a model document that carries `dielectric_kind`, `color` or `impedance_controlled`, because its reader refuses an unknown key. `docs/design-model.md` and the changelog MUST hold that sentence. The `board.json` that the code of release 0.2.1 wrote for `examples/blink_2layer`, committed by this change as `tests/data/model/v0.2.1/blink_2layer.board.json` (the 0.2.0 fixture of "Graphics and texts of a footprint instance" belongs to a change that is not on the branch), MUST still load unchanged and serialise again to its own bytes.
- **Helpers.** `Stackup.thickness() -> Nm` MUST return the sum of `thickness` over `layers`; this sum is the board thickness of the model, and the model holds no other. `Stackup.depth(name) -> tuple[Nm, Nm]` MUST return the depths, below the top face of the first entry, of the top face and the bottom face of the first entry of that name; an unknown name MUST raise `KeyError`. `Stackup.between(upper, lower) -> tuple[StackLayer, ...]` MUST return the entries strictly between the first entries named `upper` and `lower`, top to bottom; an unknown name MUST raise `KeyError`, and an `upper` that does not lie above `lower` MUST raise `ValueError`.
- **Findings.** When `Board.stackup` is not `None`, `Design.validate()` MUST report, with `where` set to the stack-up's id:
  - `model.stackup-order` (error): an entry of kind `soldermask`, `silkscreen` or `solderpaste` between two copper entries, or two entries of one such kind on one side; a dielectric entry above the first copper entry or below the last; two neighbouring copper entries with no entry between them; dielectric entries between the same two copper entries with different `dielectric_kind`; a `dielectric_kind` on an entry that is not a dielectric;
  - `model.stackup-copper` (error): no copper entry, or, when `Board.layers` holds copper layers, copper entries whose names, in order, are not the names of those layers in ordinal order;
  - `model.stackup-value` (error): a negative thickness; a copper or dielectric entry of thickness 0; an `epsilon_r` that is neither empty nor a plain decimal above 0, or a `loss_tangent` that is neither empty nor a plain decimal (digits, an optional point and digits, no sign and no exponent; 0 is accepted for a loss tangent).
- `docs/design-model.md` MUST describe the fields, the helpers and the three findings, and `docs/cli-contract.md` MUST list the findings with the other `model.*` codes.

#### Scenario: Old documents still load
- **GIVEN** a `board.json` written before this change whose board holds a stack-up of three entries
- **WHEN** `canonical.loads` reads it into a `Board`
- **THEN** every entry has `dielectric_kind is None` and `color == ""`, and `impedance_controlled is False`

#### Scenario: A document of 0.2.1 still loads
- **GIVEN** `tests/data/model/v0.2.1/blink_2layer.board.json`, which holds none of the three new keys
- **WHEN** `uv run pytest tests/unit/model/test_stackup.py -k v021` loads it with `canonical.loads` and dumps it again
- **THEN** the dumped text equals the file byte for byte, and `docs/design-model.md` and `CHANGELOG.md` each hold the sentence that release 0.2.x cannot read a model document that carries the new keys

#### Scenario: Thickness, depth and the entries between two layers
- **GIVEN** a stack-up of `F.Mask` 10 000 nm, `F.Cu` 35 000, `dielectric 1` (prepreg) 200 000, `In1.Cu` 17 500, `dielectric 2` (core) 1 200 000, `In2.Cu` 17 500, `dielectric 3` (prepreg) 200 000, `B.Cu` 35 000 and `B.Mask` 10 000
- **WHEN** its helpers are called
- **THEN** `thickness() == 1_725_000`, `depth("In1.Cu") == (245_000, 262_500)`, `between("F.Cu", "In1.Cu")` is the one prepreg entry, and `between("In1.Cu", "F.Cu")` raises `ValueError`

#### Scenario: Copper entries out of table order
- **GIVEN** a board whose layers hold `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu`, and whose stack-up lists its copper entries as `F.Cu`, `In2.Cu`, `In1.Cu`, `B.Cu`
- **WHEN** `design.validate()` runs
- **THEN** it reports one `model.stackup-copper` of severity `error` whose `where` is the stack-up's id

#### Scenario: Mixed gap and a bad decimal
- **GIVEN** a two-layer stack-up with a core and then a prepreg between `F.Cu` and `B.Cu`, the core's `epsilon_r` being `"4,5"`
- **WHEN** `design.validate()` runs
- **THEN** it reports one `model.stackup-order` and one `model.stackup-value`, both of severity `error`

#### Scenario: Schema regenerated
- **WHEN** `uv run python tools/gen_schemas.py --check` runs after this change
- **THEN** it exits 0, and `board.json` lists `dielectric_kind` with the values `core` and `prepreg`, `color` and `impedance_controlled`

### Requirement: Rule areas, board items and the area selector in the model
The board and rules layers SHALL carry these additions, each with a default, so that documents written before them still load:
- `Keepout.name: str = ""`, the name of a rule area, which rules use to select the items inside it.
- `Text.h_justify: FieldJustifyH = "center"` and `Text.v_justify: FieldJustifyV = "center"`, with the values of `FootprintField` ("Footprint fields"), given in the reading frame of the text.
- `fenolite.model.board.Dimension`, an entity with `kind: DimensionKind` (`aligned` or `orthogonal`), `layer: str`, `start: Point`, `end: Point`, `offset: Nm` (the signed distance of the dimension line from the measured points), `direction: DimensionDirection | None = None` (`horizontal` or `vertical`, for an `orthogonal` dimension), `units: DimensionUnits = "mm"` (`mm` or `in`), `precision: int = 4`, `size: Size | None = None`, `thickness: Nm | None = None` and `width: Nm | None = None`; `None` means the backend's default. The measured value is not a field: it follows from the points.
- `Board.dimensions: tuple[Dimension, ...] = ()`.
- `SelectorOp` and `LEAF_OPS` include `area`. `RuleSubject.areas: frozenset[str] = frozenset()` holds the names of the rule areas a subject lies in. `Selector("area", v).matches(subject)` MUST be true when a name of `subject.areas` matches `v` with `fnmatch.fnmatchcase`, so letter case counts and `*` is a glob.
- The closed prefix table SHALL include `dim`.
- `tools/gen_schemas.py` MUST regenerate `schemas/fenolite.model.v0/board.json` and `rules.json` with these fields.
- The other direction does not hold, and MUST be said: release 0.2.x cannot read a model document that carries one of the new keys (`name` of a keep-out, `h_justify` and `v_justify` of a board text, `dimensions` of a board) or a selector of the op `area`, because its reader refuses an unknown key and its schema an unknown op. `docs/design-model.md` and the changelog MUST hold that sentence. The `board.json` that release 0.2.0 wrote, `tests/data/model/v0.2.0/blink_2layer.board.json` ("Graphics and texts of a footprint instance"), MUST still load unchanged and serialise again to its own bytes.
- `Text` is also the type of the texts of a footprint instance ("Graphics and texts of a footprint instance"): they gain the two fields with the default `center`, which the canonical writer omits, so no document that holds them changes.

#### Scenario: Old documents still load
- **GIVEN** a `board.json` and a `rules.json` written before this change
- **WHEN** `canonical.loads` reads them
- **THEN** every keep-out has `name == ""`, every text `h_justify == v_justify == "center"`, the board `dimensions == ()`, and every selector loads unchanged

#### Scenario: A document of 0.2.0 still loads
- **GIVEN** `tests/data/model/v0.2.0/blink_2layer.board.json`, which holds none of the new keys
- **WHEN** `uv run pytest tests/unit/model -k v020_board_items` loads it with `canonical.loads` and dumps it again
- **THEN** the dumped text equals the file byte for byte, and `docs/design-model.md` and `CHANGELOG.md` each hold the sentence that release 0.2.x cannot read a model document that carries the new keys

#### Scenario: Area selector against a subject
- **GIVEN** `Selector("area", "H*")` and the subjects `RuleSubject("track", areas=frozenset({"HV"}))`, `RuleSubject("track", areas=frozenset({"hv"}))` and `RuleSubject("track")`
- **WHEN** `matches` is evaluated for each
- **THEN** it gives true, false and false

#### Scenario: Unknown dimension kind rejected by the schema
- **GIVEN** a `board.json` document where `dimensions[0].kind` is `"radial"`
- **WHEN** it is validated against `schemas/fenolite.model.v0/board.json`
- **THEN** validation fails with the JSON pointer of that value

#### Scenario: Dimension prefix
- **WHEN** `derived_id("dim", "dsl", "dimension:width")` is called, and `new_id("dimx", rng)`
- **THEN** the first returns an id that starts with `dim_`, and the second raises `ValueError`

#### Scenario: Schemas regenerated
- **WHEN** `uv run python tools/gen_schemas.py --check` runs after this change
- **THEN** it exits 0, `board.json` lists `dimensions`, `Dimension`, `h_justify` on texts and `name` on keep-outs, and `rules.json` lists `area` among the selector ops

### Requirement: Proximity rules in the model
`fenolite.model.rules` SHALL define `PlacementSeverity = Literal["error", "warning"]` and the frozen value objects `PadSelection(path, number="", index=None)` and `ProximityRule(name, parts, anchor, within, severity="error")`, and `RuleSet` SHALL gain the field `proximity: tuple[ProximityRule, ...]`, empty by default and stored in `rules.json`. This is an addition to the rules layer of "Model layers for v0.1".
- `PadSelection.path` MUST be a non-empty component path; `number` a pad number, empty for every pad of the part; `index` `None` or a non-negative `int`, given only with a `number`. `ProximityRule.parts` and `anchor` MUST be non-empty, and `within` MUST be a positive length in nm. Each value object MUST raise `ValueError` otherwise. `RuleSet` MUST raise `ValueError` for two `ProximityRule`s of one `name`.
- They are value objects, not entities: they carry no id, and a rule's name is its key. `to_model` writes them in name order.
- A proximity rule is not a rule of `RuleSet.rules` and has no `RuleKind`. No backend lowers it: the KiCad writer and `lower_rules` read only `RuleSet.rules`, the Altium rule table (`altium-pcb-writer`, "Rule lowering table") gains no row, and a board read from a file has none.
- `schemas/fenolite.model.v0/rules.json` MUST be regenerated, and `uv run python tools/gen_schemas.py --check` MUST exit 0. A `rules.json` without the key `proximity` MUST load with an empty tuple, and a rule set without proximity rules MUST be written without the key, so a design that declares none writes the bytes it wrote before this change. `SCHEMA_VERSION` stays `"0"`.
- `docs/design-model.md` MUST describe the two value objects and the field, and MUST say that 0.2.x and 0.3.0 cannot read a `rules.json` that carries `proximity`.

#### Scenario: Rules round trip
- **GIVEN** a design whose `RuleSet.proximity` holds `ProximityRule("dec7", (PadSelection("C5", "1"),), (PadSelection("U1", "7"),), 2_000_000)`
- **WHEN** it is written with `canonical.dump_dir` and loaded with `canonical.load_dir`
- **THEN** the loaded rule equals the original, and `rules.json` holds it under `proximity`

#### Scenario: Files of an older build
- **GIVEN** a `rules.json` written before this change
- **WHEN** it is loaded, validated against the regenerated schema and written again
- **THEN** loading succeeds, validation passes, `RuleSet.proximity == ()`, and the written bytes equal the input

#### Scenario: Refused values
- **WHEN** `ProximityRule("r", (), (PadSelection("U1"),), 1)`, `ProximityRule("r", (PadSelection("C1"),), (PadSelection("U1"),), 0)`, `PadSelection("U1", index=0)` and a `RuleSet` holding two rules named `dec7` are built
- **THEN** each raises `ValueError`

#### Scenario: Compatibility is documented
- **WHEN** `uv run pytest tests/unit/model/test_rules.py -k documented` reads `docs/design-model.md`
- **THEN** the section on `proximity` holds the sentence that 0.2.x and 0.3.0 cannot read a document that carries the key

### Requirement: Differential pairs in the model
The model SHALL hold a differential pair as an `Interface` whose kind is a key of `fenolite.model.pairs.PAIR_ROLES`, and `fenolite.model.pairs` SHALL define the name rule by which two nets form a pair (`H-K-DIFFPAIR-NAMES-2`). Rules, checks, the build and the backends MUST use this module, and no other pair entity MUST exist.
- **Roles.** `PAIR_ROLES` MUST map `diff_pair` to `("p", "n")` and `usb2` to `("dp", "dn")`, the positive role first. `pair_nets(interface)` MUST return the ids of the positive and the negative net of an interface of one of those kinds, and `None` for another kind or a missing role.
- **Name rule.** `split_pair_name(name)` MUST return `PairName(base, polarity, tail)` when the name, without its longest trailing run of digits and `_` (the tail, possibly empty), ends with `P`, `N`, `+` or `-` (the polarity), `base` being the text before the polarity; otherwise it MUST return `None`. `coupled_name(name)` MUST return the base, the other polarity (`P` for `N`, `+` for `-`, and back) and the tail, or `None`. `pair_base(positive, negative)` MUST return the base when the polarity of `positive` is `P` or `+` and `negative == coupled_name(positive)`, and `None` otherwise. Letter case counts throughout.
- **Bases of a design.** `net_bases(names)` MUST map each name of `names` whose coupled name is also in `names` to its base.
- **Class values.** `NetClass` MUST gain `diff_pair_width`, `diff_pair_gap` and `diff_pair_via_gap`, each a length in nm or `None` (the default), stored in `circuit.json`. A `circuit.json` written before these fields existed MUST load with all three `None`.
- **Rules.** `RuleKind` MUST gain `diff_pair_gap`, `diff_pair_uncoupled`, `skew`, `diff_pair_skew` and `length`. `SelectorOp` and `LEAF_OPS` MUST gain `diff_pair`, a leaf whose value is a pair base, which MAY hold `*`. `RuleSubject` MUST gain `diff_pair: str | None`, the base of the subject's net when the design holds the coupled net, `None` by default.
- **Matching.** `Selector("diff_pair", v).matches(subject)` MUST be true exactly when `subject.diff_pair` is not `None` and matches `v` as a glob with its letter case, or ends with `_` and matches `v` without that `_`.
- `schemas/fenolite.model.v0/circuit.json` and `rules.json` MUST be regenerated, and `uv run python tools/gen_schemas.py --check` MUST exit 0.

#### Scenario: Names that pair
- **WHEN** `pair_base` is called on (`USB_P`, `USB_N`), (`USB+`, `USB-`), (`USB_DP`, `USB_DN`), (`D_P0`, `D_N0`), (`D_P_2`, `D_N_2`) and (`DP1`, `DN1`)
- **THEN** it returns `USB_`, `USB`, `USB_D`, `D_`, `D_` and `D`

#### Scenario: Names that do not pair
- **WHEN** `pair_base` is called on (`USB_DP`, `USB_DM`), (`USB_p`, `USB_n`), (`USB_P`, `USB-`), (`D_P1`, `D_N2`), (`D_PA`, `D_NA`) and (`USB_N`, `USB_P`)
- **THEN** it returns `None` each time, and `coupled_name("USB_DP")` is `USB_DN`

#### Scenario: Nets of a USB interface
- **GIVEN** an `Interface` of kind `usb2` with the members `dp`, `dn`, `vbus` and `gnd`, and one of kind `i2c`
- **WHEN** `pair_nets` is called on each
- **THEN** the first gives the ids of the `dp` and `dn` nets in this order, and the second `None`

#### Scenario: Pair leaf matches by base
- **GIVEN** three subjects whose `diff_pair` is `USB_`, `usb_` and `None`
- **WHEN** `Selector("diff_pair", "USB")`, `Selector("diff_pair", "USB_")` and `Selector("diff_pair", "*")` are matched against each
- **THEN** the first two match only the subject `USB_`, and the third matches `USB_` and `usb_` and not the subject without a pair

#### Scenario: Older circuit document loads
- **GIVEN** a `circuit.json` written before this change, whose class `HV` has no pair key
- **WHEN** it is loaded with `canonical.loads` and validated against the regenerated schema
- **THEN** loading succeeds, validation passes, and the three pair values of `HV` are `None`
