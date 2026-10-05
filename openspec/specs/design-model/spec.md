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
| rule | `rul` | `rule:<rule kind>` for a board minimum, `rule:<rule kind>:<class name>` for a class minimum |

- Footprints and pads placed by a build MUST follow the third case, with the component path as the key.
- Tracks and vias created from copper intents, by a build or by any other caller, MUST follow the fifth case.
- Every key names its object by a name or a path, never by a position in a list, so inserting, removing or reordering one object MUST NOT change the id of any other object, nor any KiCad uuid derived from those ids.
- The values of `--seed` and `PYTHONHASHSEED` MUST NOT change any id of the fourth case.

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
