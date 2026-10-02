## MODIFIED Requirements

### Requirement: Footprint embedding
`fenolite.backends.kicad.embed.place_footprint(defn, *, component, at, rotation=0, side="top", locked=False, key, copper=("F.Cu", "B.Cu"))` SHALL return a `FootprintInstance` for `defn` placed at `at` with stored angle `rotation` on `side`:
- It MUST call `versions.require_editable` on the definition's source format first.
- It MUST emit the definition with `_fpmap.emit_footprint`, drop the children `version`, `generator` and `generator_version`, name the footprint `defn.lib_id`, set its layer to `F.Cu` (top) or `B.Cu` (bottom), and set the value atoms of Reference and Value from `component`.
- Every KiCad uuid MUST be `embed.placement_uuid(key, locator)`, which is `uuid5(FENOLITE_NS, f"kicad-place:{key}:{locator}")`, with `locator` the bare locator of the node in the emitted definition (`/footprint` for the footprint itself).
- The instance MUST be mapped by c0009's board-footprint mapping, so its pads, slots and ids equal those `read_board` gives for the written board. `component_id` MUST be `component.id`, `lib_ref` MUST be `defn.lib_id`, `attributes` MUST hold `defn.kind` (unless `unspecified`) followed by `defn.flags`, and every pad MUST have `net_id = None`.
- `copper` MUST name the copper layers of the board that will hold the instance, in the order of its layer table. Every `*.Cu` pad layer MUST expand to exactly those names, in that order, as `read_board` expands it on that board. The default fits a two-layer board; a caller placing on a board with inner copper layers MUST pass their names (c0011's build passes those of `layers.created_layers(copper)`).
- On the bottom side, `layers.flip_layer` MUST be applied to every `layer` and `layers` atom; every node headed in `embed.MIRROR_HEADS` MUST have its Y negated; the angle of every child `at` MUST become (−φ) mod 360° before being made absolute; and the `justify` of every text on a flipped layer MUST toggle `mirror`. A node whose head is in `embed.FLIP_UNSUPPORTED` MUST make `place_footprint` raise `LossyWriteError` with `droppable == False` and one `kicad.board.flip-unsupported` issue per such node, naming its locator; no instance is returned. On the top side such nodes are copied unchanged.
- On both sides, child angles MUST be stored absolute through c0009's `pad_angle_to_board`.
- `embed.footprint_extent(defn)` MUST return the box of the modelled `F.CrtYd` graphics, else the union of the pad boxes, else `BBox(0, 0, 0, 0)`.

#### Scenario: Top placement of the mini resistor
- **GIVEN** `Mini_R_0603` read from `tests/data/libs/Mini.pretty` and a component `R1` with value `1k`
- **WHEN** `place_footprint(defn, component=r1, at=Point(10_000_000, 10_000_000), key="R1")` is called and the instance is written
- **THEN** the footprint is named `"Mini:Mini_R_0603"`, has layer `F.Cu`, holds no `version` child, its Reference value is `"R1"` and its Value value is `"1k"`

#### Scenario: Uuids from the key
- **GIVEN** the same definition placed twice with keys `R1` and `R2`
- **WHEN** the two instances are compared
- **THEN** no uuid and no id is shared, and placing again with key `R1` reproduces every uuid and id of the first instance

#### Scenario: Bottom placement mirrors the children
- **GIVEN** `Mini_QFP-32_7x7mm_P0.8mm` read from `Mini.pretty`, whose pad `"1"` sits at (−4.15 mm, −2.8 mm) with angle 0 and pad `"9"` has angle 90°
- **WHEN** it is placed with `side="bottom"` and `rotation=30_000_000`
- **THEN** pad `"1"` of the instance has `position == Point(-4_150_000, 2_800_000)` and layers starting with `B.Cu`, pad `"9"` of the instance has `rotation == 270_000_000` (the mirrored library angle, relative to the footprint), the written text stores pad `"9"` as `(at -2.8 -4.15 300)` (−90° + 30°, absolute), and the footprint layer is `B.Cu`

#### Scenario: Unsupported geometry on the bottom
- **GIVEN** a definition read from a copy of `Mini_R_0603`, built in the test, whose pad `"1"` is a `trapezoid` pad holding `(rect_delta 0 0.1)`
- **WHEN** it is placed with `side="bottom"`, then with `side="top"`
- **THEN** the bottom placement raises `LossyWriteError` with `droppable == False` and one issue `kicad.board.flip-unsupported` whose `where` locates the `rect_delta` node, and the top placement returns an instance whose pad keeps `rect_delta` unchanged

#### Scenario: Future definition refused
- **GIVEN** a definition read from a footprint file with header `20990101`
- **WHEN** `place_footprint` is called
- **THEN** `FutureFormatError` is raised

#### Scenario: Courtyard extent
- **GIVEN** `Mini_R_0603`, whose courtyard is an `fp_rect` on `F.CrtYd`
- **WHEN** `footprint_extent(defn)` is called
- **THEN** the result equals the box of that rectangle

#### Scenario: Wildcard pads on a four-layer board
- **GIVEN** `Mini_LED_THT_3mm` read from `tests/data/libs/Mini_v9.pretty`, whose pad `"1"` has layers `*.Cu` and `*.Mask`, and a board made in the test with `layers.created_layers(4)`
- **WHEN** it is placed with `key="D1"` and `copper=("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")`, the board holding it is written for target 10, and the text is read with `read_board`
- **THEN** pad `"1"` of the instance and pad `"1"` of the read-back footprint both have layers `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu`, `F.Mask` and `B.Mask`, in that order, and the written pad keeps `(layers "*.Cu" "*.Mask")`

#### Scenario: Default copper on a four-layer board is refused
- **GIVEN** the same definition placed with `key="D1"` and the default `copper`, on the same four-layer board
- **WHEN** the board is written for target 10
- **THEN** `write_board` raises `LossyWriteError` with `droppable == False` and one `kicad.board.projection-read-only` issue per wildcard pad ("Projected fields on write"), and no text is returned

## ADDED Requirements

### Requirement: Path property on placed footprints
`fenolite.backends.kicad.embed.with_property(defn, *, name, value) -> FootprintDef` SHALL return a copy of the footprint definition `defn` with one hidden property added, and `embed.PATH_PROPERTY` SHALL be `"fenolite.path"`.
- The new property MUST be appended after the last `property` child of the definition, in the form `(property "<name>" "<value>" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid U) (effects (font (size 1 1) (thickness 0.15))))`, the form of the `Datasheet` property of the `Mini_v9` footprints and of boards written by 10.0.6 (S-0058). `U` is replaced by `place_footprint`.
- The entry `name -> value` MUST be added to the copy's `FootprintDef.properties`, and `defn` MUST stay unchanged.
- Every token of the property MUST be an 8.0-floor name, so the emit check of `kicad-version-gating` passes for targets 9 and 10.
- `place_footprint` needs no change for the property: it MUST give the new node a uuid from the key and its locator, and on the bottom side flip its layer to `B.Fab`, as for every other child.
- Locator indices count earlier siblings with the same head (`kicad-sexpr`), so appending the property MUST NOT change the locator or the placement uuid of any other node of the copy.
- `read_board` MUST project the property into `Component.properties["fenolite.path"]`, through c0009's footprint mapping.
- The build writes the component path as the value on every built footprint while `H-K-BUILD-PATHPROP` holds. If a `build-pathprop-t9` or `build-pathprop-t10` probe refutes `H-K-BUILD-PATHPROP`, the build MUST write no such property, and c0019 matches by uuid only.

#### Scenario: Property appended last
- **GIVEN** `Mini_R_0603` read from `tests/data/libs/Mini_v9.pretty`
- **WHEN** `with_property(defn, name=PATH_PROPERTY, value="power/R1")` is placed with key `power/R1` and written for target 10
- **THEN** the footprint's last `property` child is `fenolite.path` with value `"power/R1"`, layer `F.Fab` and `(hide yes)`, and `read_board` of the text gives `properties["fenolite.path"] == "power/R1"`

#### Scenario: No other uuid moves
- **GIVEN** the same definition placed with key `R1`, once plain and once through `with_property`
- **WHEN** the uuids of every node other than the new property are compared
- **THEN** they are equal

#### Scenario: Bottom side
- **GIVEN** the definition with the property added
- **WHEN** it is placed with `side="bottom"`
- **THEN** the property node has layer `B.Fab` and keeps `(hide yes)`

#### Scenario: Emit check is clean on both targets
- **GIVEN** a board made in the test with `layers.created_layers(2)` that holds `Mini_R_0603`, `Mini_LED_THT_3mm` and `Mini_QFP-32_7x7mm_P0.8mm` from `tests/data/libs/Mini_v9.pretty`, each placed through `with_property` and `place_footprint`, `D1` on the bottom side
- **WHEN** the board node that `write_board` emits for target 9, and the one for target 10, is checked with `versions.check_emittable` for the same target
- **THEN** both calls return no issue
