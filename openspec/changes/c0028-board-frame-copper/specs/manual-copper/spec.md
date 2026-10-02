## ADDED Requirements

### Requirement: Copper module
The module `fenolite.backends.kicad.copper` SHALL resolve copper intents into tracks and vias of a KiCad design and SHALL merge script copper with existing copper, and MUST import only the standard library, `core`, `model`, `geometry`, `backends.base` and modules of `backends.kicad` (`package-layering`), never `fenolite.dsl`.
- Public names: `COPPER_MARKER`, `copper_uuid`, `is_copper_uuid`, `PadEndLike`, `ViaStepLike`, `TrackIntentLike`, `ViaIntentLike`, `StitchIntentLike`, `CopperIntentLike`, `resolve_copper`, `merge_copper`, `CopperMerge`, `COPPER_ISSUE_CODES` and `EVIDENCE`. `fenolite.backends.kicad` MUST re-export `resolve_copper`.
- Intents MUST be read by attribute through the structural protocols, so the DSL's frozen dataclasses (`design-dsl`, "Copper intents in the DSL") and any object with the same attributes are accepted. An intent with `path` is a track, one with `pitch` a stitch, and any other a via. A `Point` element of a path is a point; any other element is read as a pad end when it has `component`, else as a via step.
- `resolve_copper(design, intents, *, unplaced=(), issues=None) -> Design` and `merge_copper(existing, built) -> CopperMerge` MUST be pure: they read no file and no environment variable, and return new values without changing their arguments.

#### Scenario: Import edges
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes with no `ALLOWED` change, and `src/fenolite/backends/kicad/copper.py` does not import `fenolite.dsl`

#### Scenario: Pure resolution
- **GIVEN** the blink built for target 10 and the intents of `examples/blink_routed/design.py`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_copper_tracks.py -k pure` resolves them twice
- **THEN** the two results are equal and the input design's canonical texts are unchanged

### Requirement: Copper uuids and ids
Every track and via that `resolve_copper` creates SHALL carry the KiCad uuid `copper_uuid(key, locator)` in `native_ids["kicad"]` and the id that "Identifier derivation" gives an imported object with that native id: `derived_id("trk", "kicad", uuid)` or `derived_id("via", "kicad", uuid)`, with `provenance` `None`.
- `copper_uuid(key, locator)` MUST be the RFC 9562 version-8 uuid (S-0110) whose 48-bit `custom_a` field is `COPPER_MARKER = 0x66656E6F6C69`, whose version is 8 and variant `0b10`, and whose other 74 bits are the first 74 bits of the SHA-256 of the UTF-8 text `kicad-copper:<key>:<locator>`, written in the canonical lower-case 36-character form, which starts with `66656e6f-6c69-8`. Because Python's `uuid.UUID` accepts `version` only up to 5 before 3.14 (S-0111), the version and variant bits MUST be set on the integer.
- `is_copper_uuid(text)` MUST be true exactly for canonical uuid texts with that marker, version 8 and variant `0b10`.
- Locators: `seg[i]` for the segment that leaves path element `i` of a track; `via[i]` for the via step at path element `i`; `via` for a single via; `via[k]` for the `k`-th via of a stitch along a polyline; `via[i,j]` for the stitch via at grid indices `(i, j)` of a region.
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

### Requirement: Tracks from intents
`resolve_copper` SHALL turn each track intent (`key`, `path`, `layer`, `width`, `net`) into tracks and through vias along its path.
- A path element MUST be a pad end (`component`, `number`, `index`), a point, or a via step (`at`, `layer`, `diameter`, `drill`). A path with fewer than two elements or starting with a via step, or a key used by an earlier intent, MUST give `kicad.copper.bad-intent` (error).
- The point of a pad end MUST be the `position` of the chosen pad (`board-frame`, "Board-frame pads").
- The current layer starts as the intent's `layer`. For each element `i` but the last, one `Track` MUST be created from the point of element `i` to the point of element `i + 1` on the current layer, after the layer change of element `i` when it is a via step. A segment whose two points are equal MUST NOT be created, and its locator stays unused. A via step MUST create one `through` via at its point, whose `layers` are the first and last copper layers of the board, and MUST set the current layer to its `layer`.
- **Pad choice.** A pad end may stand anywhere in the path, so a track can chain several pads. Its candidates MUST be the pads that `find_pads(design, component, number)` returns that have a copper entry on the layer of every segment touching that end. With `index`, the `index`-th of all matches MUST be used. Without it, pad ends MUST be chosen in path order: the first element takes the candidate nearest to the point of the second element, or the nearest pair when the second element is a pad end without `index`; every other pad end takes the candidate nearest to the point of the element before it. Distances are exact squared distances, with ties to the earlier pads.
- **Layers.** `layer` and every via step's `layer` MUST be copper layers of the board and every via step MUST change the layer, else `kicad.copper.bad-layer`. A pad end without a candidate MUST give `kicad.copper.layer-mismatch`; a component or number that `find_pads` cannot match, or an `index` beyond the matches, `kicad.copper.pad-not-found` (errors).
- **Sizes.** The width MUST be the intent's `width`, else the `track_width` of the class of the track's net; a via step's sizes its `diameter` and `drill`, else the class's `via_diameter` and `via_drill`. A missing size MUST give `kicad.copper.size-missing`, and a size that is not positive or a drill not smaller than its diameter `kicad.copper.bad-size` (errors).
- An intent with an error MUST create nothing; the next intents are still resolved. Created tracks and vias MUST follow the path order, and intents their given order.

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
`resolve_copper` SHALL turn each via intent (`key`, `at`, `net`, `diameter`, `drill`) into one through via at `at` on its net, with the locator `via`, the size rules of "Tracks from intents" and the net rules of "Nets of script copper".

#### Scenario: Via at a point
- **GIVEN** the blink and the via intent `gnd_tie` at (120 mm, 110 mm) on `GND` with diameter 0.6 mm and drill 0.3 mm
- **WHEN** it is resolved
- **THEN** the design gains one via at that point on `GND`, with layers `F.Cu` and `B.Cu` and the uuid `copper_uuid("gnd_tie", "via")`

### Requirement: Stitching vias
`resolve_copper` SHALL turn each stitch intent (`key`, `net`, `pitch`, `along`, `region`, `origin`, `diameter`, `drill`, `clearance`, `margin`) into through vias of its net, along a polyline or on a grid inside a region, keeping clear of other copper.
- Exactly one of `along` (at least two points) and `region` (at least three points forming a simple ring) MUST be given, `pitch` MUST be positive and `margin` not negative; otherwise `kicad.copper.bad-intent`.
- **Along.** Each segment of the polyline MUST be divided into the fewest equal parts no longer than `pitch` (the smallest `n ≥ 1` with `n²·pitch²` at least the squared length). The candidates MUST be the division points, each vertex once, rounded half to even, numbered `k = 0, 1, …` from the first vertex.
- **Region.** The candidates MUST be the points `origin + (i·pitch, j·pitch)` for integers `i` and `j` that lie inside the region at a distance of at least `diameter / 2 + margin` from every edge, decided exactly, in order of `j` then `i`.
- **Clearance.** A candidate MUST be dropped when its via disc comes closer than `clearance` to a copper entry or hole of any pad (`board-frame`), or to a track, arc or via of another net or of no net, or when it touches a via of its own net. Existing items, the vias of earlier intents and the candidates already kept MUST count. Distances MUST be decided exactly with integers and `Fraction`, using c0005's predicates; an arc MUST count as its polyline of `Arc.polygonize(DEFAULT_TOL)` with its width grown by `2·DEFAULT_TOL + 2`. Zones, rule areas and the board edge MUST NOT count.
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

### Requirement: Script copper is regenerated
`merge_copper(existing, built) -> CopperMerge` SHALL decide which tracks, arcs and vias of the design `existing` stay beside the script copper of the design `built`, its tracks and vias whose KiCad uuid is a copper uuid, and `resolve_copper` SHALL use it with its input as `existing` and a design holding only the items it creates as `built`.
- An existing item whose KiCad uuid is a copper uuid MUST be dropped. When `built` holds an item with that uuid, it is regenerated, with one `kicad.copper.regenerated` info when a modelled field differs (points, width, diameter, drill, layer or layers, via type, or net name), because it was edited in KiCad or the pads it joins moved; otherwise it is stale, with one `kicad.copper.stale` warning naming its uuid, kind, layer, first point and net name.
- An existing item without a copper uuid that equals a script item of `built` (kind, layer or layers, end points as an unordered pair or position, width or diameter and drill, net name) MUST be dropped with one `kicad.copper.duplicate` info.
- `CopperMerge` MUST hold `kept` (the ids of the existing items that stay), `issues`, and the counts `regenerated`, `stale` and `duplicates`.
- The design returned by `resolve_copper` MUST hold the tracks, arcs and vias of its input that `merge_copper` keeps, in their order, followed by the created tracks and vias in intent order; every other part of the design MUST be unchanged. Resolving that design again with the same intents MUST return an equal design and no issue.

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

### Requirement: Copper issue codes
`copper` SHALL report its findings only with the codes of the closed table `COPPER_ISSUE_CODES`. They are `kicad.*` codes, so they pass through the closed sets of `lens.build.BUILD_ISSUE_CODES` (c0011) and `lens.preserve.PRESERVE_ISSUE_CODES` (c0019) unchanged, as `design-dsl` "Build issue codes" and `layout-lens` "Layout issue codes" allow.

| code | severity | when |
|---|---|---|
| `kicad.copper.bad-intent` | error | a path, region, pitch, margin or key is malformed or a key repeats |
| `kicad.copper.pad-not-found` | error | no footprint, no pad with the number, or an index beyond the matches |
| `kicad.copper.layer-mismatch` | error | no pad of a pad end has copper on the segment's layer |
| `kicad.copper.bad-layer` | error | a layer is not a copper layer of the board, or a via step keeps the layer |
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
