## ADDED Requirements

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
The board layer SHALL describe a pad's hole and its copper offsets in `Padstack`, with fields that all have defaults, so that documents written before them still load.
- `Padstack.hole_shape: HoleShape = "round"`, one of `round`, `square` and `slot`.
- `Padstack.hole_length: Nm | None = None`: the length of a slot along its axis, ends included. `Pad.drill` stays the hole's size: the diameter of a round hole, the side of a square hole and the width of a slot.
- `Padstack.hole_rotation: Udeg = 0`: the angle of the hole's axis relative to the footprint.
- `PadstackLayer.offset: Point = Point(0, 0)`: where the copper's centre lies on that layer relative to `Pad.position`, the centre of the hole, in the footprint frame.
- `Padstack.layers` MAY be empty: a pad with one shape on all its layers and a hole that is not round has a padstack without layer entries. `Pad.padstack is None` MUST still mean one shape on all layers, a round hole or no hole, and no offset.
- In a library definition, `PadstackLayer.layer` MAY be the wildcard `In*.Cu`, every inner copper layer, as `Pad.layers` of a definition may hold `*.Cu`. On a board it MUST be a real layer.
- `tools/gen_schemas.py` MUST regenerate `schemas/fenolite.model.v0/board.json` and `library.json` with the new fields and the closed vocabulary of `hole_shape`.
- No reader or writer of the KiCad backend changes: a KiCad oval or offset drill stays in the pad's opaque slots, as today.

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
- `ComponentBody` MUST carry the common entity header and: `kind: BodyKind` (`extruded` or `model`); `height: Nm`, the distance from the board surface to the top of the body; `standoff: Nm = 0`, the distance from the board surface to its underside; `outline: tuple[Point, ...] = ()`, ordered, the body's footprint as a polygon in the footprint frame of "Board entities read from file backends" (empty when the source gives none); `layer: str = ""`, the layer the body is drawn on; `model: str = ""`, the name of a 3D model for the kind `model`; and `name: str = ""`.
- A body states a volume above the side the footprint is placed on. It carries no model data: `FootprintDef.models` keeps its meaning (the model references of a definition), and no file is embedded.
- The height of a part is the largest `height` of its bodies; a part without bodies has no known height.
- The closed prefix table SHALL include `bdy`.
- `Design.validate()` MUST report `model.body-height` (error), with `where` set to the body's id, for a body whose `height` is below its `standoff` or whose `standoff` is negative.
- No reader or writer of the KiCad backend changes: definitions read from KiCad files hold no body, so a placed copy has none, and a KiCad build MUST keep the bodies of a design in `.fenolite/` only.
- `tools/gen_schemas.py` MUST regenerate `board.json` and `library.json` with `ComponentBody` and `bodies`. `docs/design-model.md` MUST describe the entity, and `docs/cli-contract.md` MUST list `model.body-height`.

#### Scenario: Old documents still load
- **GIVEN** a `board.json` and a `library.json` written before this change
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
