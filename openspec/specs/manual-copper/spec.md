# manual-copper Specification

## Purpose
Turn copper intents (tracks from pad to pad, single vias, stitching vias) into tracks and vias of a KiCad design after placement, with nets inferred and checked and ids derived from the caller's keys, and regenerate that script copper on every build so that it follows its pads and disappears with its intent.

## Requirements

### Requirement: Copper module
The module `fenolite.backends.kicad.copper` SHALL resolve copper intents into tracks, arcs and vias of a KiCad design and SHALL merge script copper with existing copper, and MUST import only the standard library, `core`, `model`, `geometry`, `backends.base` and modules of `backends.kicad` (`package-layering`), never `fenolite.dsl`.
- Public names: `COPPER_MARKER`, `copper_uuid`, `is_copper_uuid`, `PadEndLike`, `ViaStepLike`, `ArcStepLike`, `TrackIntentLike`, `ViaIntentLike`, `StitchIntentLike`, `CopperIntentLike`, `resolve_copper`, `merge_copper`, `CopperMerge`, `COPPER_ISSUE_CODES` and `EVIDENCE`. `fenolite.backends.kicad` MUST re-export `resolve_copper`.
- Intents MUST be read by attribute through the structural protocols, so the DSL's frozen dataclasses (`design-dsl`, "Copper intents in the DSL") and any object with the same attributes are accepted. An intent with `path` is a track, one with `pitch` a stitch, and any other a via. A `Point` element of a path is a point; any other element is read as a pad end when it has `component`, as an arc step when it has `mid`, else as a via step. A via step or a via intent without `kind` is a `through` via, and a via intent without `layers` names none, so the intents of earlier scripts and tests keep their meaning.
- `resolve_copper(design, intents, *, unplaced=(), issues=None) -> Design` and `merge_copper(existing, built) -> CopperMerge` MUST be pure: they read no file and no environment variable, and return new values without changing their arguments.

#### Scenario: Import edges
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes with no `ALLOWED` change, and `src/fenolite/backends/kicad/copper.py` does not import `fenolite.dsl`

#### Scenario: Pure resolution
- **GIVEN** the blink built for target 10 and the intents of `examples/blink_routed/design.py`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_copper_tracks.py -k pure` resolves them twice
- **THEN** the two results are equal and the input design's canonical texts are unchanged

### Requirement: Copper uuids and ids
Every track, arc and via that `resolve_copper` creates SHALL carry the KiCad uuid `copper_uuid(key, locator)` in `native_ids["kicad"]` and the id that "Identifier derivation" gives an imported object with that native id: `derived_id("trk", "kicad", uuid)`, `derived_id("arc", "kicad", uuid)` or `derived_id("via", "kicad", uuid)`, with `provenance` `None`.
- `copper_uuid(key, locator)` MUST be the RFC 9562 version-8 uuid (S-0110) whose 48-bit `custom_a` field is `COPPER_MARKER = 0x66656E6F6C69`, whose version is 8 and variant `0b10`, and whose other 74 bits are the first 74 bits of the SHA-256 of the UTF-8 text `kicad-copper:<key>:<locator>`, written in the canonical lower-case 36-character form, which starts with `66656e6f-6c69-8`. Because Python's `uuid.UUID` accepts `version` only up to 5 before 3.14 (S-0111), the version and variant bits MUST be set on the integer.
- `is_copper_uuid(text)` MUST be true exactly for canonical uuid texts with that marker, version 8 and variant `0b10`.
- Locators: `seg[i]` for the segment that leaves path element `i` of a track; `arc[i]` for the arc of the arc step at path element `i`; `via[i]` for the via step at path element `i`; `via` for a single via; `via[k]` for the `k`-th via of a stitch along a polyline; `via[i,j]` for the stitch via at grid indices `(i, j)` of a region.
- The same key and locator MUST give the same uuid and ids whatever the seed, `PYTHONHASHSEED` and the other intents, and two keys MUST share no uuid.

#### Scenario: Marker and determinism
- **WHEN** `copper_uuid("gnd_main", "seg[0]")` is computed in two processes with `PYTHONHASHSEED=1` and `PYTHONHASHSEED=2`
- **THEN** both values are equal, start with `66656e6f-6c69-8`, satisfy `is_copper_uuid`, and give `uuid.UUID(value).version == 8` and `variant == uuid.RFC_4122`

#### Scenario: Other uuids are not copper uuids
- **WHEN** `is_copper_uuid` is called with a version-4 uuid, with `embed.placement_uuid("R1", "/footprint")` and with `66656e6f-6c69-4000-8000-000000000000`
- **THEN** it returns `False` each time

#### Scenario: Ids survive a write and a read
- **GIVEN** the blink built for target 10 with the intents of `examples/blink_routed/design.py` resolved
- **WHEN** the design is written with `write_board` and the text is read with `read_board`
- **THEN** every track and via of the read design has the id and native id of its created item

#### Scenario: Arc ids survive a write and a read
- **GIVEN** the blink built for target 10 and a track intent `bend` whose path holds an arc step at element 1, resolved
- **WHEN** the design is written with `write_board` and the text is read with `read_board`
- **THEN** the read design holds one arc with the native id `copper_uuid("bend", "arc[1]")` and the id `derived_id("arc", "kicad", <that uuid>)`

### Requirement: Tracks from intents
`resolve_copper` SHALL turn each track intent (`key`, `path`, `layer`, `width`, `net`) into tracks, arcs and vias along its path.
- A path element MUST be a pad end (`component`, `number`, `index`), a point, a via step (`at`, `layer`, `diameter`, `drill`, `kind`) or an arc step (`mid`, `end`). A path with fewer than two elements or starting with a via step or an arc step, or a key used by an earlier intent, MUST give `kicad.copper.bad-intent` (error).
- The point of a pad end MUST be the `position` of the chosen pad (`board-frame`, "Board-frame pads"), and the point of an arc step its `end`.
- The current layer starts as the intent's `layer`. For each element `i` but the last, one item MUST be created from the point of element `i` to the point of element `i + 1` on the current layer, after the layer change of element `i` when it is a via step: an `Arc` when element `i + 1` is an arc step ("Arcs" below), a `Track` otherwise. A segment whose two points are equal MUST NOT be created, and its locator stays unused. A via step MUST create one via at its point, of its kind and with its layers ("Via kinds" below), and MUST set the current layer to its `layer`.
- **Pad choice.** A pad end may stand anywhere in the path, so a track can chain several pads. Its candidates MUST be the pads that `find_pads(design, component, number)` returns that have a copper entry on the layer of every segment or arc touching that end. With `index`, the `index`-th of all matches MUST be used. Without it, pad ends MUST be chosen in path order: the first element takes the candidate nearest to the point of the second element, or the nearest pair when the second element is a pad end without `index`; every other pad end takes the candidate nearest to the point of the element before it. Distances are exact squared distances, with ties to the earlier pads.
- **Layers.** `layer` and every via step's `layer` MUST be copper layers of the board and every via step MUST change the layer, else `kicad.copper.bad-layer`; the two layers of a via step MUST also fit its kind ("Via kinds" below), with the same code. A pad end without a candidate MUST give `kicad.copper.layer-mismatch`; a component or number that `find_pads` cannot match, or an `index` beyond the matches, `kicad.copper.pad-not-found` (errors).
- **Sizes.** The width MUST be the intent's `width`, else the `track_width` of the class of the track's net; a via step's sizes its `diameter` and `drill`, else the class's `via_diameter` and `via_drill`. A missing size MUST give `kicad.copper.size-missing`, and a size that is not positive or a drill not smaller than its diameter `kicad.copper.bad-size` (errors).
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

### Requirement: Nets of script copper
Every item that `resolve_copper` creates SHALL carry one net of the design, inferred from the pads that it joins and checked against them.
- The net of a track intent MUST be the net of its pad ends. A pad end whose pad has no net, or pad ends on two nets, MUST give `kicad.copper.net-conflict` (error).
- An explicit `net` MUST name a net of the design, else `kicad.copper.unknown-net`, and MUST equal the net of the pad ends when the path has any, else `kicad.copper.net-conflict`. A track without a pad end MUST name its net, else `kicad.copper.no-net` (errors).
- Via and stitch intents MUST name their net, with the same checks.
- When `unplaced` names the component of a pad end, by component path or reference, the intent MUST create nothing and give `kicad.copper.end-unplaced` (warning): that part sits in the build's staging row.

#### Scenario: Net inferred
- **GIVEN** the blink and a track intent from `R1` pad `2` to `D1` pad `2` without `net`
- **WHEN** it is resolved
- **THEN** every created item carries the id of `LED_A`

#### Scenario: Two nets joined
- **GIVEN** the blink and a track intent from `R1` pad `1` (`LED_DRV`) to `D1` pad `2` (`LED_A`)
- **WHEN** it is resolved with `issues=found`
- **THEN** nothing is created and `found` holds `kicad.copper.net-conflict` naming both pads and both nets

#### Scenario: End at a staged part
- **GIVEN** the blink and a track intent ending at `D1` pad `2`
- **WHEN** it is resolved with `unplaced=("D1",)` and `issues=found`
- **THEN** nothing is created and `found` holds one `kicad.copper.end-unplaced` warning naming `D1`

### Requirement: Single vias
`resolve_copper` SHALL turn each via intent (`key`, `at`, `net`, `diameter`, `drill`, `kind`, `layers`) into one via at `at` on its net, with the locator `via`, the size rules of "Tracks from intents" and the net rules of "Nets of script copper".
- Its kind is the intent's `kind`, `through` when the intent has none. A `through` via spans the first and last copper layers of the board, and its `layers` MUST be `None`.
- Any other kind MUST name two different copper layers of the board in `layers`. They are stored in stack order and MUST fit the kind as "Tracks from intents" defines. A missing, repeated or unknown layer, a pair that does not fit, or `layers` given for a `through` via MUST give `kicad.copper.bad-layer` (error), and the intent creates nothing.

#### Scenario: Via at a point
- **GIVEN** the blink and the via intent `gnd_tie` at (120 mm, 110 mm) on `GND` with diameter 0.6 mm and drill 0.3 mm
- **WHEN** it is resolved
- **THEN** the design gains one via at that point on `GND`, with layers `F.Cu` and `B.Cu` and the uuid `copper_uuid("gnd_tie", "via")`

#### Scenario: Buried via between two inner layers
- **GIVEN** a design with four copper layers and the via intent `core` on `GND` with `kind="buried"`, `layers=("In2.Cu", "In1.Cu")`, diameter 0.6 mm and drill 0.3 mm
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_copper_tracks.py -k via_kinds` resolves it
- **THEN** the design gains one via with `via_type == "buried"`, the layers `In1.Cu` and `In2.Cu` in this order, and the uuid `copper_uuid("core", "via")`

#### Scenario: Layers on a through via
- **GIVEN** the blink and a via intent with `kind="through"` and `layers=("F.Cu", "B.Cu")`
- **WHEN** it is resolved with `issues=found`
- **THEN** nothing is created and `found` holds one `kicad.copper.bad-layer` naming its key

### Requirement: Stitching vias
`resolve_copper` SHALL turn each stitch intent (`key`, `net`, `pitch`, `along`, `region`, `origin`, `diameter`, `drill`, `clearance`, `margin`) into through vias of its net, along a polyline, on a grid inside a region, or on a grid inside a pad of its net, keeping clear of other copper.
- Exactly one of `along` (at least two points) and `region` (at least three points forming a simple ring, or one pad reference) MUST be given, `pitch` MUST be positive and `margin` not negative; otherwise `kicad.copper.bad-intent`. Anchors among these points and in `origin` are replaced by their points first ("Anchored points in script copper").
- **Along.** Each segment of the polyline MUST be divided into the fewest equal parts no longer than `pitch` (the smallest `n ≥ 1` with `n²·pitch²` at least the squared length). The candidates MUST be the division points, each vertex once, rounded half to even, numbered `k = 0, 1, …` from the first vertex.
- **Region.** The candidates MUST be the grid points `(i, j)`, for integers `i` and `j`, that lie inside the region at a distance of at least `diameter / 2 + margin` from every edge, decided exactly, in order of `j` then `i`. The grid point `(i, j)` MUST be `origin + (i·pitch, j·pitch)` in the board frame when `origin` is a point, and `part_frame(design, component, number=number, index=index).point(offset + (i·pitch, j·pitch))` when `origin` is an anchor, so that the grid turns with the anchor's part and is mirrored with its bottom side.
- **Pad region.** A `region` that has `component` is a pad reference (`component`, `number`, `index`). It MUST name its pads as an anchor at offset (0, 0) does, with the codes of "Anchored points in script copper": one pad with `index`, else every pad of the number, which MUST lie at one position. Every pad named MUST be on the stitch's net, else `kicad.copper.net-conflict`, and one at least MUST have a copper entry on the outer copper layer of the part's side (`F.Cu` on the top, `B.Cu` on the bottom), else `kicad.copper.layer-mismatch`. When `origin` is a point, the grid is that of an anchor at the pads' position with offset (0, 0); when it is an anchor, the grid is that anchor's. A grid point MUST be a candidate when the disc of radius `r = diameter / 2 + margin` around it lies inside one of those copper entries: for an entry of core `K` and width `w`, when `K` is a filled ring and the point lies inside it, its distance to the edges of `K` MUST be at least `r − w / 2`; otherwise its distance to `K` MUST be at most `w / 2 − r`. Both are decided exactly with integers and `Fraction`.
- **Clearance.** A candidate MUST be dropped when its via disc comes closer than `clearance` to a copper entry or hole of any pad (`board-frame`), the copper entries of the pads of its own pad region excepted, or to a track, arc or via of another net or of no net, or when it touches a via of its own net. Existing items, the vias of earlier intents and the candidates already kept MUST count. Distances MUST be decided exactly with integers and `Fraction`, using c0005's predicates; an arc MUST count as its polyline of `Arc.polygonize(DEFAULT_TOL)` with its width grown by `2·DEFAULT_TOL + 2`. Zones MUST NOT count.
- **Keep-outs and the edge.** A candidate MUST also be dropped when its via disc meets the outline of a `Keepout` with `no_vias` on a copper layer (a through via crosses every copper layer), or comes closer than the edge clearance in force to a ring of `board_outline`: the `min` of the governing board-wide `edge_clearance` rule in `rulemap.rule_order`, else the project's `min_copper_edge_clearance` (`H-K-STITCH-AVOID`). A candidate that lies off the board, outside the board ring or inside a cut-out, MUST be dropped too. Without a closed outline the edge MUST NOT be checked. On a rebuild the rule areas and the outline of the existing board MUST count, because the lens keeps them. These candidates are dropped candidates for the count below. This bullet applies to the candidates of a pad region as to any other: the exception of "Clearance" covers only the copper entries of the region's own pads.
- `clearance` MUST be the intent's, else the clearance of the class of its net, else `kicad.copper.size-missing`.
- The dropped candidates of an intent MUST give one `kicad.copper.stitch-skipped` info with their count, and an intent that keeps no candidate one `kicad.copper.stitch-empty` warning.

#### Scenario: Along a line
- **GIVEN** a design without copper near the line (0, 0)–(10 mm, 0), and a stitch intent on `GND` along it with pitch 3 mm, diameter 0.6 mm, drill 0.3 mm and clearance 0.2 mm
- **WHEN** it is resolved
- **THEN** it creates five vias at x = 0, 2.5, 5, 7.5 and 10 mm, with the locators `via[0]` to `via[4]`

#### Scenario: Region with margin and a pad to avoid
- **GIVEN** `Mini_R_0603` placed at (5 mm, 5 mm), 0°, with both pads on `LED_DRV`, and a stitch intent on `GND` in the square (0, 0)–(10 mm, 10 mm) with pitch 2.5 mm, origin (0, 0), diameter 0.6 mm, drill 0.3 mm, margin 0.2 mm and clearance 0.2 mm
- **WHEN** it is resolved with `issues=found`
- **THEN** it creates the eight vias at (2.5·i, 2.5·j) mm for i and j in 1, 2, 3 except (5 mm, 5 mm), with the locators `via[i,j]`, and `found` holds one `kicad.copper.stitch-skipped` with the count 1

#### Scenario: Own-net via touched
- **GIVEN** the region of the previous scenario without the footprint and with an existing `GND` via of diameter 0.6 mm at (5 mm, 5 mm)
- **WHEN** the stitch is resolved
- **THEN** no new via is placed at (5 mm, 5 mm) and the other eight are created

#### Scenario: Fence across a keep-out
- **GIVEN** the line of "Along a line" crossing a `Keepout` with `no_vias` on both copper layers that covers x from 4 mm to 6 mm
- **WHEN** the stitch is resolved with `issues=found`
- **THEN** no via is created at x = 5 mm, the others are, and `found` holds one `kicad.copper.stitch-skipped` with the count 1

#### Scenario: Fence along the edge
- **GIVEN** a design with a closed outline whose left edge is the line x = 0, a board-wide `edge_clearance` rule of 0.5 mm, and a stitch intent along the line x = 0.4 mm with diameter 0.6 mm
- **WHEN** the stitch is resolved
- **THEN** no via is created, and one `kicad.copper.stitch-empty` warning is given

#### Scenario: Thermal array in a pad
- **GIVEN** `Frame_Anchor` placed for `U1` at (20 mm, 20 mm), 0°, on the top, its 3 mm × 3 mm pad `4` (at (1 mm, 0) in the footprint) on `GND`, and a stitch `ep` on `GND` whose `region` is the pad reference (`U1`, `4`, `None`) and whose `origin` is a point, with pitch 1 mm, diameter 0.6 mm, drill 0.3 mm, margin 0.1 mm and clearance 0.2 mm
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_copper_stitch.py -k pad_region` resolves it with `issues=found`
- **THEN** it creates nine vias at (21 + i, 20 + j) mm for i and j in −1, 0 and 1, with the locators `via[i,j]`, and `found` holds no issue: the pad is no obstacle to its own array

#### Scenario: The grid turns with the part
- **GIVEN** the stitch of "Thermal array in a pad" with `U1` placed at (20 mm, 20 mm), 30°, on the bottom
- **WHEN** it is resolved
- **THEN** the nine vias lie at `part_frame(design, "U1", number="4").point(Point(i·1_000_000, j·1_000_000))` for i and j in −1, 0 and 1, with the same locators `via[i,j]` as at 0°

#### Scenario: A pad region of another net
- **GIVEN** the design of "Thermal array in a pad" with `Mini_Edge_Cases` also placed for `J1` at (40 mm, 20 mm), the stitch `ep` on `VIN`, the net of pad `1` of `U1`, instead of `GND`, and a stitch `j1` on `GND` whose region is pad `1` of `J1`, whose two pads `1` lie at different positions, without an index
- **WHEN** they are resolved with `issues=found`
- **THEN** neither creates a via, and `found` holds one `kicad.copper.net-conflict` naming `ep`, `U1` and `4`, and one `kicad.copper.bad-intent` naming `j1`, `J1` and `1`

#### Scenario: A keep-out across a pad region
- **GIVEN** the design of "Thermal array in a pad" with a `Keepout` with `no_vias` on both copper layers that covers x from 21.6 mm to 22.4 mm over the height of pad `4`
- **WHEN** the stitch `ep` is resolved with `issues=found`
- **THEN** it creates the six vias at (20 mm, 20 + j mm) and (21 mm, 20 + j mm) for j in −1, 0 and 1, and `found` holds one `kicad.copper.stitch-skipped` with the count 3: the pad's own copper is no obstacle, the keep-out still is

### Requirement: Script copper is regenerated
`merge_copper(existing, built) -> CopperMerge` SHALL decide which tracks, arcs and vias of the design `existing` stay beside the script copper of the design `built`, its tracks, arcs and vias whose KiCad uuid is a copper uuid, and `resolve_copper` SHALL use it with its input as `existing` and a design holding only the items it creates as `built`.
- An existing item whose KiCad uuid is a copper uuid MUST be dropped. When `built` holds an item with that uuid, it is regenerated, with one `kicad.copper.regenerated` info when a modelled field differs (points, width, diameter, drill, layer or layers, via type, or net name), because it was edited in KiCad or the pads it joins moved; otherwise it is stale, with one `kicad.copper.stale` warning naming its uuid, kind, layer, first point and net name.
- An existing item without a copper uuid that equals a script item of `built` (kind, layer or layers, end points as an unordered pair, with the same mid point for an arc, or position, width or diameter and drill and via type, net name) MUST be dropped with one `kicad.copper.duplicate` info.
- `CopperMerge` MUST hold `kept` (the ids of the existing items that stay), `issues`, and the counts `regenerated`, `stale` and `duplicates`.
- The design returned by `resolve_copper` MUST hold the tracks, arcs and vias of its input that `merge_copper` keeps, in their order, followed by the created tracks, arcs and vias in intent order; every other part of the design MUST be unchanged. Resolving that design again with the same intents MUST return an equal design and no issue.

#### Scenario: Idempotent
- **GIVEN** the blink resolved with the intents of `examples/blink_routed/design.py`
- **WHEN** the result is resolved again with the same intents
- **THEN** the two designs are equal and no issue is reported

#### Scenario: Stale script copper
- **GIVEN** the blink resolved with the intents `a` and `b`
- **WHEN** the result is resolved with `a` only
- **THEN** the items of `b` are gone, and one `kicad.copper.stale` warning per item of `b` names its uuid

#### Scenario: Edited script copper is regenerated
- **GIVEN** the resolved blink whose track with locator `seg[0]` of `a` was moved 1 mm, keeping its uuid
- **WHEN** it is resolved again with `a`
- **THEN** the track ends at its pad again, and one `kicad.copper.regenerated` info names its uuid

#### Scenario: Duplicates and user copper
- **GIVEN** the resolved blink plus a copy of a script track with a version-4 uuid, and a track on `GND` with a version-4 uuid that equals no script item
- **WHEN** it is resolved again with the same intents
- **THEN** the copy is removed with one `kicad.copper.duplicate` info, and the `GND` track is kept

#### Scenario: Arc removed from the script
- **GIVEN** the blink resolved with an intent `bend` that holds an arc step
- **WHEN** the result is resolved with no intent
- **THEN** the arc and the tracks of `bend` are gone, with one `kicad.copper.stale` warning each, the arc's naming its uuid, the kind `arc`, its layer, its first point and its net

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
| `kicad.copper.bad-size` | error | a size is not positive, or a drill is not smaller than its diameter |
| `kicad.copper.stale` | warning | script copper of an earlier build has no intent any more and is removed |
| `kicad.copper.end-unplaced` | warning | an intent ends at a staged part and creates nothing |
| `kicad.copper.stitch-empty` | warning | a stitch intent keeps no candidate |
| `kicad.copper.regenerated` | info | script copper differs from its regenerated copy (edited in KiCad, or its pads moved) and is replaced |
| `kicad.copper.duplicate` | info | an item equal to script copper is removed |
| `kicad.copper.stitch-skipped` | info | stitch candidates are dropped for clearance (with the count) |

#### Scenario: Closed set enforced
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_copper_issues.py -k closed_set` collects every issue code produced by the copper tests
- **THEN** each is a key of `COPPER_ISSUE_CODES` with the severity of this table, and every key is produced by at least one test

### Requirement: Copper evidence
`copper.EVIDENCE` SHALL be `Evidence(Level.INFERRED, hypotheses=("H-G-FRAME-UUID", "H-G-FRAME-ROUTE"))`, and its level MUST stay `INFERRED` when both rows are `KICAD-VERIFIED`: they cover the routed blink, not every design.

#### Scenario: Evidence constant
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_copper_issues.py -k evidence` reads `copper.EVIDENCE`
- **THEN** its level is `INFERRED` and its hypotheses are `H-G-FRAME-UUID` and `H-G-FRAME-ROUTE`

### Requirement: Meanders from intents
`fenolite.backends.kicad.meander.resolve_meanders(design, meanders, *, major, issues=None) -> Design` SHALL replace, for each meander intent (`key`, `track`, `segment`, `amplitude`, `pitch`, `target`, `match`, `side`, `margin`), the track with the uuid `copper_uuid(track, f"seg[{segment}]")` that `resolve_copper` created by a square-wave meander that gives the track intent its target length. The module MUST import only the standard library, `core`, `model`, `geometry`, `backends.base` and modules of `backends.kicad`, never `fenolite.dsl`; it MUST read intents by attribute through the protocol `MeanderIntentLike`, and the function MUST be pure.
- **Length of an intent.** The length of a track intent MUST be the sum of the `segment_length` of its tracks, the `arc_length` of its arcs, the heights of its vias as major `major` counts a via that only the two segments of its via step join (`board-frame`, "KiCad net lengths"), and the die lengths of the pads its ends chose. The target MUST be `target`, or the length of the intent `match` after its own meander, when it has one.
- **Shape.** Let `P` and `Q` be the start and end of the replaced track, `u` the unit vector from `P` to `Q`, `n` the unit normal on `side` (`left` is the side where `orient2d(P, Q, X) < 0`), `m` the margin (`pitch` when `None`), `E` the target less the intent's length, `N = ⌈E / (2·amplitude)⌉` and `h = E / (2N)`. The points MUST be `P`; then, for each bump `i` from 0 to `N − 1`, `P + (m + 2i·pitch)·u`, the same point plus `h·n`, `P + (m + (2i + 1)·pitch)·u + h·n` and `P + (m + (2i + 1)·pitch)·u`; then `Q`. Each point MUST be computed with at least 64 fractional bits and rounded half to even per axis. One track MUST join each two consecutive points, with the width, layer and net of the replaced track and the uuid `copper_uuid(key, f"m[{k}]")`, `k` counting in path order, and the new tracks MUST take the place of the replaced one in `Board.tracks`.
- **Correction.** The intent's length MUST be measured on the built shape; while it differs from the target by more than `LENGTH_TOLERANCE_NM = 10`, half of the difference MUST be added to the height of the last bump and the shape built again, at most twice. No bump MUST be higher than `amplitude` plus 10 nm.
- **Refusals.** `0 ≤ E ≤ LENGTH_TOLERANCE_NM` MUST change nothing and give `kicad.meander.not-needed`, because the intent already lies within the tolerance of its target; `E < 0` `kicad.meander.too-long`; a `pitch` not above the replaced track's width `kicad.meander.bad-shape`; `(2N − 1)·pitch + 2m` above the length of `P`–`Q` `kicad.meander.no-room`, whose message gives `E` and the most the run can add; a track intent without the segment, because it had an error or ended at a staged part, `kicad.meander.no-segment`; a `match` whose intent created nothing, or matches that form a cycle, `kicad.meander.bad-match`; a length still more than 10 nm from the target `kicad.meander.inexact`; a key, side, size or segment that is malformed `kicad.meander.bad-intent`. A refused meander MUST change nothing, and the other meanders are still resolved.
- **Order.** Meanders MUST be resolved in key order, except that a meander whose `match` intent has a meander comes after that one.
- The same design and intents MUST give the same tracks, uuids and issues in every process, whatever `PYTHONHASHSEED`. The tracks carry copper uuids, so `merge_copper` and `merge_layout` keep, regenerate and drop them as script copper.
- `MEANDER_ISSUE_CODES` MUST be the closed table of these codes; as `kicad.*` codes they pass through the closed tables of the build and of the lens unchanged. `meander.EVIDENCE` MUST be `Evidence(Level.INFERRED, hypotheses=("H-K-NETLEN-MEANDER",))`.

| code | severity | when |
|---|---|---|
| `kicad.meander.bad-intent` | error | a key, side, size or segment index is malformed, or the segment is an arc |
| `kicad.meander.bad-shape` | error | the pitch is not above the track's width |
| `kicad.meander.too-long` | error | the intent is already longer than the target |
| `kicad.meander.no-room` | error | the segment cannot add the needed length with the amplitude, pitch and margin |
| `kicad.meander.bad-match` | error | `match` names an intent without copper, or matches form a cycle |
| `kicad.meander.inexact` | error | after two corrections the length differs from the target by more than 10 nm |
| `kicad.meander.no-segment` | warning | the track intent created no segment of that index; the meander creates nothing |
| `kicad.meander.not-needed` | info | the intent already has the target length, within 10 nm |

#### Scenario: A run along an axis
- **GIVEN** a design with the track intent `t` of net `N` from (0, 0) to (20 mm, 0) on `F.Cu`, width 0.2 mm, resolved by `resolve_copper`, and the meander `m` on segment 0 with `target=23 mm`, `amplitude=1 mm`, `pitch=1 mm` and side `left`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_meander.py -k axis` calls `resolve_meanders(design, [m], major=10)`
- **THEN** the track `seg[0]` of `t` is gone, nine tracks with the uuids `copper_uuid("m", "m[0]")` to `m[8]` join (0, 0), (1 mm, 0), (1 mm, −0.75 mm), (2 mm, −0.75 mm), (2 mm, 0), (3 mm, 0), (3 mm, −0.75 mm), (4 mm, −0.75 mm), (4 mm, 0) and (20 mm, 0), and their lengths sum to 23 000 000

#### Scenario: A run at 30 degrees
- **GIVEN** the same intent from (0, 0) to (17.320508 mm, 10 mm) and a meander with `target=23 mm`
- **WHEN** it is resolved
- **THEN** the intent's length differs from 23 mm by at most 10 nm, and every point lies within `amplitude` plus 10 nm of the run on its left

#### Scenario: Matching another intent
- **GIVEN** the track intents `p` of 20 mm and `n` of 18.8 mm, and a meander on `n` with `match="p"`
- **WHEN** it is resolved
- **THEN** the length of `n` differs from that of `p` by at most 10 nm, and `p` is unchanged

#### Scenario: Refusals change nothing
- **GIVEN** the intent of "A run along an axis"
- **WHEN** meanders with `target=60 mm`, with `target=15 mm` and with `pitch=0.2 mm` are resolved, one at a time
- **THEN** each design is unchanged, and the issues hold `kicad.meander.no-room` (naming 40 mm needed and at most 18 mm possible), `kicad.meander.too-long` and `kicad.meander.bad-shape`

### Requirement: Anchored points in script copper
`resolve_copper` SHALL accept an anchor wherever an intent holds a point, in addition to the elements and fields that "Copper module", "Tracks from intents", "Single vias" and "Stitching vias" read: a path element, the `at` of a via step or of a via intent, the `mid` and the `end` of an arc step, and the `along` points, the `region` points and the `origin` of a stitch. It SHALL replace each anchor by its board point before any other rule reads the intent.
- An anchor is an object with `component`, `number`, `index` and `offset`, read by attribute through the protocol `AnchorLike`, which `copper` exports in addition to the names of "Copper module". An element or a field that has `offset` MUST be read as an anchor, never as a pad end.
- Its point MUST be `part_frame(design, component, number=number, index=index).point(offset)` (`board-frame`, "Anchor points in a part's frame"), on the design given to `resolve_copper`. A build gives the design at its effective placements (`design-dsl`, "Copper intents in a build"), so anchored copper follows a part that was placed in KiCad or by `fenolite place`.
- An anchor is a point and nothing more: it joins no pad and gives no net. A track's net still comes from its pad ends, and a via or a stitch names its net ("Nets of script copper").
- An anchor that cannot be resolved MUST make its intent create nothing, while the next intents are still resolved, with a code of "Copper issue codes" and its severity: `kicad.copper.pad-not-found` when no footprint matches the component, no pad has the number, or the index is beyond the pads of the number; `kicad.copper.bad-intent` when the pads of the number lie at more than one position and no index is given; `kicad.copper.end-unplaced` when `unplaced` names the component, by path or reference, as for a pad end. Each issue MUST name the intent's key and the anchor's component, and its number when it has one.
- The locator and the uuid of an item are those of the element or candidate the anchor stands for ("Copper uuids and ids"), so resolving again after the part moved regenerates the same items ("Script copper is regenerated"). An intent without an anchor MUST resolve as before.

#### Scenario: A via anchored beside a pad
- **GIVEN** the blink built for target 10, whose `U1` sits at 0° on the top, and the via intent `fan9` on `VIN` at `Anchor("U1", "9", None, Point(0, 1_000_000))` with diameter 0.6 mm and drill 0.3 mm
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_copper_anchor.py -k beside` resolves it
- **THEN** the design gains one via at the position of the record of `U1` pad `9` plus (0, 1 mm), on `VIN`, with the uuid `copper_uuid("fan9", "via")`

#### Scenario: Anchored copper follows a turned part
- **GIVEN** the result of "A via anchored beside a pad", in which the footprint of `U1` is then placed again with `place_footprint` at the same point at 90°
- **WHEN** it is resolved again with `fan9` and `issues=found`
- **THEN** the via lies at the record of pad `9` plus (1 mm, 0), which `part_frame(design, "U1", number="9").point(Point(0, 1_000_000))` returns, with the same uuid, and `found` holds one `kicad.copper.regenerated` naming that uuid

#### Scenario: An anchor is not a pad end
- **GIVEN** the blink and a track intent `stub` without net, width 0.3 mm, whose path is `PadEnd("R1", "2", None)` then `Anchor("R1", "2", None, Point(1_000_000, 0))`, and a track intent `loose` whose path holds two anchors and no pad end, without net
- **WHEN** both are resolved with `issues=found`
- **THEN** `stub` creates one track from `R1` pad `2` to the point 1 mm beside it, on `LED_A`, the net of its pad end; `loose` creates nothing, and `found` holds one `kicad.copper.no-net` naming it

#### Scenario: Anchors that cannot be resolved
- **GIVEN** the blink and via intents anchored to `R9`, which has no footprint, to pad `7` of `R1`, and to `D1`
- **WHEN** they are resolved with `unplaced=("D1",)` and `issues=found`
- **THEN** no via is created, and `found` holds two `kicad.copper.pad-not-found`, naming `R9` and `R1` with `7`, and one `kicad.copper.end-unplaced` naming `D1`

#### Scenario: An anchor on a shared number needs an index
- **GIVEN** `Mini_Edge_Cases` placed at (0, 0) for `J1`, its two pads `1` at (−2 mm, 0) and (2 mm, 0), and the via intents `a` at `Anchor("J1", "1", None, Point(0, 0))` and `b` at `Anchor("J1", "1", 1, Point(0, 0))` on `GND`
- **WHEN** they are resolved with `issues=found`
- **THEN** `a` creates nothing and `found` holds one `kicad.copper.bad-intent` naming `a`, `J1` and `1`; `b` creates one via at (2 mm, 0)
