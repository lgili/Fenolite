## ADDED Requirements

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

## MODIFIED Requirements

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
