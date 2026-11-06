## MODIFIED Requirements

### Requirement: Tracks from intents
`resolve_copper` SHALL turn each track intent (`key`, `path`, `layer`, `width`, `net`) into tracks, arcs and vias along its path.
- A path element MUST be a pad end (`component`, `number`, `index`), a point, a via step (`at`, `layer`, `diameter`, `drill`, `kind`) or an arc step (`mid`, `end`). A path with fewer than two elements or starting with a via step or an arc step, or a key used by an earlier intent, MUST give `kicad.copper.bad-intent` (error).
- The point of a pad end MUST be the `position` of the chosen pad (`board-frame`, "Board-frame pads"), and the point of an arc step its `end`.
- The current layer starts as the intent's `layer`. For each element `i` but the last, one item MUST be created from the point of element `i` to the point of element `i + 1` on the current layer, after the layer change of element `i` when it is a via step: an `Arc` when element `i + 1` is an arc step ("Arcs" below), a `Track` otherwise. A segment whose two points are equal MUST NOT be created, and its locator stays unused. A via step MUST create one via at its point, of its kind and with its layers ("Via kinds" below), and MUST set the current layer to its `layer`.
- **Pad choice.** A pad end may stand anywhere in the path, so a track can chain several pads. Its candidates MUST be the pads that `find_pads(design, component, number)` returns that have a copper entry on the layer of every segment or arc touching that end. With `index`, the `index`-th of all matches MUST be used. Without it, pad ends MUST be chosen in path order: the first element takes the candidate nearest to the point of the second element, or the nearest pair when the second element is a pad end without `index`; every other pad end takes the candidate nearest to the point of the element before it. Distances are exact squared distances, with ties to the earlier pads.
- **Layers.** `layer` and every via step's `layer` MUST be copper layers of the board and every via step MUST change the layer, else `kicad.copper.bad-layer`; the two layers of a via step MUST also fit its kind ("Via kinds" below), with the same code. A pad end without a candidate MUST give `kicad.copper.layer-mismatch`; a component or number that `find_pads` cannot match, or an `index` beyond the matches, `kicad.copper.pad-not-found` (errors).
- **Sizes.** The width MUST be the intent's `width`, else the `track_width` of the class of the track's net; a via step's sizes its `diameter` and `drill`, else the class's `via_diameter` and `via_drill`. A missing size MUST give `kicad.copper.size-missing`, and a size that is not positive or a drill larger than its diameter `kicad.copper.bad-size` (errors). A drill equal to the diameter MUST be accepted: a via without a ring, which a source document can hold (change c0426).
- An intent with an error MUST create nothing; the next intents are still resolved. Created tracks, arcs and vias MUST follow the path order, and intents their given order.
- **Arcs.** The item that ends at an arc step MUST be one `Arc` on the current layer, with the width and the net of the intent, from the point of the element before the step through the step's `mid` to its `end`, with the locator `arc[i]`, `i` being the index of the arc step. Its three points MUST be distinct and MUST NOT lie on one line, decided exactly with integers; otherwise the intent gives `kicad.copper.bad-intent`.
- **Via kinds.** The kind of a via step is its `kind`: `through` (also when the step has none), `blind`, `buried` or `micro`; any other value gives `kicad.copper.bad-intent`. A `through` via MUST have the first and last copper layers of the board as its `layers`, as before. Any other kind MUST have the current layer and the step's `layer`, in stack order, and they MUST fit the kind: for `blind`, exactly one of the two is the first or the last copper layer; for `buried`, neither is; for `micro`, exactly one is, and the two are next to each other in the stack. `Via.via_type` MUST be the kind. Whether a target can hold a kind is the board writer's rule (`kicad-file-backend`, "Lossy writes are refused unless allowed"): a `buried` via needs target 10.

#### Scenario: Pad to pad through a via step
- **GIVEN** the blink built for target 10, and the intent `led_a` from `R1` pad `2` through a point `P` and a via step at `Q` to `B.Cu`, ending at `D1` pad `2`, on `F.Cu` with width 0.3 mm and via sizes 0.6 mm and 0.3 mm
- **WHEN** `resolve_copper(design, [intent])` runs
- **THEN** the design gains the tracks `R1.2`–`P` and `P`–`Q` on `F.Cu` and `Q`–`D1.2` on `B.Cu`, one through via at `Q`, all on `LED_A`, with the uuids `copper_uuid("led_a", "seg[0]")`, `seg[1]`, `seg[2]` and `via[2]`

#### Scenario: Shared number, nearest pad
- **GIVEN** `Mini_Edge_Cases` placed at (0, 0) for `J1`, both pads `1` on net `GND`, and a track intent from `J1` pad `1` to the point (5 mm, 0) on `F.Cu`
- **WHEN** it is resolved, and again with `index=0`
- **THEN** the first track starts at (2 mm, 0) and the second at (−2 mm, 0)

#### Scenario: Pad without copper on the layer
- **GIVEN** the blink and a track intent from `R1` pad `1` (an `smd` pad on `F.Cu`) to a point, on `B.Cu`
- **WHEN** it is resolved with `issues=found`
- **THEN** no item is created and `found` holds one `kicad.copper.layer-mismatch` naming `R1`, pad `1` and `B.Cu`

#### Scenario: Width from the net class
- **GIVEN** the blink, whose class `PWR` sets `track_width` 0.5 mm for `GND`, a track intent on `GND` without width, and a track intent on `LED_A` without width
- **WHEN** they are resolved with `issues=found`
- **THEN** the `GND` tracks have width 0.5 mm, the `LED_A` intent creates nothing, and `found` holds one `kicad.copper.size-missing` naming its key

#### Scenario: Arc between two points
- **GIVEN** the blink built for target 10, and the intent `bend` on `GND` (named by `net`), on `F.Cu` with width 0.25 mm, whose path is the point `P`, an arc step with `mid` `M` and `end` `E`, and the point `Q`, the three points `P`, `M` and `E` not on one line
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_copper_tracks.py -k arc` resolves it
- **THEN** the design gains one arc from `P` through `M` to `E` with the uuid `copper_uuid("bend", "arc[1]")` and one track from `E` to `Q` with the uuid `copper_uuid("bend", "seg[1]")`, both on `GND` and `F.Cu`, and no item with the locator `seg[0]`

#### Scenario: Arc on one line
- **GIVEN** the same intent with `M` on the line from `P` to `E`
- **WHEN** it is resolved with `issues=found`
- **THEN** nothing is created, and `found` holds one `kicad.copper.bad-intent` naming `bend` and the arc step

#### Scenario: Blind via step on four copper layers
- **GIVEN** a design with the copper layers `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu` (`tests/_boards.py::created_board(4)`), and a track intent on `F.Cu` whose path is a point, a via step with `kind="blind"` to `In1.Cu`, and a point
- **WHEN** it is resolved
- **THEN** the via has `via_type == "blind"` and the layers `F.Cu` and `In1.Cu`, the first track is on `F.Cu` and the second on `In1.Cu`

#### Scenario: Layers that do not fit the kind
- **GIVEN** the same design
- **WHEN** an intent with a via step `kind="buried"` from `F.Cu` to `In1.Cu`, one with `kind="micro"` from `F.Cu` to `In2.Cu`, and, on a two-layer board, one with `kind="blind"` from `F.Cu` to `B.Cu` are resolved with `issues=found`
- **THEN** each creates nothing, and `found` holds one `kicad.copper.bad-layer` per intent, naming its key and its kind

#### Scenario: A via without a ring
- **GIVEN** the blink and a via intent whose drill equals its diameter, 0.6 mm, and another whose drill is 0.7 mm
- **WHEN** they are resolved with `issues=found`
- **THEN** the first creates one via of diameter and drill 0.6 mm, and the second creates nothing and gives `kicad.copper.bad-size` naming a drill larger than the diameter

### Requirement: Copper issue codes
`copper` SHALL report its findings only with the codes of the closed table `COPPER_ISSUE_CODES`. They are `kicad.*` codes, so they pass through the closed sets of `lens.build.BUILD_ISSUE_CODES` (c0011) and `lens.preserve.PRESERVE_ISSUE_CODES` (c0019) unchanged, as `design-dsl` "Build issue codes" and `layout-lens` "Layout issue codes" allow.

| code | severity | when |
|---|---|---|
| `kicad.copper.bad-intent` | error | a path, region, pitch, margin, key or via kind is malformed, a key repeats, or the three points of an arc are not distinct or lie on one line |
| `kicad.copper.pad-not-found` | error | no footprint, no pad with the number, or an index beyond the matches |
| `kicad.copper.layer-mismatch` | error | no pad of a pad end has copper on the segment's layer |
| `kicad.copper.bad-layer` | error | a layer is not a copper layer of the board, a via step keeps the layer, or the layers of a via do not fit its kind |
| `kicad.copper.net-conflict` | error | pad ends on two nets or without a net, or a named net that differs from theirs |
| `kicad.copper.unknown-net` | error | a named net is not a net of the design |
| `kicad.copper.no-net` | error | a track without a pad end names no net |
| `kicad.copper.size-missing` | error | a width, via size or clearance is neither given nor set by the net's class |
| `kicad.copper.bad-size` | error | a size is not positive, or a drill is larger than its diameter |
| `kicad.copper.stale` | warning | script copper of an earlier build has no intent any more and is removed |
| `kicad.copper.end-unplaced` | warning | an intent ends at a staged part and creates nothing |
| `kicad.copper.stitch-empty` | warning | a stitch intent keeps no candidate |
| `kicad.copper.regenerated` | info | script copper differs from its regenerated copy (edited in KiCad, or its pads moved) and is replaced |
| `kicad.copper.duplicate` | info | an item equal to script copper is removed |
| `kicad.copper.stitch-skipped` | info | stitch candidates are dropped for clearance (with the count) |

#### Scenario: Closed set enforced
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_copper_issues.py -k closed_set` collects every issue code produced by the copper tests
- **THEN** each is a key of `COPPER_ISSUE_CODES` with the severity of this table, and every key is produced by at least one test
