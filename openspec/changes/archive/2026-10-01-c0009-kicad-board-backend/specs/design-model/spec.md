## ADDED Requirements

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
