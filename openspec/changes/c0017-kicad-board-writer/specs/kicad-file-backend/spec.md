## ADDED Requirements

### Requirement: Board writing per target
`fenolite.backends.kicad.pcb.write_board(design, *, target=DEFAULT_TARGET, allow_lossy=False)` SHALL return a `WriteResult` whose `text` is a `.kicad_pcb` file for KiCad `target`.0 and whose `issues` hold the warnings and infos of the write. It MUST proceed in this order:
1. For a design read from a file, `versions.require_editable` and then `versions.check_target` on the source header (`pcb.source_info(design)`). A created design has no source header and skips this step.
2. The refusal of "KiCad 8 boards are read-only".
3. The header `(version FORMAT_VERSIONS[FileKind.BOARD][target])`, `(generator "fenolite")` and `(generator_version "<target>.0")`, for read and created boards alike.
4. The net form of "Net form per target", applied to every `net` node.
5. For target 10, every node matched by an inventory row with `until_major = 9` is converted or dropped, with one `kicad.board.obsolete-dropped` info per row id whose nodes were removed, converted rows included, carrying the count of nodes.
6. Created entities are inserted in `pcb.CANONICAL_ORDER` ("Slot source for model entities" of `kicad-slots`).
7. `versions.check_emittable(root, FileKind.BOARD, target)` runs on the final tree; its errors are handled by "Lossy writes are refused unless allowed".

Further rules:
- `target` MUST be in `TARGET_MAJORS`; any other value raises `ValueError`.
- `write_board` MUST NOT write any file, and `text` MUST be printed by c0006's `dumps` in `kicad` style and end with a newline.
- Writing the same design twice MUST give identical `text`.
- `WriteResult.issues` MUST hold only warnings and infos; every error MUST be raised.
- The writer's issue codes MUST be the closed set `pcb.WRITE_ISSUE_CODES`: `kicad.board.dropped-too-new` (warning), `kicad.board.obsolete-dropped` (info), `kicad.board.opaque-net-ref`, `kicad.board.projection-read-only`, `kicad.board.outline-conflict` and `kicad.board.flip-unsupported` (errors).

#### Scenario: Header for target 9
- **GIVEN** the created test board `tests/_boards.py::created_board()`, built through the model API without library definitions
- **WHEN** `write_board(design, target=9)` is called and the text is parsed
- **THEN** the root has `(version 20241229)`, `(generator "fenolite")` and `(generator_version "9.0")`

#### Scenario: Emit check is clean for both targets
- **GIVEN** the created test board
- **WHEN** it is written for target 9 and for target 10, and `check_emittable` runs on each parsed text with the same target
- **THEN** both calls return no issue at all

#### Scenario: Read board upgraded to target 10
- **GIVEN** `tests/data/kicad/tokens/skeleton.kicad_pcb` (header `20241229`) read with `read_board`
- **WHEN** `write_board(design, target=10)` is called
- **THEN** the text has header `20260206` and `generator_version "10.0"`, holds none of `hpglpennumber`, `hpglpenspeed`, `hpglpendiameter`, `plotinvisibletext`, `filled_areas_thickness` and `net_name` and no root `net` row, and `issues` holds exactly seven `kicad.board.obsolete-dropped` infos, one for each of the row ids `board-net-table` (count 3), `zone-net-name`, `zone-filled-areas-thickness`, `plot-hpglpennumber`, `plot-hpglpenspeed`, `plot-hpglpendiameter` and `plot-plotinvisibletext` (count 1 each)

#### Scenario: Downgrade refused
- **GIVEN** `tests/data/kicad/tokens/future.kicad_pcb` (header `20260206`) read with `read_board`
- **WHEN** `write_board(design, target=9)` is called
- **THEN** `DowngradeRefusedError` is raised with `cli_code == "FEN-7002"`

#### Scenario: Future board refused
- **GIVEN** a copy of `tests/data/kicad/tokens/future.kicad_pcb` whose header is changed to `20990101`, read with `read_board`
- **WHEN** `write_board(design, target=10)` is called
- **THEN** `FutureFormatError` is raised and no text is returned

#### Scenario: Deterministic text
- **GIVEN** the created test board
- **WHEN** it is written twice for target 10
- **THEN** the two texts are equal byte for byte

### Requirement: Created board header
For a created design, `write_board` SHALL emit exactly the root head set of c0007's `tests/data/kicad/tokens/skeleton.kicad_pcb`:
- `version`, `generator` and `generator_version`;
- `(general (thickness T) (legacy_teardrops no))`, where T is the sum of the `Board.stackup` layer thicknesses, or 1.6 mm without a stack-up;
- `(paper "A4")`;
- `layers`, from `Board.layers` and each layer's `kicad` bag;
- `(setup (pad_to_mask_clearance 0))`;
- for target 9 only, the net table.

The content follows in `CANONICAL_ORDER`. `fenolite.backends.kicad.layers.created_layers(copper)` MUST return the 2- and 4-copper-layer sets recorded in `docs/formats/kicad/board.md`, numbered in the 9.0 scheme (`F.Cu` 0, `B.Cu` 2, `In1.Cu` 4, `In2.Cu` 6, `Edge.Cuts` 25), with the KiCad number, type and user name in each layer's `kicad` bag. Any other `copper` value MUST raise `ValueError`. Every head and field name the writer can create MUST match a row of the token inventory, appear in c0007's skeleton, or be listed in `pcb.FLOOR_HEADS`: a closed tuple of names that the 8.0 board format already has, each recorded in `docs/formats/kicad/board.md` with its source and written by the created test board that the triad oracle loads on both majors.

#### Scenario: Head set of a created 2-layer board
- **GIVEN** a created design whose board has `created_layers(2)` and no content
- **WHEN** it is written for target 9
- **THEN** the root's child heads are, in order, `version`, `generator`, `generator_version`, `general`, `paper`, `layers`, `setup`, `net`

#### Scenario: No net table for target 10
- **GIVEN** the same design
- **WHEN** it is written for target 10
- **THEN** the root's child heads are `version`, `generator`, `generator_version`, `general`, `paper`, `layers`, `setup`, and no child is headed `net`

#### Scenario: Four copper layers
- **WHEN** `created_layers(4)` is called
- **THEN** the copper layers are `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu` with KiCad numbers 0, 4, 6 and 2

#### Scenario: Created tokens are known
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pcb_write.py -k created_tokens` runs
- **THEN** every head and field in `CANONICAL_ORDER` and in the created header is found in the skeleton, is in `FLOOR_HEADS`, or matches an inventory row, and every name of `FLOOR_HEADS` occurs in the parsed text of the created test board written for target 9

### Requirement: Net form per target
`write_board` SHALL write every net reference in the form of the target, in modelled and opaque content alike:
- **Target 9.** The root holds `(net 0 "")` followed by `(net i "<name>")` for the model's nets sorted by name in code-point order, i = 1 … n. Pads write `(net i "<name>")`; tracks, arcs, vias and zones write `(net i)`; zones also write `(net_name "<name>")`. For a read board, the table MUST take the place of the source's table, and its row 0 MUST replace the source's opaque `(net 0 "")` slot, so the text holds exactly one row 0.
- **Target 10.** The root holds no net table, and the source's opaque `(net 0 "")` slot MUST be removed. Every reference is `(net "<name>")`, and zones write no `net_name`.
- Net 0 and the empty name mean no net. For target 9, a zone or rule area whose net is `None` MUST write `(net 0)` and `(net_name "")`, and every other item whose `net_id` is `None` MUST carry no `net` child. For target 10, an item whose net is `None` MUST NOT carry a `net` child.
- Inside opaque fragments, `(net 0)`, `(net 0 "")` and `(net "")` MUST be written `(net 0)` for target 9 and removed for target 10, and MUST NOT give `kicad.board.opaque-net-ref`.
- Inside opaque fragments, a numbered reference MUST be resolved through the source net table kept by `read_board`, and a named reference by its name; both MUST be re-emitted in the target's form.
- A `net` node in opaque content that matches none of `(net N)`, `(net N "name")` and `(net "name")`, or whose number N ≥ 1 is absent from the source table, MUST give `kicad.board.opaque-net-ref` (error). `allow_lossy` MUST NOT drop it.

#### Scenario: Numbered table for target 9
- **GIVEN** a design with nets `VIN`, `GND` and `LED_A`
- **WHEN** it is written for target 9
- **THEN** the root holds `(net 0 "")`, `(net 1 "GND")`, `(net 2 "LED_A")`, `(net 3 "VIN")` in that order, and a track on `GND` holds `(net 1)`

#### Scenario: Names for target 10
- **GIVEN** the same design
- **WHEN** it is written for target 10
- **THEN** a pad on `VIN` holds `(net "VIN")`, a zone on `GND` holds `(net "GND")` and no `net_name`, and the root holds no net table

#### Scenario: Opaque net reference converted
- **GIVEN** a copy of `tests/data/kicad/tokens/skeleton.kicad_pcb`, built in the test, with an added teardrop zone (an `attr` child holding `teardrop`) that holds `(net 2)` and `(net_name "B")`, where net 2 is `B` in the source table, read with `read_board`, so the teardrop zone is an opaque root slot
- **WHEN** it is written for target 10
- **THEN** the teardrop zone holds `(net "B")` and no `net_name`, and every other child of it is tree-equal to the source

#### Scenario: Unknown opaque net reference
- **GIVEN** a copy of `skeleton.kicad_pcb` whose segment holds `(net 7)` while the source table ends at 2, read with `read_board`, which keeps that reference opaque (c0009 "Nets in both forms")
- **WHEN** it is written with `allow_lossy=True`
- **THEN** `LossyWriteError` is raised with `droppable == False` and an issue `kicad.board.opaque-net-ref` whose `where` locates that node

#### Scenario: Unconnected rule area in both forms
- **GIVEN** a copy of `tests/data/kicad/board/two_layer.kicad_pcb` whose rule area holds `(net 0)` and `(net_name "")`, as KiCad 9 writes, read with `read_board`
- **WHEN** it is written for target 9 and for target 10
- **THEN** both writes succeed; the target-9 text holds exactly one root `(net 0 "")` and a rule area holding `(net 0)` and `(net_name "")`; the target-10 text holds no `net` node whose atom is `0` or `""`, and no `net_name`

### Requirement: Lossy writes are refused unless allowed
`write_board` SHALL raise `fenolite.backends.kicad.versions.LossyWriteError` (`cli_code = "FEN-7001"`) when the final emit check reports `kicad.token.too-new` inside an opaque slot and `allow_lossy` is false. The exception MUST carry every such issue in `issues` and `droppable = True`, and its hint MUST name `--allow-lossy`.
- With `allow_lossy=True`, the writer MUST remove the innermost opaque slot holding each such token, add one `kicad.board.dropped-too-new` warning per removed slot naming its locator and inventory row, and run the emit check again, which MUST then report no error.
- A too-new token in modelled content MUST raise `LossyWriteError` with `droppable = False`, with or without `allow_lossy`.
- Every other writer error (`opaque-net-ref`, `projection-read-only`, `outline-conflict`) MUST raise `LossyWriteError` with `droppable = False` and a hint that does not name `--allow-lossy`.
- The gate MUST be the emit check over tokens; a slot's `min_version` MUST NOT refuse a fragment whose tokens the target reads.

#### Scenario: 10.0 footprint embedded for target 9
- **GIVEN** a created design holding `Mini_R_0603` read from `tests/data/libs/Mini.pretty` (header `20260206`) and placed with `place_footprint`
- **WHEN** `write_board(design, target=9)` is called
- **THEN** `LossyWriteError` is raised with `droppable == True`, one of its issues names `duplicate_pad_numbers_are_jumpers`, and its hint contains `--allow-lossy`

#### Scenario: Lossy write allowed
- **GIVEN** the same design
- **WHEN** `write_board(design, target=9, allow_lossy=True)` is called
- **THEN** the text holds no `duplicate_pad_numbers_are_jumpers`, `issues` holds one `kicad.board.dropped-too-new` warning, and `check_emittable` on the parsed text for target 9 returns no error

#### Scenario: Modelled content is never dropped
- **GIVEN** a created design with a `Via` whose `via_type` is `"buried"`
- **WHEN** it is written for target 9 with `allow_lossy=True`
- **THEN** `LossyWriteError` is raised with `droppable == False`

### Requirement: KiCad 8 boards are read-only
`write_board` SHALL raise `fenolite.backends.kicad.versions.LegacyEditRefusedError` (`cli_code = "FEN-7003"`) for every target when `major_for(FileKind.BOARD, version)` of the source header is 8. Its hint MUST name `kicad-cli pcb upgrade` and re-saving in KiCad 9.0. `read_board` MUST keep reading such boards. A source whose header maps to major 9, including the development header `20241030`, MUST NOT be refused by this rule.

#### Scenario: KiCad 8 board refused
- **GIVEN** `tests/data/kicad/tokens/old/old.kicad_pcb` (header `20240108`) read with `read_board`
- **WHEN** `write_board(design, target=9)` and `write_board(design, target=10)` are called
- **THEN** each raises `LegacyEditRefusedError` with `cli_code == "FEN-7003"` and a hint containing `kicad-cli pcb upgrade`

#### Scenario: Development header of 9.0 is writable
- **GIVEN** a copy of `tests/data/kicad/tokens/skeleton.kicad_pcb` with header `20241030`, read with `read_board`
- **WHEN** it is written for target 9
- **THEN** no exception is raised and the text has header `20241229`

### Requirement: Projected fields on write
Before re-emitting an opaque fragment that a reader projected into a model field, `write_board` SHALL project the fragment again with the reader's function and compare the result with the model.
- When `Component.ref` or `Component.value` differs, the writer MUST rewrite only the value atom of the `(property "Reference" …)` or `(property "Value" …)` fragment; every other atom and child of that fragment MUST stay tree-equal.
- When a modelled field kept as an `Opaque` projected slot by the reader's reproducibility check differs, the writer MUST emit that field from the model if the fragment differs from the emitter's output for the old value only in spelling (same heads and atom count, numbers equal as decimals, strings equal as text, a zero angle written or omitted); otherwise it MUST give `kicad.board.projection-read-only`. An unchanged value MUST keep its fragment.
- When any other projection differs (`Component.properties` other than Reference and Value, `Graphic.width` from a `stroke`, `Pad.padstack`), the writer MUST give `kicad.board.projection-read-only`, naming the field and the locator.

#### Scenario: Reference renamed
- **GIVEN** `two_layer.kicad_pcb` read with `read_board`, and its resistor component's `ref` changed to `R9`
- **WHEN** the design is written for target 9 and the text is parsed
- **THEN** that footprint's `property "Reference"` node has value `"R9"` and is otherwise tree-equal to the source node

#### Scenario: Spelling-only projection re-emitted
- **GIVEN** a copy of `two_layer.kicad_pcb`, built in the test, whose first `segment` holds `(width 0.250000)`, read with `read_board`, so the reader keeps that `width` as a projected slot, and the track's width then changed to 300 000 nm
- **WHEN** the design is written for target 9 and the text is parsed
- **THEN** that segment holds `(width 0.3)` at the position of the source `width`, and no issue is raised

#### Scenario: Read-only projection edited
- **GIVEN** the same board with the resistor's `properties["Datasheet"]` changed
- **WHEN** it is written
- **THEN** `LossyWriteError` is raised with an issue `kicad.board.projection-read-only` naming `properties` and the footprint's locator

### Requirement: KiCad uuids on write
`write_board` SHALL give every emitted entity that KiCad identifies by `uuid` the value of `entity.native_ids["kicad"]` when present, and otherwise `uuid5(FENOLITE_NS, "kicad-out:" + entity.id)`. A part without its own id (an outline edge) MUST use `"kicad-out:<owner id>:<part>"`. `pcb.kicad_uuid(entity, part="")` MUST return the same value.

#### Scenario: Read uuids are kept
- **GIVEN** `two_layer.kicad_pcb` read with `read_board`
- **WHEN** it is written for target 9 and every `uuid` atom of both texts is collected
- **THEN** the two multisets are equal

#### Scenario: Created track uuid
- **GIVEN** a created `Track` with id `trk_00000000-0000-4000-8000-000000000001` and no native id
- **WHEN** a design holding it is written
- **THEN** the segment's uuid is `uuid5(FENOLITE_NS, "kicad-out:trk_00000000-0000-4000-8000-000000000001")`

### Requirement: Outline lowering
For any board whose `Board.outline` has points, created or read and then given an outline, `write_board` SHALL emit one `gr_line` on `Edge.Cuts` per edge of the outer ring and of each cutout, closing every ring, with stroke width 0.1 mm and type `solid`. The lines are created entities. A board with no outline, or an outline without points, MUST emit none. No `gr_arc` is emitted, because `Outline` holds points only. A board with both a non-empty outline and a `Graphic` on a layer of kind `edge` MUST give `kicad.board.outline-conflict`.

#### Scenario: Rectangle outline
- **GIVEN** a created board whose outline has the points (0, 0), (50 mm, 0), (50 mm, 30 mm), (0, 30 mm)
- **WHEN** it is written
- **THEN** the text holds four `gr_line` nodes on `Edge.Cuts`, the last ending at (0, 0)

#### Scenario: Outline and edge graphics
- **GIVEN** a created board with that outline and a `Graphic` on `Edge.Cuts`
- **WHEN** it is written
- **THEN** `LossyWriteError` is raised with an issue `kicad.board.outline-conflict`

#### Scenario: Outline set on a read board
- **GIVEN** `tests/data/kicad/tokens/skeleton.kicad_pcb` read with `read_board`, given the rectangle outline, once with its `Edge.Cuts` `gr_rect` and once with that `Graphic` removed from the model
- **WHEN** each design is written for target 9
- **THEN** the first raises `LossyWriteError` with an issue `kicad.board.outline-conflict`, and the second text holds four `gr_line` nodes on `Edge.Cuts` and no `gr_rect`

### Requirement: Footprint embedding
`fenolite.backends.kicad.embed.place_footprint(defn, *, component, at, rotation=0, side="top", locked=False, key)` SHALL return a `FootprintInstance` for `defn` placed at `at` with stored angle `rotation` on `side`:
- It MUST call `versions.require_editable` on the definition's source format first.
- It MUST emit the definition with `_fpmap.emit_footprint`, drop the children `version`, `generator` and `generator_version`, name the footprint `defn.lib_id`, set its layer to `F.Cu` (top) or `B.Cu` (bottom), and set the value atoms of Reference and Value from `component`.
- Every KiCad uuid MUST be `embed.placement_uuid(key, locator)`, which is `uuid5(FENOLITE_NS, f"kicad-place:{key}:{locator}")`, with `locator` the bare locator of the node in the emitted definition (`/footprint` for the footprint itself).
- The instance MUST be mapped by c0009's board-footprint mapping, so its pads, slots and ids equal those `read_board` gives for the written board. `component_id` MUST be `component.id`, `lib_ref` MUST be `defn.lib_id`, `attributes` MUST hold `defn.kind` (unless `unspecified`) followed by `defn.flags`, and every pad MUST have `net_id = None`.
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

### Requirement: DRC report reading
`fenolite.backends.kicad.drc.read_drc_report(text, *, file="")` SHALL return a `DrcReport` (`backend-protocol`, "Neutral DRC report") for the JSON text that `kicad-cli pcb drc --format json` writes.
- The text MUST be parsed as strict JSON with numbers kept as text. `NaN`, `Infinity` and `-Infinity` MUST raise `FormatError`, and no float is ever created.
- A missing key of `drc.REQUIRED_KEYS` (`source`, `date`, `kicad_version`, `violations`, `unconnected_items`, `schematic_parity`, `coordinate_units`) MUST raise `FormatError` naming the key. Unknown keys MUST be ignored.
- `ignored_checks`, present at 10.0.6 only, MUST be accepted and kept as the `key` string of each entry. `included_severities` MUST be kept when present.
- Positions MUST be converted to integer nanometres from `coordinate_units` (`mm`, `mils`, `in`) with exact rational arithmetic, rounded half to even when not exact. Any other unit MUST raise `FormatError`.
- `type` and `severity` MUST stay KiCad's strings, and violations, unconnected items and parity items MUST keep file order.
- `docs/formats/kicad/drc.md` MUST describe the report structure in Fenolite's own words, with key names only from S-0055 and S-0056; `drc.v1.json` MUST NOT be vendored or read at runtime.

#### Scenario: Millimetre report
- **GIVEN** the authored `tests/data/kicad/drc/report_mm.json`, whose first violation is a `clearance` with an item at x 12.5 and y 3.25
- **WHEN** `read_drc_report` reads it
- **THEN** `report.violations[0].type == "clearance"` and its first item has `position == Point(12_500_000, 3_250_000)`

#### Scenario: Mil report
- **GIVEN** the authored `tests/data/kicad/drc/report_mils.json`, whose first item is at x 100 and y 0
- **WHEN** `read_drc_report` reads it
- **THEN** that item has `position == Point(2_540_000, 0)`

#### Scenario: Non-strict number rejected
- **GIVEN** `report_mm.json` with one coordinate replaced by `NaN`
- **WHEN** `read_drc_report` reads it
- **THEN** `FormatError` is raised

#### Scenario: Missing required key
- **GIVEN** `report_mm.json` without `coordinate_units`
- **WHEN** `read_drc_report` reads it
- **THEN** `FormatError` is raised naming `coordinate_units`

#### Scenario: Ignored checks tolerated
- **GIVEN** `report_mm.json` with `"ignored_checks": [{"key": "silk_overlap", "description": "x"}]`
- **WHEN** `read_drc_report` reads it
- **THEN** `report.ignored_checks == ("silk_overlap",)`
