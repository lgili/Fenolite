# altium-pcb-writer Specification

## Purpose
Write the Altium PCB library (`.PcbLib`) and PCB document (`.PcbDoc`) from the model as pure functions that return bytes: units and record framing, the layer map, the pad, line and arc records of a footprint, the library and document files in the form Altium saves, component placement, and the links and nets that let a change order match the schematic. `kicad-cli` converts both files back as an oracle of what KiCad's importer reads; what Altium does with them is settled only by the maintainer's author reports.
## Requirements
### Requirement: PCB units and record framing
`backends.altium.pcbrecords` SHALL hold the units and the framing shared by the PCB library and the PCB document (S-0002, S-0150, S-0160, S-0162).
- `to_units(nm)` MUST return `nm · 50 / 127` (1/10 000 mil, 2.54 nm) rounded half away from zero, as an int32; a value outside the int32 range MUST raise `ValueError`. Every length, position and size written in a binary record MUST pass through it.
- `mil_text(units)` MUST return the length in mils as a decimal with at most four decimals, trailing zeros and a trailing point removed, followed by `mil` (`10000000` gives `1000mil`, `3937008` gives `393.7008mil`). Every length written in property text MUST use it.
- `string_block(text)` MUST return a 32-bit little-endian length, then one length byte and the 7-bit ASCII text; texts that `ascii.text_problem` refuses or that exceed 255 bytes MUST raise `ValueError`.
- `property_block(fields)` MUST return c0033's `binary.frame_record(fields)`.
- Angles MUST be written as IEEE-754 doubles in degrees, counter-clockwise, computed from microdegrees or from exact coordinates with `decimal` and converted to a double once with `float(Decimal)`. No `math` trigonometric function may produce a written value.
- The common prefix of a track, arc and pad geometry MUST be: layer byte, two flag bytes, net index, polygon index `0xFFFF`, component index (all uint16, `NO_INDEX = 0xFFFF` for none), then `FF FF FF FF`. The flag bytes MUST be `0x0C 0x00` (unlocked) for every item but a locked free track, arc or via of a record kind in `pcbrecords.LOCK_WRITTEN`, whose flag bytes MUST be `0x08 0x00`: bit 2 of the first byte clear, every other bit as in the unlocked form ("Locked copper records").
- `pcbrecords.EVIDENCE` MUST be `INFERRED` and name every `H-A-PCB-*` row this change registers.

#### Scenario: Units
- **WHEN** `to_units` is called with `0`, `254`, `1000000`, `-1000000` and `127`
- **THEN** it returns `0`, `100`, `393701`, `-393701` and `50`

#### Scenario: Mil text
- **WHEN** `mil_text` is called with `10000000`, `3937008` and `-5`
- **THEN** it returns `1000mil`, `393.7008mil` and `-0.0005mil`

#### Scenario: Angles do not depend on the platform
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcbrecords.py -k angle` runs the arc of start (−0.29, −1.08) mm, mid (1.27, −1.65) mm and end (2.83, −1.08) mm
- **THEN** the start and end angles equal the doubles pinned in the test, computed once with `decimal` at 40 digits, and no module of `backends/altium` imports a trigonometric function of `math`

#### Scenario: Flag bytes of a locked track
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcbrecords.py -k locked` builds the same track record with `locked=False` and with `locked=True`, `track` being in `LOCK_WRITTEN`
- **THEN** the two records differ in one byte, the first flag byte, `0C` against `08`

### Requirement: PCB layer map
`pcbrecords.LAYER_MAP` SHALL map Fenolite layer names to Altium layer ids, and `pcbrecords.FLIP_PAIRS` SHALL give each mapped id its other-side id (S-0002, S-0160, S-0161).

| Fenolite layer | Altium id | Altium name |
|---|---|---|
| `F.Cu` | 1 | Top Layer |
| `B.Cu` | 32 | Bottom Layer |
| `F.SilkS` | 33 | Top Overlay |
| `B.SilkS` | 34 | Bottom Overlay |
| `F.Fab` | 69 | Mechanical 13 |
| `B.Fab` | 70 | Mechanical 14 |
| `F.CrtYd` | 71 | Mechanical 15 |
| `B.CrtYd` | 72 | Mechanical 16 |

- A through-hole or non-plated pad MUST be on id 74 (Multi-Layer). An SMD pad MUST be on 1 or 32, by its copper layer.
- `FLIP_PAIRS` MUST pair 1 and 32, 33 and 34, 69 and 70, 71 and 72; 74 is its own pair.
- A layer outside the table has no Altium id; the mechanical choices are Fenolite's (`docs/altium.md`) and are not checked by any oracle.

#### Scenario: Map and pairs
- **WHEN** the map is read and every mapped id is flipped twice
- **THEN** the eight rows above hold, and each id comes back to itself

### Requirement: Footprint pad records
`pcbrecords.pad_record(...)` SHALL write one pad as the six subrecords of record type 2 (S-0150, S-0160, S-0161, S-0143).
- Subrecord 1 MUST hold the pad number as a short string, its length exactly 1 + the text's length. Subrecords 2 to 4 MUST hold the bytes `00`, the short string `|&|0` and `00` (S-0150).
- Subrecord 5 MUST be 114 bytes: the prefix; x, y; top, middle and bottom size equal to the pad size; hole size (the drill, 0 for SMD); top, middle and bottom shape; rotation; plated (1 only for `thru_hole`); pad mode 0; the values S-0150 writes at offsets 63 to 85; for a pad without its own margins the mask expansions 0, paste mode 0 and solder mode 1, and for a pad with `Pad.mask_margin` solder mode 2 with the margin as the solder-mask expansion, with `Pad.paste_margin` paste mode 2 with the margin as the paste expansion (change c0440; a connector pad keeps modes 0); the int32 at 106 and the bytes 110 to 113 zero.
- Shapes: `circle` and `oval` MUST be shape 1 (round; an oval has unequal sizes), `rect` shape 2, `roundrect` shape 1 with subrecord 6.
- Subrecord 6 MUST be empty, except for a `roundrect` pad: 596 bytes, every inner size equal to the pad size, every inner shape 1, hole shape 0, no slot, zero offsets, the rounded-rectangle flag 1, every alternate shape 9 and every corner percentage `round(200 · ratio)` clamped to 0 … 100, where `ratio` is the pad's corner ratio (`H-A-PCB-PAD`).
- The pad rotation MUST be the pad angle in degrees; KiCad's and Altium's positive angles both turn counter-clockwise on screen (`H-G-ROT-DIR`).

#### Scenario: Roundrect pad
- **WHEN** a `roundrect` pad `1` of 0.9 × 0.95 mm at (−0.8, 0) mm with ratio 0.25 is written
- **THEN** the test decoder reads subrecord 5 of 114 bytes with shape 1, sizes 354331 × 374016, x −314961 and y 0, and subrecord 6 of 596 bytes with alternate shape 9 and percentage 50

#### Scenario: Through-hole pads
- **WHEN** the mini LED footprint's pads are written
- **THEN** both are on layer 74 with hole size 354331 and plated 1, pad `1` has shape 2 and pad `2` shape 1, and both have an empty subrecord 6

#### Scenario: A pad's own margin is a manual expansion
- **GIVEN** the KiCad board converted from `tests/data/altium/blink`, whose pads are given a `solder_mask_margin` of 0.05 mm, the first of 0
- **WHEN** `uv run pytest tests/unit/convert/test_pad_mask_c0440.py` converts it to Altium and back to KiCad
- **THEN** each written pad holds solder mode 2 with the expansion 19685 or 0, and the KiCad board read again holds the same margins

### Requirement: Footprint line and arc records
Footprint graphics SHALL be written as tracks (type 4) and arcs (type 1) (S-0150, S-0160).
- A track MUST be one subrecord of 36 bytes: the prefix, x1, y1, x2, y2, width, a zero uint16 and a zero byte.
- An arc MUST be one subrecord of 47 bytes: the prefix, centre x and y, radius, start and end angle, width and a zero uint16 (`H-A-PCB-GRAPHICS`; a 45-byte arc is refused by KiCad).
- A `line` MUST give one track. A `rect` that is not filled MUST give four tracks, corner to corner in the order start, (end.x, start.y), end, (start.x, end.y). A `circle` that is not filled MUST give one arc from 0 to 360 degrees with the radius `|end − center|`. An `arc` MUST give one arc whose centre is computed exactly from its start, mid and end, rounded once, and whose angles run counter-clockwise from start to end in the Y-up frame: when the three points turn clockwise there, start and end swap.
- `pcbrecords.arc_from_points(start, mid, end)` MUST raise `ValueError` for collinear points.

#### Scenario: Silkscreen arcs of the mini LED
- **WHEN** the two `F.SilkS` arcs of the mini LED footprint are written and decoded
- **THEN** both arcs have layer 33 and width 0.12 mm, each centre has X 1.27 mm within 2.54 nm, each radius equals the distance from the centre to the arc's KiCad start, mid and end within 2.54 nm, and each arc's angular span contains its KiCad mid point

#### Scenario: Rectangle and circle
- **WHEN** the `F.CrtYd` rectangle and the `F.Fab` circle of the mini LED footprint are written
- **THEN** the rectangle gives four tracks on layer 71 that close, and the circle one arc on layer 69 from 0 to 360 degrees

### Requirement: Footprint content checks
`pcblib.check_footprint(defn, extras)` SHALL return a `FootprintCheck` that refuses the footprint, or lists what is dropped. `extras` maps each pad id to a `pcblib.PadExtras(corner_ratio, refusal, dropped)` that `lens.altium.pad_extras` builds from the KiCad children the model keeps opaque.
- The footprint MUST be refused, with the reason, when: a pad has shape `trapezoid` or `custom`, kind `connect`, or a padstack; a through-hole pad has no drill (a slot), a drill offset, or copper on only one side; a pad has chamfered corners; a `roundrect` pad has no corner ratio; a pad number or the footprint name fails `ascii.text_problem` or exceeds 255 bytes; or a graphic lies on a copper layer.
- The check MUST list as dropped: `polygon` graphics, filled `rect` and `circle` graphics, graphics on layers outside `LAYER_MAP`, and the pad settings in `PadExtras.dropped` (solder mask and paste margins, zone connection, thermal settings, a missing paste or mask layer).
- Texts, properties and 3D model links of the footprint MUST be listed as extras, not as dropped primitives.
- A refused footprint MUST NOT be written; a dropped item MUST NOT be written.

#### Scenario: Refused pad shapes
- **GIVEN** footprints with one `trapezoid` pad, one `custom` pad, one oval-drilled through-hole pad, and one `roundrect` pad without ratio
- **WHEN** each is checked
- **THEN** each is refused with a reason that names the pad

#### Scenario: Dropped polygon
- **GIVEN** a footprint with a `polygon` on `F.SilkS` and a line on `Dwgs.User`
- **WHEN** it is checked and written
- **THEN** both are listed as dropped, and the written footprint holds only its pads and other graphics

### Requirement: PCB library name
`backends.altium.project.pcblib_name(link, *, design)` SHALL give the PCB library file of a footprint link, as c0034's `schlib_name` gives the schematic library of a lib id.
- It MUST return the link's library part when it ends with `.PcbLib` in any letter case (an Altium link), and `<design>.PcbLib` otherwise (a KiCad footprint link), where `<design>` is the design name. All KiCad footprints of a design therefore share one library, beside c0034's `<design>.SchLib`.
- A link that is not `<library>:<name>` with both parts non-empty MUST raise `ValueError`; the build reports c0032's `altium.footprint-form` first.

#### Scenario: Names
- **WHEN** `pcblib_name("Mini:Mini_R_0603", design="blink")`, `pcblib_name("FenoliteSample.PcbLib:R0603", design="blink")` and `pcblib_name("My.pcblib:X", design="blink")` are called
- **THEN** they return `blink.PcbLib`, `FenoliteSample.PcbLib` and `My.pcblib`

### Requirement: PCB library file
`pcblib.write_pcblib(footprints, *, filename="Fenolite.PcbLib")` SHALL return the bytes of one PCB library holding the given `pcblib.LibFootprint` values, as a compound file built with c0034's `cfb.Storage`, in the form Altium Designer saves (S-0145, S-0150, S-0162, S-0170, S-0171, S-0173). `filename` is the library's file name without a folder; a name with `/` or `\`, or one that `text_problem` refuses, MUST raise `ValueError`.
- The root MUST hold, in this order: `FileHeader`; `SectionKeys` only when a storage name differs from its footprint name; the storage `Library`; then one storage per footprint, in the MS-CFB order of storage names.
- `FileHeader` MUST hold 53 bytes: `PCB 6.0 Binary Library File` after a uint32 and a length byte that both hold 27, the double 5.01, then `project.unique_id("pcblib:<filename>")` after a uint32 and a length byte that both hold 8.
- `Library` MUST hold `Header` (uint32 1), `Data`, `EmbeddedFonts` (uint32 0), the storages `Models`, `ModelsNoEmbed` and `Textures` (each `Header` uint32 0 and an empty `Data`), `ComponentParamsTOC` (`Header` uint32 1; `Data` one block of a uint32 length, per footprint the line `Name=<name>|Pad Count=<pads>|Height=0|Description=<description>` ended by CR LF, and a final NUL that the length counts) and `PadViaLibrary` (`Header` uint32 0; `Data` one property block `PADVIALIBRARY.LIBRARYID=<libboard.guid("padvia:<filename>")>`, `PADVIALIBRARY.LIBRARYNAME=<Local>`, `PADVIALIBRARY.DISPLAYUNITS=1`).
- `Library/Data` MUST hold one property block, the board record `libboard.board_text(filename, used_layers)` framed by `pcbrecords.text_block` (a uint32 length of up to 2^24 - 1, the text, one NUL), then a uint32 footprint count, then each footprint name as a string block, in the storage order. The block MUST NOT hold `HEADER` or `WEIGHT`.
- `libboard.board_records` MUST return 25 lines of fields, every line after the first starting with `RECORD=Board`; `board_text` MUST join the lines' `|KEY=VALUE` texts with one CR (0x0D), and `board_fields` MUST give the fields of all lines in order. They are the 2044 fields of `docs/formats/altium/pcb-library.md`, "The board record of `Library/Data`", in that order: the file keys (`FILENAME`, `KIND=Protel_Advanced_PCB_Library`, `VERSION=3.00`, `DATE=2000-01-01`, `TIME=00:00:00`), the `V9_MASTERSTACK`, `V9_STACK_LAYER<0…8>` and `V9_CACHE_LAYER<0…101>` keys, the `LAYERMASTERSTACK_V8` and `LAYER_V8_<0…55>` keys, the numbered `LAYER<1…82>` keys five layers at a time with `RECORD=Board` before each later group, `LAYERV7_<0…15>`, the grid, five layer sets, the 2D view keys (their `RECORD=Board` alone opens no line; `2DCONFIGURATION` repeats that group as one value), and `BOARDVERSION=5.01` with four empty GUID keys last. Mechanical 13 to 16 MUST be the enabled mechanical layers; `USEDBYPRIMS` MUST be `TRUE` exactly for the layers of `used_layers` (the layer bytes of the written primitives); every GUID MUST be `libboard.guid(<key>)`, the first 16 bytes of the SHA-256 of `fenolite.altium.guid:<key>`, one per layer in every list.
- Each footprint storage MUST hold `Header` (uint32 primitive count), `Parameters` (property block `PATTERN=<name>`, `HEIGHT=0mil`, `DESCRIPTION=<description>` (empty when there is none or `text_problem` refuses it), `ITEMGUID=` and `REVISIONGUID=`), `WideStrings` (an empty property block), `Data` (the name as a string block, then the pads in definition order, then the tracks and arcs in graphic order) and the storage `UniqueIDPrimitiveInformation` with `Header` (count) and `Data` (one property block per primitive: `PRIMITIVEINDEX=<i>`, `PRIMITIVEOBJECTID=<Pad|Track|Arc>`, `UNIQUEID=<project.unique_id("pcblib:<name>:<i>")>`).
- Storage names MUST come from c0034's `project.storage_name`. `SectionKeys` MUST hold a uint32 count, then per keyed footprint its full name (uint32 block length, NUL-terminated text) and its storage name (a string block) (S-0150; `H-A-PCB-LIB-NAME`). Two footprints with equal storage names under the MS-CFB order MUST raise `ValueError`.
- Nothing else is written: no `FileVersionInfo` and no `LayerKindMapping` (`H-A-PCB-LIB-OPEN`).
- The bytes MUST depend only on `footprints` and `filename`. The build MUST pass `<name>.PcbLib` as `filename`.

#### Scenario: Library of the mini footprints
- **WHEN** the three mini footprints are written and read with `tests/_altium_pcb_read.py`
- **THEN** `Library/Data` lists their three names, `ComponentParamsTOC` lists the same names with their pad counts, each storage's `Parameters` holds its `PATTERN`, each `Header` equals its decoded primitive count, and no `SectionKeys` stream exists

#### Scenario: Library header and side streams
- **WHEN** one mini footprint is written as `a.PcbLib`, again as `a.PcbLib` and as `b.PcbLib`, and read with `tests/_altium_pcb_read.py`
- **THEN** `FileHeader` holds 53 bytes, the two `a.PcbLib` libraries hold the same unique id and `PadViaLibrary` block and `b.PcbLib` other ones, and the board record's `FILENAME` is `a.PcbLib`

#### Scenario: Board record
- **WHEN** `Mini_R_0603` is written and read
- **THEN** the block of `Library/Data` is longer than 65 535 bytes with type 0 in its length word, holds 2044 fields in 25 lines and no `HEADER` or `WEIGHT`, and marks as used exactly the four layers of the footprint's primitives

#### Scenario: Library without footprints
- **WHEN** no footprint is written
- **THEN** the library reads back with no name, `ComponentParamsTOC/Data` is the block of the NUL alone, and no layer is marked as used

#### Scenario: Long name
- **WHEN** a footprint named with 43 characters is written
- **THEN** its storage name has 31 characters, `SectionKeys` maps the full name to it, and `Parameters` holds the full name as `PATTERN`

### Requirement: PCB document file
`pcbdoc.write_pcbdoc(spec, *, filename="Fenolite.PcbDoc")` SHALL return the bytes of one PCB document for a `pcbdoc.PcbDocSpec`, as a compound file in the form Altium saves (`docs/formats/altium/pcb-document.md`, "The document as Altium saves it"; S-0143, S-0150, S-0160, S-0161, S-0172, S-0174, S-0175, S-0176). `filename` is the document's file name without a folder; `project.write_project` passes `<name>.PcbDoc`.
- The root MUST hold `FileHeader` (uint32 19, then the first ten characters of `PCB 5.0 Binary File` in UTF-16LE), `FileHeaderSix` (uint32 19, the short string `PCB 6.0 Binary File`, the double 5.01, then uint32 38, a length byte 38 and `libboard.guid("pcbdoc:<the components' unique ids joined by commas>")`), and 42 storages, each with `Header` (uint32) and `Data`: the record storages `Board6`, `Nets6`, `Components6`, `Pads6`, `Tracks6`, `Arcs6`, `Texts6`, `WideStrings6` and `UniqueIDPrimitiveInformation` (`Header` the record count), the four of `pcbdoc.COPPER_STORAGES` (`Vias6`, `Polygons6`, `Classes6` and `Rules6`: `Header` the record count, and an empty `Data` when the spec holds no such object), the eight of `pcbdoc.OPTION_STORAGES` and the 21 of `pcbdoc.EMPTY_STORAGES` (`Fills6`, `Regions6`, `ShapeBasedRegions6`, `Dimensions6`, `ComponentBodies6`, `ShapeBasedComponentBodies6`, `DifferentialPairs6`, `Connections6`, `FromTos6`, `Textures`, `Embeddeds6`, `Coordinates6`, `Models`, `ModelsNoEmbed`, `EmbeddedBoards6`, `PinPairsSection`, `PadViaLibraryLinks`, `ExtendedPrimitiveInformation`, `WaivedViolations`, `PrimitiveParameters`, `SmartUnions`), each with `Header` 0 and an empty `Data`.
- The option storages MUST hold the fixed content of a document without rules, classes or pad templates: `Advanced Placer Options6`, `Pin Swap Options6` and `Design Rule Checker Options6` (`Header` 1, one property block starting with `RECORD=AdvancedPlacerOptions`, `RECORD=PinSwapOptions` or `RECORD=DesignRuleCheckerOptions` and the keys of the fact page); `PadViaLibrary` and `PadViaLibraryCache` (`Header` 0, one block `PADVIALIBRARY.LIBRARYID` = `libboard.guid("pcbdoc:<filename>:padvia")` or `…:padviacache`, `PADVIALIBRARY.LIBRARYNAME=<Local>`, `PADVIALIBRARY.DISPLAYUNITS=1`); `LayerKindMapping` (`Header` 1, 20 bytes: the wide string `1.0`, then two uint32 0); `ConstraintManager` (`Header` 1, the wide string `eNoDAAAAAAE=`); `SignalClasses` (`Header` 1, one block: the seven common keys with `LAYER=MULTILAYER`, `NAME=All xSignals`, `KIND=10`, `SUPERCLASS=TRUE`, `SELECTED=FALSE`, `SCHAUTOGENERATEDCLUSTER=FALSE`, `UNIQUEID`). A wide string is a uint32 byte length that counts the 2-byte NUL, then UTF-16LE and the NUL.
- `UniqueIDPrimitiveInformation/Data` MUST hold one property block per pad, in `Pads6` order: `PRIMITIVEINDEX` (the pad's position), `PRIMITIVEOBJECTID=Pad` and `UNIQUEID` = `project.unique_id("pcbdoc:<filename>:pad:<index>")`.
- `Board6/Data` MUST be one property block, the board record `docboard.board_text(filename, vertices, origin, unique_id=…, used_layers=…, stack=…)` framed by `pcbrecords.text_block`. `docboard.board_records` MUST return 27 lines of fields, every line after the first starting with `RECORD=Board`, joined with one CR by `board_text`; they are the fields of `docs/formats/altium/pcb-document.md`, "The `Board6` record", in that order (2231 for an outline of four points and two copper layers): line 1 with the seven common keys (`LAYER=UNKNOWN`), `FILENAME`, `KIND=Protel_Advanced_PCB`, `VERSION=5.01`, `DATE`, `TIME`, `ORIGINX`, `ORIGINY`, the grids, the outline as a polygon (the common keys with `LAYER=TOP`, the nine polygon keys, per vertex `KIND<k>=0`, `VX<k>`, `VY<k>`, `CX<k>`, `CY<k>`, `SA<k>`, `EA<k>`, `R<k>`, the first vertex repeated last, the thirteen closing keys), the sheet and `PLANE<n>NETNAME` for n from 1 to 16 (`(No Net)`, or the net of a plane of the stack, "Four-layer stack"); line 2 with the library's stacks (`libboard.stack_fields`) plus the sub-stack keys `V9_SUBSTACK0_…` and `LAYERSUBSTACK_V8_0…` (`ID` = `libboard.guid("substack")`, `NAME=Board Layer Stack`) and, before the `ID` of each physical-stack layer in the three lists (nine layers for two copper layers), `<prefix>_<sub-stack GUID>CONTEXT=0` and `…USEDBYPRIMS=FALSE`; the library's numbered layers 1 to 82 (for two copper layers `LAYER1NEXT=32`, `LAYER32PREV=1` and every other link 0; "Four-layer stack" gives the links and the stack of four) and `LAYERV7_` layers, the line of layers 81 and 82 ending with the five `LAYERPAIR0` keys; the routing line; the grid-factor line; the six view lines (the window is the outline's box widened by `docboard.VIEW_MARGIN`, 100 mil); and the last line with the camera, the `GR0_` snap grid, the snap options, `UNIQUEID` = `project.unique_id("pcbdoc:<filename>:board")`, `PINPAIRCOUNT=0` and the teardrop keys. `USEDBYPRIMS` of a layer MUST be `TRUE` exactly for the layers that written primitives lie on. `docboard.angle_text` MUST give an angle as a space, one digit, 14 decimals and a signed four-digit exponent (` 2.70000000000000E+0002`). `board_records` MUST raise `ValueError` for fewer than three vertices, and `format_line` for a field that is not printable 7-bit ASCII or holds `|`.
- `Nets6/Data` MUST hold one property record per net, in name order, with these 15 keys in this order: the seven common keys (`SELECTION=FALSE`, `LAYER=TOP`, `LOCKED=FALSE`, `POLYGONOUTLINE=FALSE`, `USERROUTED=TRUE`, `KEEPOUT=FALSE`, `UNIONINDEX=0`), `PRIMITIVELOCK=FALSE`, `NAME`, `VISIBLE=TRUE`, `COLOR=7709086`, `LOOPREMOVAL=TRUE`, `OVERRIDECOLORFORDRAW=FALSE`, `UNIQUEID` = `project.unique_id("pcbdoc:<filename>:net:<name>")` and `JUMPERSVISIBLE=TRUE`; a net's index is its position.
- `Components6/Data` MUST hold one property record per component, in component-path order, with these 25 keys in this order: `SELECTION=FALSE`, `LAYER` (`TOP` or `BOTTOM`), `LOCKED`, `POLYGONOUTLINE=FALSE`, `USERROUTED=TRUE`, `KEEPOUT=FALSE`, `PRIMITIVELOCK=TRUE`, `X`, `Y`, `PATTERN`, `NAMEON=TRUE`, `COMMENTON=FALSE`, `GROUPNUM=0`, `COUNT=0`, `ROTATION` (`docboard.angle_text`), `UNIONINDEX=0`, `CHANNELOFFSET` (the component's index), `SOURCEDESIGNATOR`, `SOURCEUNIQUEID`, `SOURCEHIERARCHICALPATH` (empty), `SOURCEFOOTPRINTLIBRARY`, `SOURCECOMPONENTLIBRARY`, `SOURCELIBREFERENCE`, `UNIQUEID` = `project.unique_id("pcbdoc:<filename>:component:<schematic id>")` and `JUMPERSVISIBLE=TRUE`; booleans `TRUE` or `FALSE`.
- `Texts6/Data` MUST hold, per component, a designator text and a comment text with the component index, in the long form of 137 bytes with the designator or comment flag set (`pcb-records.md`; the 252-byte form of Altium-saved documents is not written, `H-A-PCB-DOC-OPEN`), the text in the 8-bit subrecord and in `WideStrings6/Data` (uint32 index, uint32 byte length with the NUL, UTF-16LE text); a text's wide-string index MUST be its position in `Texts6`.
- `Pads6`, `Tracks6` and `Arcs6` MUST hold the component's primitives, each with its record type byte; `Tracks6` and `Arcs6` then hold the board's routed tracks and arcs ("Routed track and arc records").
- The bytes MUST depend only on `spec` and `filename`.

#### Scenario: Storages of the sample
- **WHEN** the sample's PCB document is read with `tests/_altium_pcb_read.py`
- **THEN** it holds the root streams and the 42 storages of this requirement, every `Header` equals its decoded record count or the fixed value of its option storage, and every storage of `EMPTY_STORAGES` has `Header` 0 and an empty `Data`, `Vias6` and `Polygons6` are empty too, and `Classes6` holds one record, the net class `PWR`

#### Scenario: Two-layer stack
- **WHEN** `Board6` of the sample is read
- **THEN** following `NEXT` from layer 1 gives 32, then 0, and the outline has five vertices, the last equal to the first

#### Scenario: Board record in Altium's form
- **WHEN** `Board6` of the sample is read as fields
- **THEN** it has 27 lines and 2231 fields, the first line starts with `SELECTION=FALSE` and holds `KIND=Protel_Advanced_PCB` and `VERSION=5.01`, each of the five vertices has its eight keys, and `USEDBYPRIMS` is `TRUE` exactly for the layers of the sample's pads, tracks, arcs and texts

#### Scenario: Option storages
- **WHEN** the option storages of the sample are read
- **THEN** each holds the header and the block of this requirement, and `UniqueIDPrimitiveInformation` lists the 36 pads once, in order

### Requirement: PCB document placement
`pcbdoc.write_pcbdoc` SHALL place each `pcbdoc.PlacedComponent` by the transform of `geometry.transform.Transform.placement(at, rotation, mirror=side == "bottom")`, as KiCad places a footprint (`H-G-BOTTOM-PLACE`, `H-G-BOTTOM-STORE`).
- Each pad and graphic MUST be written at absolute coordinates: the transformed point with Y negated, then shifted by the offset that puts the outline's lowest X and highest Y at (1000 mil, 1000 mil) (`pcbdoc.BOARD_OFFSET_MIL`). `ORIGINX` and `ORIGINY` MUST be that point.
- A pad's rotation MUST be `Transform.apply_angle` of its angle. Arcs MUST be rebuilt from the transformed start, mid and end.
- On the bottom side, every layer id MUST be replaced by its `FLIP_PAIRS` partner.
- Component `X`, `Y` MUST be the transformed origin, and `ROTATION` the placement angle (`H-A-PCB-DOC-BOTTOM` for the bottom side).
- The designator text MUST sit at the middle of the top edge of the component's box of pads and graphics, plus 0.5 mm, 1 mm high with a 0.15 mm stroke, on the overlay of the component's side; the comment text at the middle of the bottom edge, minus 1.5 mm.

#### Scenario: A bottom part
- **WHEN** the sample's `D1` (bottom side) is written
- **THEN** its component record holds `LAYER=BOTTOM`, its silkscreen arcs lie on layer 34 and its courtyard on 72, and every pad position equals `Transform.placement(at, θ, mirror=True)` of the footprint pad, converted as this requirement says, within 1.27 nm

### Requirement: PCB document links and nets
Each component record SHALL link to the schematic, and each pad SHALL carry its net (S-0161, S-0164, S-0139, S-0188).
- `SOURCEUNIQUEID` MUST be a backslash followed by the component's schematic `UNIQUEID` (`project.unique_id(<component id>)`); `SOURCEDESIGNATOR` its ref; `PATTERN` its footprint name; `SOURCEFOOTPRINTLIBRARY` the file name of the PCB library it comes from; `SOURCELIBREFERENCE` and `SOURCECOMPONENTLIBRARY` the schematic's `LIBREFERENCE` and `SOURCELIBRARYNAME` (`H-A-PCB-DOC-LINK`).
- For a component on a module sheet (`pcbdoc.PlacedComponent.sheet` is `(<sheet symbol UNIQUEID>, <module name>)`; `altium-schematic-writer`, "Sheets of a hierarchical project"), `SOURCEUNIQUEID` MUST instead be `\<sheet symbol UNIQUEID>\<component UNIQUEID>` and `SOURCEHIERARCHICALPATH` MUST be `<design name>\<module name>`, as Altium saves them (S-0188). For any other component `PlacedComponent.sheet` is `None`, `SOURCEUNIQUEID` keeps the one-id form and `SOURCEHIERARCHICALPATH` is empty, as c0035 writes them. That the change order matches both forms is `H-A-SCH-HIER-ECO`.
- `CHANNELOFFSET` MUST be the component's index among the components of its own sheet, in component-path order, starting at 0 on every module sheet and on the top sheet, as a saved board of a hierarchical project holds it (S-0188; `pcbdoc.channel_offsets`). In a `flat` build this is the component's index in the document, so the bytes of c0035 do not change.
- The test suite MUST read a built project back as a second program finds it (`tests/_altium_read.py`, `component_links` and `board_link_problems`): the sheets are the `.SchDoc` documents the project file lists; a sheet symbol's file-name record names its child by the exact name of a listed document; every module sheet MUST be reachable from the top sheet; and every board component's `SOURCEUNIQUEID`, designator and `SOURCEHIERARCHICALPATH` MUST be those of one schematic component. A module MUST get its sheet symbol even when no net crosses it. This readback raises no evidence label.
- A pad whose number equals a pin designator of its component on a net MUST carry that net's index; any other pad MUST carry `0xFFFF`. Every primitive MUST carry its component's index.

#### Scenario: Unique ids match the schematic
- **WHEN** the sample's schematic and PCB document are read
- **THEN** for every component, `SOURCEUNIQUEID` equals `\` followed by the `UNIQUEID` of the schematic component with the same designator

#### Scenario: Pad nets
- **WHEN** the pads of the sample's `R1` are read
- **THEN** pad `1` carries the index of `LED_DRV` and pad `2` the index of `LED_A`

#### Scenario: Link of a part on a module sheet
- **WHEN** `examples/altium_hier_board/design.py` is built with `sheets="modules"` and its PCB document and sheets are read
- **THEN** the component `D1` holds `SOURCEUNIQUEID` equal to `\`, the `UNIQUEID` of the sheet symbol `led`, `\` and the `UNIQUEID` of the schematic component `D1`, and `SOURCEHIERARCHICALPATH=altium_hier_board\led`

#### Scenario: Every board link resolves
- **WHEN** `examples/altium_hier_board/design.py` is built with `sheets="modules"` and `component_links` and `board_link_problems` read its project file, sheets and PCB document
- **THEN** there is no problem: the links of `R1` and `U1` resolve through the sheet symbol `driver` and that of `D1` through the sheet symbol `led`, both module sheets are listed in the project file and reachable from the top sheet, and `CHANNELOFFSET` is `0` and `1` on `driver` and `0` on `led`

#### Scenario: A sheet outside the hierarchy is caught
- **GIVEN** that build with the section of `altium_hier_board_led.SchDoc` removed from the project file, or with the top sheet replaced by one without sheet symbols
- **WHEN** `component_links` runs
- **THEN** it fails, naming the sheet

#### Scenario: Module without a crossing
- **GIVEN** a design of two modules whose only nets are the two nets of a `power` interface
- **WHEN** it is built with `sheets="modules"`
- **THEN** the top sheet holds one sheet symbol per module, each with its name and file name and no sheet entry, and both module sheets are reachable from the top sheet

#### Scenario: Flat links are unchanged
- **WHEN** the same example is built with `sheets="flat"`
- **THEN** every component holds `SOURCEUNIQUEID` equal to `\` and its schematic `UNIQUEID`, and an empty `SOURCEHIERARCHICALPATH`

### Requirement: PCB files read back
`tests/_altium_pcb_read.py` SHALL read PCB libraries and documents as test code that the product never imports, written from `docs/formats/altium/pcb-*.md` before the writer is read: `read_pcblib(data)`, `read_pcbdoc(data)` and `decode_primitives(data)`, on top of `tests/_cfb_read.py`.
- It MUST check every subrecord length against the minimums (pad subrecord 5 at least 110, subrecord 6 empty or at least 596, track 36, arc 47, text 40), that the pad name subrecord's length is 1 + its text, that every net and component index names an existing record, that `Header` counts equal decoded counts, and that every `Library/Data` name has a storage whose `Parameters` holds it as `PATTERN`.
- For a library it MUST also check the 53-byte `FileHeader` (text, the double 5.01, an id of eight upper-case letters), every `Library` stream of "PCB library file", that the board record holds `KIND=Protel_Advanced_PCB_Library`, `VERSION=3.00` and `V9_MASTERSTACK_STYLE=0` and no `HEADER` or `WEIGHT`, that `ComponentParamsTOC` lists the names of `Library/Data` with each footprint's pad count, the first five `Parameters` keys, and the spelling `UniqueIDPrimitiveInformation`. For a document it MUST check that `FileHeaderSix` ends with a 38-character GUID block. It MUST read `Board6/Data` as exactly one block of fields in order (`board_fields`; `board` keeps the first value of a repeated key), and, when the storage is present, check that `UniqueIDPrimitiveInformation` lists every pad once in `Pads6` order with `PRIMITIVEOBJECTID=Pad`, that each property option storage holds exactly one block with its `RECORD` and its fixed `Header`, that `LayerKindMapping` is the wide string `1.0` and eight zero bytes, that `ConstraintManager` is one wide string and nothing more, and that a storage it does not know holds no data.

#### Scenario: Negative controls
- **WHEN** the reader gets a library whose pad subrecord 5 has 100 bytes, an arc of 45 bytes, a footprint without `Parameters`, a `FileHeader` of 32 bytes, a board record of `HEADER` and `WEIGHT`, no `Library/EmbeddedFonts`, a storage spelled `UniqueIdPrimitiveInformation`, a document whose `FileHeaderSix` has no id, a document whose pad names component 9 of 3, a `Board6/Data` of two blocks or of none, a `UniqueIDPrimitiveInformation` that repeats a pad, names an arc or skips an index, a `Pin Swap Options6` with another `RECORD`, two blocks or `Header` 0, a `LayerKindMapping` with a four-byte tail, a `ConstraintManager` that is not a wide string or has a tail, and an unknown storage with data
- **THEN** each read raises an error that names the broken rule

### Requirement: PCB library oracle
`tests/kicad/altium/test_pcblib_oracle.py` SHALL convert the sample's PCB library with `kicad-cli fp upgrade <lib>.PcbLib -o <dir>.pretty` and compare it with the source footprints (S-0166, S-0020).
- The exit code MUST be 0 and the folder MUST hold exactly one `.kicad_mod` per written footprint: exit 0 alone proves nothing.
- Each converted footprint, read with Fenolite's footprint reader, MUST match its source: pad numbers, kinds, shapes, sizes, positions, rotations and drills within 10 nm and 1 microdegree, corner ratios within 0.005; tracks and arcs as segments and arcs of the same geometry within 10 nm, on the layer the map gives back (Mechanical n as `User.n`).
- The test MUST run where `kicad-cli` is present and be required in the `kicad-10` and `kicad-9` jobs. A pass on 10.0.6 gives `H-A-PCB-KICAD-LIB` the level `ORACLE-VERIFIED(kicad-cli)`; the 9.0.9 result is recorded on that row.

#### Scenario: Round trip of the mini footprints
- **WHEN** `uv run pytest tests/kicad/altium/test_pcblib_oracle.py` runs with `kicad-cli` 10.0.6
- **THEN** three `.kicad_mod` files are written and each matches its source footprint

### Requirement: PCB document oracle
`tests/kicad/altium/test_pcbdoc_oracle.py` SHALL import the sample's PCB document with `kicad-cli pcb import --format altium --report-format json --report-file <r>.json -o <out>.kicad_pcb <doc>.PcbDoc` and compare it with the design (S-0161, S-0166).
- The exit code MUST be 0, the report's `errors` empty, `statistics.footprints` equal to the component count, and stdout MUST hold no line that starts with `Error:`. Warnings MUST be only those listed in `pcb-document.md` (layers KiCad does not map).
- The imported board, read with Fenolite's board reader, MUST give: the same references; per pad the same net name; pad positions relative to the first component's origin equal to the design's within 10 nm; four outline segments; copper layers named "Top Layer" and "Bottom Layer".
- The test MUST be skipped on `kicad-cli` 9.x with the reason "no `pcb import` before 10.0" and required in the `kicad-10` job. A pass on 10.0.6 gives `H-A-PCB-KICAD-DOC` the level `ORACLE-VERIFIED(kicad-cli)`.

#### Scenario: Import of the sample
- **WHEN** `uv run pytest tests/kicad/altium/test_pcbdoc_oracle.py` runs with `kicad-cli` 10.0.6
- **THEN** the board has `U1`, `R1` and `D1` with their nets, `D1` on the bottom, and no error in the report or on stdout

### Requirement: Copper layer map
`pcbrecords.LAYER_MAP` SHALL also map the inner copper layers of a four-layer board as signal layers, `pcbrecords.layer_text` SHALL give the layer text of a copper layer id in a property record (`TOP`, `MID<n>`, `BOTTOM`, `PLANE<n>`), and `pcbrecords.copper_stack` SHALL give the Altium ids of a stack whose inner layers are signal layers or internal planes, by position (change c0085) (S-0002, S-0160, S-0176, S-0199, S-0200). This requirement extends c0035's "PCB layer map", whose eight rows and pairs hold unchanged.

| Fenolite layer | as | Altium id | Altium name | layer text |
|---|---|---|---|---|
| `F.Cu` | signal | 1 | Top Layer | `TOP` |
| `In1.Cu` | signal | 2 | Mid-Layer 1 | `MID1` |
| `In2.Cu` | signal | 3 | Mid-Layer 2 | `MID2` |
| `B.Cu` | signal | 32 | Bottom Layer | `BOTTOM` |
| first inner layer that is a plane | plane | 39 | Internal Plane 1 | (no primitive is written on it) |
| second inner layer that is a plane | plane | 40 | Internal Plane 2 | (no primitive is written on it) |
| k-th inner layer of any stack | signal | k + 1 | Mid-Layer k | `MID<k>` |
| p-th inner layer that is a plane | plane | 38 + p | Internal Plane p | (no primitive is written on it) |

- `pcbrecords.copper_stack(names, planes=())` MUST return the Altium ids of a board's copper layers from top to bottom. `names` are the model's copper layers in stack order, distinct, an even count that "Layer stacks of any even count" allows: the first is the top layer (1), the last the bottom layer (32); `planes` MUST name only inner layers of `names`, without repeats. Any other input MUST raise `ValueError` naming it.
- A signal inner layer keeps its row of the table whatever the other inner layers are: the k-th inner layer is Mid-Layer k, whatever its name. Planes are numbered from the top: the first plane is Internal Plane 1, the second Internal Plane 2. So Mid-Layer 2 may be written without Mid-Layer 1, a state Altium saves (S-0200).
- `LAYER_MAP` and `COPPER_LAYER_TEXT` MUST NOT hold a plane: a primitive on a plane layer has no id (`ValueError`).
- No inner layer has a flip partner: `FLIP_PAIRS` MUST stay as c0035 wrote it.

#### Scenario: Four signal layers
- **WHEN** `pcbrecords.copper_stack(("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"))` runs
- **THEN** it returns `(1, 2, 3, 32)`

#### Scenario: Planes numbered from the top
- **WHEN** `copper_stack` runs for the four layers with `planes=("In1.Cu",)`, with `planes=("In2.Cu",)` and with `planes=("In1.Cu", "In2.Cu")`
- **THEN** it returns `(1, 39, 3, 32)`, `(1, 2, 39, 32)` and `(1, 39, 40, 32)`

#### Scenario: Other stacks refused
- **WHEN** `copper_stack` gets `("F.Cu", "In1.Cu", "B.Cu")`, `("F.Cu", "In1.Cu", "In1.Cu", "B.Cu")`, `planes=("F.Cu",)` with four layers, or `planes=("In1.Cu",)` with two layers
- **THEN** each call raises `ValueError` that names the input

### Requirement: Four-layer stack
`docboard.board_records(..., stack=…)` SHALL write the layer stack of a `docboard.StackSpec` with any even number of copper layers that "Layer stacks of any even count" allows (change c0085; two or four before it), each inner layer a signal layer or an internal plane with a net (`docs/formats/altium/pcb-copper.md`, "Layer stack"; S-0160, S-0176, S-0199, S-0200; `H-A-PCB-CU-STACK`, `H-A-PCB-CU-PLANE`).
- `StackSpec` MUST hold `copper` (the Altium ids from top to bottom, as `copper_stack` gives them), one copper thickness per layer, one `Dielectric(kind, thickness, epsilon_r, material)` between each pair of neighbours (`kind` is `unspecified`, `core` or `prepreg`; lengths in nanometres), and `plane_nets`, one net name per plane of `copper`, in plane order. A `plane_nets` whose length differs from the number of planes, or a net name that fails `text_problem`, MUST raise `ValueError`.
- `StackSpec.default(copper, plane_nets=())` MUST give 1.4 mil copper and, for two layers, the dielectric of c0035 (`unspecified`, 12.6 mil, `4.800`, `FR-4`); for four layers a prepreg of 0.2 mm, a core of 1.0 mm and a prepreg of 0.2 mm, each `4.800` and `FR-4`; for more layers prepregs of 0.2 mm and cores in turn, the outermost a prepreg, the cores sharing 1.0 mm. These values are Fenolite's choices.
- For two copper layers and the default stack, the record MUST equal the record of c0035 byte for byte.
- For four or more copper layers the numbered keys MUST link the ids of `copper` in order through `LAYER<id>PREV` and `LAYER<id>NEXT` (0 before the first and after the last); every other copper link stays 0. Each linked layer MUST carry its `COPTHICK`, and each but the bottom the dielectric below it (`DIELTYPE`, `DIELCONST`, `DIELHEIGHT`, `DIELMATERIAL`).
- The physical stack of the `V9_STACK_LAYER<i>` list and the head of the `LAYER_V8_<i>` list MUST hold 13 layers: paste, overlay, solder, `Top Layer`, `Dielectric 1`, the first inner layer, `Dielectric 2`, the second inner layer, `Dielectric 3`, `Bottom Layer`, solder, overlay, paste. The dielectrics MUST have the long ids 17039361, 17039362 and 17039363 from the top (the numbering S-0199 saves). A stack of more layers MUST grow by one dielectric and one copper entry per inner layer, `Dielectric n` with the long id 17039360 + n.
- A **signal** inner layer MUST be written as S-0199 and S-0200 save it: `NAME` (`Mid-Layer <n>`), `LAYERID` (16777217 + n), `USEDBYPRIMS`, `COPTHICK` and `COMPONENTPLACEMENT=1`.
- A **plane** MUST be written as S-0176 saves it: `NAME` (`Internal Plane <k>`), `LAYERID` (16842752 + k), `USEDBYPRIMS`, `COPTHICK` and `PULLBACKDISTANCE=20mil`; and line 1 of the record MUST hold `PLANE<k>NETNAME=<net name>`. Every other `PLANE<n>NETNAME` stays `(No Net)`.
- No primitive is written for a plane: no `Split Plane` polygon record, no pull-back track and no region (`H-A-PCB-CU-PLANE`); its `USEDBYPRIMS` is `FALSE`. Split planes are not written.
- The cache list MUST hold every layer once, in the form S-0176 saves (found when the written stack was compared with it, 2026-10-03): the 102 layers of a two-layer document in their order, then `Dielectric 2` and `Dielectric 3` (and the further dielectrics of a larger stack). A mid layer or a plane of the stack keeps its place in its run and carries its stack keys.
- `pcbdoc.write_pcbdoc` MUST take the stack from `PcbDocSpec.stack` (`None` is `StackSpec.default` for `PcbDocSpec.copper_layers` without planes) and MUST raise `ValueError` when `stack.copper` does not hold one id per name of `copper_layers`, or when a plane's net is not in `PcbDocSpec.nets`.
- `DIELTYPE` MUST be 0 for `unspecified`, 1 for `core` and 2 for `prepreg`; `DIELCONST` three decimals; `DIELHEIGHT` and `COPTHICK` mil text.
- The layer set `&Signal Layers` MUST also list the signal inner layers (`MidLayer1`, `MidLayer2`), `&Plane Layers` the planes (`InternalPlane1`, `InternalPlane2`), and `&All Layers` both. The first drill pair stays `LAYERPAIR0LOW=TOP`, `LAYERPAIR0HIGH=BOTTOM`; "Blind and buried via records" adds one pair per span of a blind or buried via.
- A stack with one signal inner layer and one plane is composed from the two entry forms; no saved document with such a stack was read, and the fact page MUST say so on its row.

#### Scenario: Two layers keep their bytes
- **WHEN** `docboard.board_text` runs for the blink outline with `stack=StackSpec.default((1, 32))` and without `stack`
- **THEN** both texts are equal, and equal to the text c0035's test pins

#### Scenario: Chain of four signal layers
- **WHEN** `Board6` of the routed sample is read with `tests/_altium_pcb_read.py`
- **THEN** following `NEXT` from layer 1 gives 2, 3, 32, then 0; `V9_STACK_LAYER4_NAME` is `Dielectric 1`, `V9_STACK_LAYER5_LAYERID` is `16777218` and `V9_STACK_LAYER5_COMPONENTPLACEMENT` is `1`; and the record has 27 lines

#### Scenario: Ground plane under the top layer
- **WHEN** `board_fields` runs with `StackSpec.default((1, 39, 3, 32), plane_nets=("GND",))`
- **THEN** following `NEXT` from layer 1 gives 39, 3, 32, then 0; `PLANE1NETNAME` is `GND` and `PLANE2NETNAME` is `(No Net)`; `V9_STACK_LAYER5_NAME` is `Internal Plane 1` with `LAYERID=16842753` and `PULLBACKDISTANCE=20mil` and without `COMPONENTPLACEMENT`; `V9_STACK_LAYER7_NAME` is `Mid-Layer 2`; and the layer set `&Plane Layers` is `InternalPlane1`

#### Scenario: Two planes
- **WHEN** `board_fields` runs with `StackSpec.default((1, 39, 40, 32), plane_nets=("GND", "VIN"))`
- **THEN** the chain is 1, 39, 40, 32; `PLANE1NETNAME` is `GND` and `PLANE2NETNAME` is `VIN`; `&Signal Layers` lists no mid layer; and the cache list names `Internal Plane 1` and `Internal Plane 2` once each, with `PULLBACKDISTANCE`

#### Scenario: Dielectric values from the spec
- **WHEN** `board_fields` runs with a four-layer `StackSpec` whose core is 0.71 mm of `4.5`
- **THEN** `V9_STACK_LAYER6_DIELHEIGHT` is `27.9528mil`, `V9_STACK_LAYER6_DIELCONST` is `4.500` and `V9_STACK_LAYER6_DIELTYPE` is `1`

#### Scenario: Plane without a net refused
- **WHEN** `StackSpec.default((1, 39, 3, 32))` is built without `plane_nets`
- **THEN** it raises `ValueError` naming Internal Plane 1

### Requirement: Routed track and arc records
`pcbdoc.write_pcbdoc` SHALL write each `model.board.Track` and `Arc` of `PcbDocSpec.tracks` and `PcbDocSpec.arcs` as a free primitive with its net (S-0160, S-0150; `H-A-PCB-CU-TRACK`).
- A track MUST be `pcbrecords.track_record` (36 bytes) and an arc `pcbrecords.arc_record` (47 bytes) from `arc_from_points`, on the Altium id of its layer, with the index of its net in `Nets6` (`0xFFFF` without a net; in a `PcbDocSpec`, the `net_id` of a track, arc, via or zone holds the net's **name**, which the lens puts there), polygon index `0xFFFF` and component index `0xFFFF`.
- Points are in the board frame of the placements. They MUST be converted as c0035's "PCB document placement" converts a placed point: Y negated and shifted by the outline's offset, then `to_units`.
- Routed records MUST follow the component primitives in `Tracks6` and `Arcs6`, sorted by stack position of the layer, net name, start, end, width and then entity id, so the order does not depend on where the copper came from.
- A layer outside `PcbDocSpec.copper_layers`, a layer that `PcbDocSpec.stack` writes as a plane, a width of 0 or less, a track of zero length, or a net name that `PcbDocSpec.nets` does not hold MUST raise `ValueError` that names the entity id.
- The 49- and 60-byte forms that Altium saves are not written (`pcb-copper.md`).

#### Scenario: Track on an inner layer
- **GIVEN** a spec with four copper layers and a track on `In1.Cu` from (10, 10) mm to (30, 10) mm, 0.2 mm wide, on the net `SIG`
- **WHEN** the document is read with `tests/_altium_pcb_read.py`
- **THEN** `Tracks6` ends with one track on layer 2 with the index of `SIG`, component `0xFFFF`, width 78740 units, and a length of 7874016 units along X within one unit

#### Scenario: Unknown layer refused
- **WHEN** a spec with two copper layers holds a track on `In1.Cu`
- **THEN** `write_pcbdoc` raises `ValueError` naming the track's id and `In1.Cu`

### Requirement: Via records
`pcbrecords.via_record(x, y, diameter, hole, *, net=NO_INDEX, start=1, end=32, locked=False, tented_top=False, tented_bottom=False, mask=None)` SHALL write one via as record type 3 with one subrecord of 321 bytes, the form Altium saves (S-0150, S-0160, S-0173, S-0172, S-0174, S-0175, S-0176; `H-A-PCB-CU-VIA`).
- The subrecord MUST start with the common prefix on layer 74 with flags `0C 00`, or `08 00` for a locked via when `via` is in `LOCK_WRITTEN` ("PCB units and record framing", "Locked copper records"), polygon and component `0xFFFF`; then x at 13, y at 17, the diameter at 21, the hole at 25, the start layer at 29 and the end layer at 30: 1 and 32 for a through via, the ids of the two copper layers of its span for a blind or buried via (change c0085, "Blind and buried via records").
- The later fields MUST follow the rows of `pcb-copper.md`, "Via": thermal-relief air gap 10 mil at 32, 4 conductors at 36, conductor width 10 mil at 38, 20 mil at 42 and at 46, solder-mask expansion 4 mil at 54 and at 242 (`mask` in binary units when it is not `None`, change c0445), stack mode 0 at 74, thirty-two diameters at 75, the 16-bit 15 and the 32-bit 259 at 203, `2A` at 254, `0x7FFFFFFF` at 291 and at 295, the entry size 30 at 304, 9 at 308 and 1 at 320; every other byte 0.
- `pcbdoc.write_pcbdoc` MUST write each `model.board.Via` of `PcbDocSpec.vias` in `Vias6`, sorted by net name, position, diameter and then entity id, at its converted position, with its net's index and its `locked`. It MUST raise `ValueError` for a via whose `via_type` is `micro`, whose `layers` are not two different copper layers of the board, or whose drill is not below its diameter. With `PcbDocSpec.allow_full_drill` (change c0128; `False` by default, and no build sets it) a via whose drill equals its diameter MUST be written instead: the hole at 25 holds the value of the diameter at 21, and every other byte is that of any via. A drill above the diameter and a drill of 0 or less MUST be refused in both cases.
- Vias MUST NOT be listed in `UniqueIDPrimitiveInformation`.
- With `mask` not `None` (change c0445), the subrecord MUST hold `mask` at 54 and at 242 and the manual solder-mask cache state 2 at 66, as a tented side does (c0112). `pcbdoc.write_pcbdoc` MUST pass `PcbDocSpec.via_mask` (nanometres, `None` by default) converted to binary units to every via. `lower.from_design` MUST set it to `Board.mask_margin` for a write of a model (no build options) and to `None` for a build (S-2042, S-2043; the opening Altium gives is `INFERRED`).

#### Scenario: Via bytes
- **WHEN** `via_record(393701, 393701, 236220, 118110, net=2)` runs
- **THEN** the record is `03`, the length 321 and a subrecord whose bytes 0 to 4 are `4A 0C 00 02 00`, whose bytes 29 and 30 are `01 20`, and whose 32-bit values at 21, 25, 75 and 199 are 236220, 118110, 236220 and 236220

#### Scenario: Micro via refused
- **WHEN** a spec holds a via with `via_type="micro"` between `F.Cu` and `In1.Cu`
- **THEN** `write_pcbdoc` raises `ValueError` naming the via's id

#### Scenario: Blind via refused
- **WHEN** a spec holds a via with `via_type="blind"` whose two layers are both `F.Cu`, a span that is not two different copper layers of the board (a blind via with a span of two copper layers is written since change c0085, "Blind and buried via records")
- **THEN** `write_pcbdoc` raises `ValueError` naming the via's id

#### Scenario: Via with a full drill
- **GIVEN** a spec with a through via of diameter 600 000 nm and drill 600 000 nm
- **WHEN** `write_pcbdoc` runs, and again with `allow_full_drill=True`
- **THEN** the first raises `ValueError` naming the via's id, as before change c0128; the second writes one via record whose 32-bit values at 21 and 25 are both 236220, and with a drill of 600 001 nm it raises `ValueError` too

#### Scenario: Locked via bytes
- **WHEN** `via_record(393701, 393701, 236220, 118110, net=2, locked=True)` runs with `via` in `LOCK_WRITTEN`
- **THEN** bytes 0 to 4 of the subrecord are `4A 08 00 02 00`, and every other byte equals that of the unlocked record

#### Scenario: A via with its own mask expansion
- **WHEN** `via_record(0, 0, 200000, 100000, mask=-40000)` runs
- **THEN** its subrecord holds the 32-bit value -40000 at 54 and at 242 and the byte 2 at 66, while the record written without `mask` holds 40000 at 54 and 0 at 66

### Requirement: Polygon pour records
`pcbdoc.write_pcbdoc` SHALL write each `model.board.Zone` of `PcbDocSpec.zones` as one `Polygons6` property record per zone layer, with or without poured copper by its pour mode ("Polygon pour modes"; S-0160, S-0172, S-0174, S-0175, S-0176, S-0195, S-0196, S-0833; `H-A-PCB-CU-REPOUR`).

#### Scenario: Detailed contract for polygon pour records
- **WHEN** this behavior is exercised
- **THEN** the following detailed conditions MUST hold:

`pcbdoc.write_pcbdoc` SHALL write each `model.board.Zone` of `PcbDocSpec.zones` as one `Polygons6` property record per zone layer, with or without poured copper by its pour mode ("Polygon pour modes"; S-0160, S-0172, S-0174, S-0175, S-0176, S-0195, S-0196, S-0833; `H-A-PCB-CU-REPOUR`).
- A record MUST hold, in this order: the seven common keys with `LAYER` = the layer text; `PRIMITIVELOCK=TRUE`, `POLYGONTYPE=Polygon`, `POUROVER=TRUE`, `REMOVEDEAD=TRUE` (`FALSE` for a zone whose islands are never removed, change c0085), `GRIDSIZE=20mil`, `TRACKWIDTH=8mil`, `HATCHSTYLE=Solid`, `USEOCTAGONS=FALSE`, `MINPRIMLENGTH=3mil`; per vertex `KIND<k>=0`, `VX<k>`, `VY<k>`, `CX<k>`, `CY<k>`, `SA<k>`, `EA<k>`, `R<k>` as the board outline writes them, the first vertex repeated last; `SHELVED=FALSE`, `RESTORELAYER=UNKNOWN`, `RESTORENET` (empty), `REMOVEISLANDSBYAREA`, `REMOVENECKS=TRUE`, `AREATHRESHOLD`, `ARCRESOLUTION=0.5mil`, `NECKWIDTHTHRESHOLD` (change c0446: a zone whose `settings.island_removal` is `always` and whose `settings.min_thickness` is 0.25 mm, the default settings, keeps `REMOVEISLANDSBYAREA=TRUE`, `AREATHRESHOLD=250000000000.000000` and `NECKWIDTHTHRESHOLD=5mil`, the values the kit verified; any other zone gets `REMOVEISLANDSBYAREA=TRUE` only when `island_removal` is `below_area`, with `AREATHRESHOLD` its `min_island_area` in square file units, 0.0001 mil squared, six decimals rounded half to even, else `FALSE` with `250000000000.000000`, and `NECKWIDTHTHRESHOLD` its `min_thickness` as mil text), `POUROVERSTYLE=1`, `NAME`, `POURINDEX`, `IGNOREVIOLATIONS=FALSE`, `AUTONAME` (only when the name is generated), `OPTIMALVOIDROTATION` (`TRUE` with the pour mode `outline`, `FALSE` with `computed`, change c0215), and `NET` (the net's index; left out without a net).
- `NAME` MUST be the character codes of the name in decimal, joined by commas. The name is `Zone.name`, or `<net name>_L<layer position, two digits from 01>_P<pour index, three digits>` when it is empty (`NONET` stands for a missing net), in upper case, with `AUTONAME=TRUE`.
- `POURINDEX` MUST number the records from 0 in the order of falling `Zone.priority`, then net name, first outline point, zone id and stack position, so a zone of higher priority is poured first. `POURINDEX` MUST equal the record's position in `Polygons6`.
- With the pour mode `outline`, `Regions6` and `ShapeBasedRegions6` MUST hold no region of a polygon (they hold the filled graphics, keep-outs and cut-outs only, and stay empty without them). `Zone.fills` MUST NOT be written in either mode: a computed pour comes from the document ("Poured regions"), never from the model.
- A zone with fewer than three outline points, a zone layer outside the copper layers or on a plane, or a name that fails `text_problem` MUST raise `ValueError` naming the zone's id.

#### Scenario: Ground zone on two layers
- **GIVEN** a zone on `In1.Cu` and `B.Cu` with the net `GND`, four outline points and priority 0, and a second zone on `F.Cu` with priority 2
- **WHEN** `Polygons6` is read after a write with the pour mode `outline`
- **THEN** it holds three records; the `F.Cu` record has `POURINDEX=0`; the two `GND` records have `LAYER=MID1` and `LAYER=BOTTOM`, five vertices, `NET` equal to the index of `GND`, and names that decode to `GND_L02_P001` and `GND_L04_P002`; `Regions6` is empty

#### Scenario: Zone without an outline refused
- **WHEN** a spec holds a zone whose `outline` is empty
- **THEN** `write_pcbdoc` raises `ValueError` naming the zone's id

#### Scenario: Zone fills of the model are not written
- **GIVEN** a zone whose `fills` hold a ring that differs from what the engine pours
- **WHEN** the document is written with the pour mode `computed`
- **THEN** the regions of the polygon are the engine's pieces, and no region holds the model's ring

#### Scenario: Thresholds from the zone settings
- **GIVEN** a zone with the default settings, a zone whose islands are removed below 0.1 mm² with a minimum width of 0.1 mm, and a zone whose islands are never removed
- **WHEN** `uv run pytest tests/unit/backends/altium/test_polygon_thresholds.py -k written` writes them
- **THEN** the first record holds `REMOVEISLANDSBYAREA=TRUE`, `AREATHRESHOLD=250000000000.000000` and `NECKWIDTHTHRESHOLD=5mil`; the third `REMOVEDEAD=FALSE`, `REMOVEISLANDSBYAREA=FALSE` and `NECKWIDTHTHRESHOLD=9.8425mil`; the second holds `REMOVEISLANDSBYAREA=TRUE`, `AREATHRESHOLD=15500031000.062000` (Altium's own save of 0.1 mm² holds `15500031000.062008`, which reads as the same square nanometres) and `NECKWIDTHTHRESHOLD=3.937mil`; the board outline's polygon keeps `REMOVEISLANDSBYAREA=TRUE`, `AREATHRESHOLD=250000000000.000000` and `NECKWIDTHTHRESHOLD=5mil`

### Requirement: Net class records
`pcbdoc.write_pcbdoc` SHALL write one `Classes6` property record per `pcbdoc.NetClassSpec` of `PcbDocSpec.net_classes`, in name order (S-0160, S-0161, S-0172, S-0174, S-0175, S-0176; `H-A-PCB-CU-CLASS`).
- A record MUST hold, in this order: the seven common keys with `LAYER=MULTILAYER`, `NAME`, `KIND=0`, `SUPERCLASS=FALSE`, the members `M0`, `M1`, … (the class's net names in name order), `SELECTED=FALSE`, `SCHAUTOGENERATEDCLUSTER=FALSE` and `UNIQUEID` = `project.unique_id("pcbdoc:<filename>:class:<name>")`.
- A class without a member MUST still be written. The super classes and the generated component classes of Altium-saved documents are not written.
- A class name that fails `text_problem` or holds `'`, or a member that `PcbDocSpec.nets` does not hold, MUST raise `ValueError`.

#### Scenario: Class of the blink sample
- **WHEN** `Classes6` of the blink sample is read
- **THEN** it holds one record with `NAME=PWR`, `KIND=0`, `M0=GND`, `M1=VIN` and no `M2`

### Requirement: Design rule records
`pcbdoc.write_pcbdoc` SHALL write `Rules6` with the lowered rules of the design (`PcbDocSpec.design_rules`, the records of `rulemap.lower`; "Rule lowering table", "Scoped rule records") and with Clearance, Width and Routing Via Style rules from the net classes (S-0160, S-0161, S-0172, S-0174, S-0175, S-0176; `H-A-PCB-CU-RULES`). The rules of the net classes and the `All` defaults MUST be written only when the spec holds a track, an arc, a via, a zone or a net class, and only for the kinds of `PcbDocSpec.class_kinds`; the rules of the design are written whenever the spec holds them. With neither, and with `PcbDocSpec.rules` off, `Rules6` MUST be empty.
- A build (`lower.from_design` with `options`, change c0126), whose net classes the user wrote, MUST set `class_kinds` to Clearance, Width and RoutingVias. A write of a model (`lower.write_design`, a conversion, `AltiumBackend.write`) MUST write the records of the design's rules, the rules a source record or the user gave, and of the c0038 rules only those KiCad checks (change c0434): `class_kinds` MUST be Clearance alone, and empty when a Clearance record of the design has the scopes `All` and `All`, which overrides every class clearance as an unconditioned KiCad rule does. A class's track width and via size MUST NOT be written as rules: KiCad does not check them, a KiCad project gives every class a value, and a board converted from Altium gets KiCad's defaults there. Each written net class with a value that is left out MUST be counted `changed` under `netclass`.
- A rule of the design that gives fewer limits than its record holds MUST stay refused (`value-unsupported`, "Rule lowering table"): no limit is invented for a board or class minimum.
- Each rule MUST be a 16-bit rule-kind number (0 Clearance, 2 Width, 11 RoutingVias, 42 HoleSize, 63 BoardOutlineClearance, 52 HoleToHoleClearance, 19 MinimumAnnularRing), then one property block with, in this order: the seven common keys with `LAYER=TOP`, `RULEKIND`, `NETSCOPE` (`DifferentNets` for Clearance and BoardOutlineClearance, `AnyNet` otherwise), `LAYERKIND=SameLayer`, `SCOPE1EXPRESSION`, `SCOPE2EXPRESSION` (`All`, or the second scope of a Clearance rule of the design), `NAME`, `ENABLED=TRUE`, `PRIORITY`, `COMMENT` (empty), `UNIQUEID` = `project.unique_id("pcbdoc:<filename>:rule:<name>")`, `DEFINEDBYLOGICALDOCUMENT=FALSE`, then the kind's keys.
- Kind keys: Clearance `GAP`, `GENERICCLEARANCE`, `IGNOREPADTOPADCLEARANCEINFOOTPRINT=FALSE`, `OBJECTCLEARANCES` (empty); Width `MAXLIMIT`, `MINLIMIT`, `PREFEREDWIDTH`; RoutingVias `HOLEWIDTH`, `WIDTH`, `VIASTYLE=Through Hole`, `MINHOLEWIDTH`, `MINWIDTH`, `MAXHOLEWIDTH`, `MAXWIDTH`; HoleSize `ABSOLUTEVALUES=TRUE`, `MAXLIMIT`, `MINLIMIT`, `MAXPERCENT=80.000`, `MINPERCENT=20.000`; BoardOutlineClearance the keys of Clearance; HoleToHoleClearance `GAP`, `ALLOWSTACKEDMICROVIAS=FALSE`; MinimumAnnularRing `MINIMUMRING`; lengths as mil text.
- Per kind, one rule `<Kind>_<class>` with `SCOPE1EXPRESSION=InNetClass('<class>')` MUST be written for each class that holds the kind's value (clearance; track width; via diameter and drill), in class-name order with `PRIORITY` from 1, then one rule named `Clearance`, `Width` or `RoutingVias` with `SCOPE1EXPRESSION=All` and the next priority. The rules of one kind are written together, in the order of `rulemap.KIND_ORDER`: Clearance, Width, RoutingVias, HoleSize, BoardOutlineClearance, HoleToHoleClearance, MinimumAnnularRing.
- Within a kind the rules of the design MUST come first, in the order of `rulemap.lower`, then the class rules and the `All` rule; `PRIORITY` counts from 1 over them all. A class rule or `All` rule whose two scopes are those of a rule of the design MUST be left out: the design's rule replaces it. A class rule whose name a rule of the design holds gets the suffix `_class`.
- The `All` rules MUST use `pcbdoc.DEFAULT_CLEARANCE` (0.2 mm), `DEFAULT_TRACK_WIDTH` (0.25 mm), `DEFAULT_VIA_DIAMETER` (0.6 mm) and `DEFAULT_VIA_DRILL` (0.3 mm), Fenolite's choices.
- A class or `All` width rule's `MINLIMIT` and `MAXLIMIT` MUST be the smallest and the largest of the preferred width and the widths of the written tracks and arcs in its scope; a via rule's minimum and maximum likewise over the written vias. So the written copper never breaks the width or via rule of a net class or the default; a rule of the design holds the limits of the script exactly, and the copper may break it.

#### Scenario: Rules of the blink sample
- **WHEN** `Rules6` of the blink sample is read
- **THEN** it holds five rules in this order: `Clearance_PWR` (kind 0, `GAP=7.874mil`, priority 1), `Clearance` (priority 2, `GAP=7.874mil`), `Width_PWR` (kind 2, `PREFEREDWIDTH=19.685mil`, priority 1), `Width` (priority 2, `PREFEREDWIDTH=9.8425mil`) and `RoutingVias` (kind 11, priority 1, `WIDTH=23.622mil`, `HOLEWIDTH=11.811mil`)

#### Scenario: Limits follow the copper
- **GIVEN** a class `PWR` with track width 0.5 mm and tracks of 0.4 mm and 1.0 mm on its nets
- **WHEN** `Width_PWR` is read
- **THEN** `MINLIMIT` is `15.748mil`, `PREFEREDWIDTH` is `19.685mil` and `MAXLIMIT` is `39.3701mil`

#### Scenario: A rule of the design replaces the default of its scope
- **GIVEN** the blink sample with a `clearance` rule of 0.15 mm for all objects and an `edge_clearance` rule of 0.5 mm
- **WHEN** `Rules6` is read
- **THEN** it holds, in this order, `Clearance` (`GAP=5.9055mil`, priority 1), `Clearance_PWR` (priority 2), `Width_PWR`, `Width`, `RoutingVias` and `BoardOutlineClearance` (kind 63, `GAP=19.685mil`, priority 1), and no second rule with the scope `All` of the kind Clearance

#### Scenario: A conversion writes only the rules of its source
- **GIVEN** the public document `altium-third-party-pcbdoc-08` converted to KiCad, whose project holds 14 net classes with KiCad's default values and whose rules file holds 8 rules
- **WHEN** the project is converted back to Altium with `--altium-pour outline`
- **THEN** the written document holds no rule scoped `InNetClass(...)` and no `All` default, 4 Clearance and 1 Width record as the source, the Width limits equal to the source's, no more records of a kind than the source holds; the 14 net classes are counted `changed` under `netclass`

#### Scenario: A KiCad board without a rules file keeps its class clearances
- **GIVEN** a model with a net class that holds a clearance, a track width and a via size, and no rule of its own
- **WHEN** `lower.from_design` lowers it without options
- **THEN** `class_kinds` is Clearance alone: the class's Clearance record and the `All` Clearance are written, no class Width or Routing Via Style record, and the class is counted `changed`; with a clearance rule on every object `class_kinds` is empty

### Requirement: Copper records read back
`tests/_altium_pcb_read.py` SHALL read the copper of a PCB document as test code written from `docs/formats/altium/pcb-copper.md`, without importing the writer. This requirement extends c0035's "PCB files read back".
- `read_pcbdoc` MUST also return the vias (position, diameter, hole, start and end layer, net), the polygons (layer text, net index, decoded name, pour index, vertices), the net classes (name, members) and the rules (kind number, name, priority, scope, keys), and the free tracks and arcs with their net index.
- It MUST check: a via subrecord of at least 31 bytes with layer byte 74 and a hole below its diameter; every net index of a track, arc, via or polygon names a record of `Nets6`; a polygon's first and last vertex are equal and its pour index is unique; a class member names a net; a rule's leading number matches its `RULEKIND`; `Header` equals the record count in the four copper storages; the numbered copper layers form one chain from 1 to 32 and the `V9_STACK` list holds the same copper layers in that order; every plane of the chain has a `PLANE<k>NETNAME` that names a record of `Nets6`, and no track, arc or polygon lies on a plane.

#### Scenario: Copper negative controls
- **WHEN** the reader gets a document whose via has 30 bytes, whose via lies on layer 1, whose track names net 9 of 3, whose polygon is not closed, whose two polygons share a pour index, whose class lists an unknown net, whose Width rule starts with the number 0, whose `LAYER2NEXT` is 0 while `LAYER1NEXT` is 2, whose `V9_STACK` list lacks `Mid-Layer 2`, whose chain holds layer 39 while `PLANE1NETNAME` is `(No Net)`, and whose track lies on layer 39
- **THEN** each read raises an error that names the broken rule

### Requirement: Copper oracle
`tests/kicad/altium/test_pcbdoc_copper_oracle.py` SHALL import the routed sample's PCB document with `kicad-cli pcb import --format altium` as c0035's "PCB document oracle" does, read the result with `fenolite.backends.kicad.pcb.read_board`, and compare it with the sample's model (S-0161, S-0166, S-0020; `H-A-PCB-CU-KICAD`).
- The exit code MUST be 0, the report's `errors` empty, and its statistics MUST count the model's tracks plus arcs, vias and polygon records. Warnings MUST be only those c0035 lists (one per internal plane outside the stack).
- The copper layers MUST be `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu`, each inner layer with the KiCad type `signal`.
- The test MUST also import the plane variant `p0` ("Routed sample and author report"): its `In1.Cu` MUST have the type `power`, its `In2.Cu` the type `signal` with the variant's inner track, and every other item MUST match as above. KiCad maps the stack by chain position, and it does not import a plane's net; the test MUST say so.
- Relative to the outline's corner and within 10 nm, every model track MUST be found with its layer, net name, ends and width; every arc with its start, mid and end; every via as a through via with its net, position, diameter and drill; every zone layer as a zone with its net and outline points and no fill.
- The zone of higher model priority MUST get the higher KiCad priority.
- Net classes and rules are not compared: the import writes no project file, and the test MUST say so.
- The test MUST be skipped on `kicad-cli` 9.x and required in the `kicad-10` job. A pass on 10.0.6 gives `H-A-PCB-CU-KICAD` the level `ORACLE-VERIFIED(kicad-cli)`; it settles no Altium row.

#### Scenario: Import of the routed sample
- **WHEN** `uv run pytest tests/kicad/altium/test_pcbdoc_copper_oracle.py -k sample` runs with `kicad-cli` 10.0.6
- **THEN** the imported board has four copper layers and the sample's tracks, arc, vias and zones with their nets and geometry, and no error in the report or on stdout

#### Scenario: Import of the plane variant
- **WHEN** `uv run pytest tests/kicad/altium/test_pcbdoc_copper_oracle.py -k plane` runs with `kicad-cli` 10.0.6
- **THEN** the imported board's copper rows are `F.Cu` `signal`, `In1.Cu` `power`, `In2.Cu` `signal` and `B.Cu` `signal`, and the track of the variant on `In2.Cu` is found with its net and ends

### Requirement: Component class records
`pcbdoc.write_pcbdoc` SHALL write one `Classes6` property record per schematic sheet that holds a component of the document, so that the board holds the component classes Altium derives from the sheets (S-0172, S-0175, S-0199, S-0200, S-0310; `H-A-ECO-COMPCLASS`, `H-A-ECO-SHEETCLASS`). This requirement extends "Net class records", whose rules hold.
- `pcbdoc.component_class_records(components, filename)` MUST return the records.
- The class of a component on a module sheet MUST be named after the module, the second item of `PlacedComponent.sheet`: the name of the module's sheet symbol. With these classes the change order of Altium Designer 26.5 proposes no component class (report of Part E, 2026-10-04).
- The class of a component whose `sheet` is `None`, on the top sheet or on the single sheet of a flat build, MUST be named after that sheet: the stem of `filename`, which the document shares with it. Altium Designer 26.5 offered the class `routed`, with every component, for the flat sample `routed.SchDoc` (same report). A module of that name shares the class.
- The two rules are one rule: a sheet's class carries the name Altium shows for the sheet.
- The records MUST follow the net class records, in code-point order of the class names.
- A record MUST hold, in this order: the seven common keys with `LAYER=MULTILAYER`, `NAME`, `KIND=1`, `SUPERCLASS=FALSE`, the members `M0`, `M1`, … (the refs of the sheet's components, each once, in code-point order), `SELECTED=FALSE`, `SCHAUTOGENERATEDCLUSTER=FALSE` and `UNIQUEID` = `project.unique_id("pcbdoc:<filename>:component-class:<name>")`.
- A class name that fails `text_problem` MUST raise `ValueError`.
- A document without a component MUST hold no component class. A component class alone MUST NOT make `rule_records` write a rule.
- The classes that Altium-saved documents hold with `AUTOGENERATEDCLASS=TRUE`, which are what "Net class records" calls generated component classes, and the super classes are not written.
- The test reader `tests/_altium_pcb_read.read_classes` MUST check that every member of a `KIND=1` class is the `SOURCEDESIGNATOR` of a record of `Components6`, and raise `PcbReadError` otherwise.

#### Scenario: Classes of the board example
- **WHEN** `examples/altium_hier_board/design.py` is built with `sheets="modules"` and `Classes6` is read
- **THEN** it holds three records in this order: `NAME=PWR` with `KIND=0`, `NAME=driver` with `KIND=1`, `M0=R1`, `M1=U1` and no `M2`, and `NAME=led` with `KIND=1`, `M0=D1` and no `M1`

#### Scenario: Class of a flat document
- **WHEN** the blink sample is built with the single sheet and `Classes6` of `blink.PcbDoc` is read
- **THEN** it holds two records: `NAME=PWR` with `KIND=0`, then `NAME=blink` with `KIND=1`, `M0=D1`, `M1=R1`, `M2=U1` and no `M3`

#### Scenario: Top sheet with parts
- **WHEN** a document named `blink.PcbDoc` is written whose component `D1` is on the module sheet `led` and whose other components have `sheet` equal to `None`
- **THEN** `Classes6` holds `NAME=blink` with the members `R1` and `U1`, then `NAME=led` with the member `D1`

#### Scenario: Member that is no component
- **WHEN** the reader is given a `KIND=1` class whose member `R9` is not a component of the document
- **THEN** it raises `PcbReadError` naming `R9`

### Requirement: Rule lowering table
`fenolite.backends.altium.rulemap.TABLE` SHALL be the closed table that maps each neutral rule kind to the Altium rule kind that carries it. Each row MUST hold the neutral kind, the Altium kind and its kind number, the limits a rule must give, the constraint fields in written order, the `NETSCOPE`, the scope forms it supports, and either `exact` or one reason of `NOT_LOWERED_REASONS` (`no-counterpart`, `scope-unsupported`, `value-unsupported`, `unit-loss`) with a note.
- Every neutral rule kind of `model/rules.py` MUST have a row. A row MUST be `exact` only when `docs/formats/altium/pcb-copper.md` ("Rule kinds lowered") records, with a public source and a label, the Altium constraint and the keys of its record. The `exact` rows are: `clearance` → `Clearance` (0), `track_width` → `Width` (2), `via_diameter` and `via_drill` → `RoutingVias` (11), `hole_size` → `HoleSize` (42), `edge_clearance` → `BoardOutlineClearance` (63), `hole_to_hole` → `HoleToHoleClearance` (52), `annular_width` → `MinimumAnnularRing` (19). `hole_clearance`, `courtyard_clearance`, `silk_clearance` and `creepage` are `no-counterpart`.
- The five pair and length kinds, `diff_pair_gap`, `diff_pair_uncoupled`, `skew`, `diff_pair_skew` and `length`, MUST each have a row with the reason `no-counterpart`, in the model's order after `no_tracks`. Each note MUST say that the record of the Altium rule that would carry the kind is in no public source that `pcb-copper.md` records, so its keys are not known; no note MAY name a kind number or a key. A row of these five becomes `exact` only through a later change that first records the fact rows.
- `lower(rules)` MUST return the rule records of the rules it writes and, for every rule that is not written, its kind, selector and reason. A rule is written only when its row is `exact`, its severity is `error`, it gives exactly the limits of its row (`min` for a clearance kind, `hole_to_hole` and `annular_width`; `min` and `max` for `hole_size`; `min`, `opt` and `max` for `track_width`, `via_diameter` and `via_drill`), and each value is 0 or at least one PCB unit and inside the 32-bit range; otherwise the reason is `value-unsupported`. `lower` MUST never write a rule whose value or scope differs from the neutral rule's beyond the 2 nm of the PCB unit.
- A `via_diameter` and a `via_drill` rule of the same selector MUST share one `RoutingVias` record; either one without the other MUST be `value-unsupported`.
- Fixed constraint values: `IGNOREPADTOPADCLEARANCEINFOOTPRINT=FALSE` and an empty `OBJECTCLEARANCES` (Clearance, BoardOutlineClearance), `VIASTYLE=Through Hole`, `ABSOLUTEVALUES=TRUE` with `MAXPERCENT=80.000` and `MINPERCENT=20.000`, and `ALLOWSTACKEDMICROVIAS=FALSE`.
- `lift(records)` MUST return the neutral rules of the records that `read.rules.map_rules` maps, in record order, and the count of the others by Altium kind. `lift` MUST never return a rule of the five pair and length kinds or a selector with a `diff_pair` leaf: `read.scope.parse_scope` keeps its closed grammar, and a scope outside it stays unmapped as before.
- `lift(lower(rules).records)` MUST equal the lowered subset of `rules` (`Lowered.written`) in kind, selectors and limits within 2 nm (`rulemap.same_rules`); the priority of a lifted rule is the record's, which counts within its Altium kind.

#### Scenario: Every kind has a row
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k complete` compares the kinds of `model/rules.py` with `TABLE` and with the table "The lowering table" of `docs/formats/altium/pcb-copper.md`
- **THEN** every kind has exactly one row, the five pair and length kinds included, the page's table equals `TABLE`, and every `exact` row is cited on the page with a source and is a kind of `read.rules.RULE_KIND_MAP`

#### Scenario: Round trip of the table
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k roundtrip` lowers and lifts one rule of every `exact` kind and generated rule sets
- **THEN** the lifted rules equal the lowered subset, within 2 nm, and every rule is either written or named with one reason

#### Scenario: A rule with no counterpart
- **GIVEN** a rule of a kind whose row has the reason `no-counterpart`
- **WHEN** `lower` runs
- **THEN** no record is written for it, and the result names its kind, its selector and that reason

#### Scenario: A minimum alone is not a Width rule
- **GIVEN** a `track_width` rule with `min` only
- **WHEN** `lower` runs
- **THEN** no record is written and the reason is `value-unsupported`, because a Width record holds a minimum, a preferred and a maximum width

#### Scenario: Pair and length rules are named, not written
- **GIVEN** one rule of each of `diff_pair_gap`, `diff_pair_uncoupled`, `skew`, `diff_pair_skew` and `length`, each on `diff_pair USB_`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k pair` calls `lower` on them
- **THEN** no exception is raised, no record is written, and the result names each rule once with its kind, the selector `diff_pair USB_` and the reason `no-counterpart`

### Requirement: Scoped rule records
Rule records SHALL carry the scope of their rule as an expression of the closed scope grammar of `altium-project-reader` ("Closed scope grammar"): all objects (`All`), a net (`InNet('<net>')`), a net class (`InNetClass('<class>')`), a component (`InComponent('<ref>')`), an item kind (`IsTrack`, `IsVia`, `IsPad`, and `InPolygon` for `zone`), and their combinations with `And`, `Or` and `Not` (change c0412); a `clearance` rule with a second selector uses both scope fields, and every other kind writes `All` as its second scope. Every written scope MUST be one that `read.scope.parse_scope` turns back into the rule's selector.
- An operand that is itself a conjunction, a disjunction or a negation MUST be written in parentheses, because the grammar holds one kind of operator per parenthesis level.
- A layer is not a written scope: the closed grammar refuses layer functions, so a rule with `layers` or a `layer` selector MUST give `scope-unsupported`.
- Rules of one Altium kind MUST be written from the most governing neutral rule to the least (priority 1, 2, … and then priority 0; ties by falling name, then id), with `PRIORITY` from 1 in that order within the kind. This is the reverse of the order of a KiCad rules file, where the last rule governs.
- A selector outside the written forms (a glob, a value that holds `'` or cannot be written, an `area` or `diff_pair` leaf, an item kind other than `track`, `via`, `pad` and `zone`, a second selector for a kind other than `clearance`) MUST give the reason `scope-unsupported` for that rule only; the other rules of the kind are written.
- Rule names MUST be unique in the document and derived from the kind and the scopes (`<Kind>`, `<Kind>_<class>`, `<Kind>_net_<net>`, `<Kind>_ref_<ref>`, `<Kind>_<item>` for an item kind, `_and_`, `_or_` and `not_` for the operators, `_to_` before the second scope; a repeated name gets `_2`, `_3`…), so that two builds give equal names.

#### Scenario: Class rule above the general rule
- **GIVEN** a design with a track width (minimum, preferred and maximum) for all nets and another, of priority 1, for the class `PWR`
- **WHEN** the PCB document is written and read back
- **THEN** two Width rules exist, `Width_PWR` with the scope `InNetClass('PWR')` and `PRIORITY=1`, and `Width` with the scope `All` and `PRIORITY=2`

#### Scenario: A scope outside the grammar
- **GIVEN** a `track_width` rule on the net glob `PWR_*`, a second on the layer `F.Cu` and a third on the class `PWR`
- **WHEN** `lower` runs
- **THEN** one record `Width_PWR` is written, and the two others are named with the reason `scope-unsupported`

#### Scenario: Composite clearance scopes
- **GIVEN** clearance rules on `and(ref J1, item_kind pad)`; on `net A` against `or(net B, net C)`; on `netclass HV` against `and(item_kind zone, not(netclass HV))`; and on `and(item_kind pad, net SENSE)` against `not(netclass HV)`
- **WHEN** `lower` runs and the records are lifted again
- **THEN** four Clearance records are written with the scopes `InComponent('J1') And IsPad`; `InNet('A')` and `InNet('B') Or InNet('C')`; `InNetClass('HV')` and `InPolygon And (Not InNetClass('HV'))`; `IsPad And InNet('SENSE')` and `Not InNetClass('HV')`, and the lifted rules equal the lowered ones

#### Scenario: Pads without a net
- **GIVEN** a single-sided clearance rule on `or(and(or(ref R1, ref R2), item_kind pad), and(ref U1, item_kind pad, not(or(net A, net B))))`
- **WHEN** `lower` runs and the record is lifted again
- **THEN** one Clearance record is written with the first scope `((InComponent('R1') Or InComponent('R2')) And IsPad) Or (InComponent('U1') And IsPad And (Not (InNet('A') Or InNet('B'))))` and the second `All`, and the lifted rule equals the written one

#### Scenario: Limit combinations
- **GIVEN** `track_width` rules with min, opt and max (scoped `all` and by a class), with min only and with min and max; `via_diameter` rules with min, opt and max beside a `via_drill` rule of the same selector, alone (scoped `all` and by a class) and with min only; and `hole_size` rules with min and max and with min only
- **WHEN** `lower` runs on each
- **THEN** the full Width rules, the via pair and the min-and-max Hole Size rule are written, and every other rule is one `value-unsupported` loss whose detail names the missing limit, or the missing partner rule, because no record read leaves a limit out

### Requirement: Layer stacks of any even count
The PCB document writer SHALL write the copper layers of the model's stack-up, for any even count from 2 to 32 with at most 16 signal layers and 16 plane layers, in the model's order, each a signal layer or, when the build declares it a plane, an internal plane on its net, with the dielectrics between them (thickness, material name, permittivity).
- The layer map MUST assign each copper layer of the model to one Altium layer, and two model layers MUST NOT share one. The map MUST be recorded in `docs/formats/altium/pcb-copper.md`.
- A design without a stack-up MUST get the stack that the writer gave it before this change.
- A stack the rules above exclude MUST give `altium.not-lowered` with `where` `stackup` and the default stack of the two outer layers; no partial stack is written.

#### Scenario: Six layers read back
- **GIVEN** the authored design `board6` with the copper layers `F.Cu, In1.Cu, In2.Cu, In3.Cu, In4.Cu, B.Cu`, built with `In2.Cu` as a plane on `GND`
- **WHEN** it is written and the PCB document is read back
- **THEN** the board has six copper layers in that order, `In2.Cu` is a plane, and the dielectric thicknesses equal the design's within 2 nm

#### Scenario: Odd count refused
- **GIVEN** a design whose board has five copper layers
- **WHEN** it is built for Altium
- **THEN** `altium.not-lowered` has `where` `stackup`, and the document holds the default stack

### Requirement: Blind and buried via records
A via whose span is two copper layers of the written stack SHALL be written with its start and end layer, and the board record SHALL hold one drill pair per distinct span.
- A through via MUST be written as before this change.
- A micro via MUST give `altium.via-unsupported` (warning) and MUST NOT be written.

#### Scenario: Three spans
- **GIVEN** `board6` with a through via, a via from `F.Cu` to `In1.Cu` and a via from `In1.Cu` to `In2.Cu`
- **WHEN** the document is written and read back
- **THEN** the three vias have those spans, and the board record holds three drill pairs

### Requirement: Board text records
Board texts SHALL be written as stroke text records with their string, layer, position, height, stroke width and rotation; a text on a bottom-side layer SHALL be mirrored. The model's text has no mirror, justification or font kind, so none is written.
- The string MUST be written in every form that `altium-pcb-reader` ("Text records and wide strings") needs to return it unchanged, non-ASCII characters included.
- A text that has no record (an empty string, a control character or a line break, a height or a stroke width that is not positive, a layer outside the board layer map of `docs/formats/altium/pcb-records.md`) MUST give `altium.not-lowered` with `where` `text/<id>` and the reason in its message.

#### Scenario: Accented text
- **GIVEN** a board text `Tensão 5 V` on `F.SilkS`
- **WHEN** the document is written and read back
- **THEN** the text record returns that string, on the top overlay, at the same place within 2 nm

### Requirement: Board graphics and keep-out records
Board graphics on the non-copper layers of the board layer map SHALL be written as track, arc and region records without a net. Board graphics on a signal layer of the written stack SHALL be written as copper records on that layer with the net index of their net (change c0412). Keep-outs SHALL be written as region records with the keep-out flag and the restriction set of the model, on the Keep-Out layer when they name every copper layer of the board, else one per copper layer, except a rule area of poured copper alone, which is a polygon cut-out ("Rule areas of poured copper alone").
- A filled rectangle or polygon on a signal layer MUST be one region record with `KIND=0`, its layer's id and its net's index in the common prefix (`0xFFFF` for a shape without a net), in `Regions6` and in `ShapeBasedRegions6`. A drawn line, arc, circle, rectangle or polygon outline on a signal layer MUST be tracks and arcs of its width with that net. No fill record is written: `docs/formats/altium` records no field after offset 37 of a fill, whose saved lengths are 46 and 50.
- A shape on an internal plane, a filled circle, a shape that `pcbdoc.graphic_problem` refuses, and a shape whose net no net record holds MUST give `altium.not-lowered` with the kind `copper-shape` and `where` `graphic/<id>`; `copper-shape` stays a loss kind, which `FEN-7001` refuses without `--allow-lossy`.
- A keep-out record MUST hold its restrictions value in two keys, `KEEPOUTRESTRICTIONS` (the key saved documents hold) and after it `KEEPOUTRESTRIC` (the key KiCad's importer reads; not a key Altium writes), both with the same value (the maintainer's decision of 2026-10-06), so that KiCad imports the keep-out with exactly the restrictions written. That Altium accepts the pair stays `INFERRED` until step X11 of Part X.
- A restriction that the record cannot carry (`no_footprints`) MUST give `altium.not-lowered` with `where` `keepout/<id>` naming the restriction; the keep-out is written with the others, and not at all when it has no other.
- A graphic that has no record (a layer outside the map, a drawn shape without a positive width, a filled circle, a shape without an extent) MUST give `altium.not-lowered` with `where` `graphic/<id>`. A graphic on `Edge.Cuts` is the outline and counts as written.
- The board outline MUST stay as written before this change.

#### Scenario: Keep-out with two restrictions
- **GIVEN** a keep-out that forbids tracks and vias in a rectangle on all copper layers
- **WHEN** the document is written and read back
- **THEN** one keep-out region with those two restrictions is read, its value 3 in `KEEPOUTRESTRICTIONS` and in `KEEPOUTRESTRIC`

#### Scenario: Copper polygon with a net
- **GIVEN** a KiCad board with a filled `gr_poly` on `F.Cu` on the net `VIN`, a filled `gr_rect` on `B.Cu` without a net and a drawn `gr_line` on `F.Cu` on `GND`
- **WHEN** it is converted with `convert --to altium` without `--allow-lossy`
- **THEN** the write succeeds, the document holds one region on the top layer with the index of `VIN`, one region on the bottom layer with no net and one track on the top layer with the index of `GND`, the report has no `copper-shape` loss, and KiCad's import of the document holds the shapes on their layers and nets

#### Scenario: Copper on a plane stays a loss
- **GIVEN** a filled polygon on an internal plane layer
- **WHEN** the board is converted without `--allow-lossy`
- **THEN** `FEN-7001` names `copper-shape` for that graphic

### Requirement: Non-plated holes and slots
A hole of the board SHALL be written as a free pad record with a hole and no copper, its plated byte the hole's `plated`. A hole with a `length` (`design-model`, "Slotted board holes") SHALL be written as a slot: hole shape 2, the slot length `length` and the slot rotation 0 in subrecord 6, the pad's size (`length`, `drill`), its shape round and its rotation the hole's `rotation`, so that the copper equals the hole.
- A hole without a positive drill MUST give `altium.not-lowered` with `where` `hole/<id>`.

#### Scenario: Mounting hole
- **GIVEN** a non-plated hole of 3.2 mm
- **WHEN** the document is written and read back
- **THEN** a free pad with a 3.2 mm hole, plating off and no copper is read

#### Scenario: A turned slot
- **GIVEN** a non-plated hole of drill 2 mm, length 12 mm and rotation 30°
- **WHEN** `uv run pytest tests/unit/backends/altium/test_slot_records.py` writes the document and reads it back
- **THEN** a free pad on Multi-Layer with hole shape 2, hole size 2 mm, slot length 12 mm and rotation 30° within the units' rounding is read, without name, net or component

### Requirement: Component bodies are reported
The writer SHALL write a component body record for each `ComponentBody` of a footprint of the board that is extruded, has an outline and a height above its standoff, when bodies are asked for (`altium-build`, "Component bodies in an Altium build"), and each other `ComponentBody` SHALL give one `altium.not-lowered` with `where` `body/<id>` that names its height and its reason. A model file is embedded only for a model that the caller gives with its data ("Embedded model bodies", change c0449), and no body is written that the model does not hold.
- `pcbdoc.body_problem(body)` MUST return why a body has no record, or `None`: the kind `model` ("a body that names a 3D model needs the model's data, which the model does not hold"); an outline of fewer than three distinct points ("the body has no outline"); a standoff below the board surface, which no saved extruded body holds; and a height that is not above the standoff in the units of the record. The function reads `kind`, `outline`, `height` and `standoff` of the body as the model holds them and no other field. A body whose footprint is no component of the written document has the reason "its footprint is not written", and a body whose placed outline keeps fewer than three vertices in whole units has no outline: `pcbdoc.place_body` and the lowering decide these two.
- Without the request (`bodies="off"`, which `fenolite build` gives only with `--altium-bodies off` since change c0155) every body MUST be reported, with the reason "component bodies are not written without --altium-bodies extruded" and the body's height, and no record is written: the document is the document of change c0085.
- A written body MUST be one record of "Extruded component body records": the component is the body's footprint; the outline is the body's outline placed by the position and rotation that the document gives the footprint's component, without a mirror (the outline of a footprint instance is held as seen from the top, as its pads are); `STANDOFFHEIGHT` and `OVERALLHEIGHT` are `standoff` and `height`; `bottom` is the footprint's side; the identifier is `name`; `MODELID` is `body_model_id(body.id)`.
- The layer MUST be the Altium id of `ComponentBody.layer` when the layer map gives it a mechanical layer 1 to 16, and otherwise Mechanical 13 for a body of a top footprint and Mechanical 14 for a body of a bottom one.
- A footprint without a body MUST get no record and no issue: no outline is derived from a courtyard or from any other graphic, and no height is assumed.
- Each body MUST be counted once, as written or as not lowered ("Written items are accounted").

#### Scenario: Body height
- **GIVEN** a board footprint with a body of height 2.5 mm
- **WHEN** the design is built for Altium with `--altium-bodies off` (without the option the body is written since change c0155)
- **THEN** `result.pcb.not_lowered` holds `body` with the count 1, and one `altium.not-lowered` with `where` `body/<id>` names 2.5 mm and the option

#### Scenario: Body written
- **GIVEN** the same footprint, placed on the bottom side and turned by 90 degrees, with a rectangle outline
- **WHEN** the design is built with `--altium-bodies extruded` and the document is imported
- **THEN** `result.pcb.written` holds `body` with the count 1 and no issue names the body, both body storages hold one record with `BODYPROJECTION=1` on Mechanical 14 and the index of the footprint's component, and the imported footprint holds one extruded body with the height 2.5 mm and the outline of the model within 2 nm

#### Scenario: Bodies that have no record
- **GIVEN** a footprint with a body of kind `model`, a body without outline and a body whose height equals its standoff, and a second footprint without a body
- **WHEN** the design is built with `--altium-bodies extruded`
- **THEN** `result.pcb.not_lowered.body` is 3, each of the three has one `altium.not-lowered` with its own reason, the second footprint has no issue, and both body storages are empty

### Requirement: Written items are accounted
The writer SHALL return, per kind of model item (footprint, pad, track, arc, via, zone, text, graphic, keep-out, hole, body, rule), the number of items written and the number not lowered, and every item of the board MUST be in exactly one of the two.

#### Scenario: Nothing is lost silently
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pcb_complete.py -k accounted` builds `board6`, the routed samples and a variant of `board6` with one item of every kind that has no record
- **THEN** for each kind, written plus not lowered equals the number of items in the model, and each not-lowered item has an issue

### Requirement: Imported boards are written from the model
`backends.altium.lower.from_design(design, *, issues, options=None, corner_ratios=None, rewrite=False, full_drill=False, bodies="off")` SHALL return the inputs of the PCB and schematic writers (`AltiumInputs`) from a `Design`: footprints with their pads, graphics, fields and texts taken from the board's footprint instances (no library is read), placements, copper, zones, free items, rules, the stack and the classes.
- A footprint instance MUST be written as a component with its own pads: its footprint definition holds exactly the pads of the instance that the pad record can hold. Its graphics, its fields `Reference` and `Value` and its texts are written as "Footprint items of a written component" says. An instance that holds none (a model stored before change c0126, a design read from KiCad without the projection) is written with its pads alone, as before. The definition holds no body: the bodies of an instance are written into the document (change c0121), not into a library.
- A footprint without a reference and a footprint link whose one pad stands alone (the import's reading of a free pad) MUST be written as a free pad, with its net.
- Native ids of the model that are Altium unique ids MUST be reused: the record's `UNIQUEID` is the id of `fp:<id>`, and `SOURCEUNIQUEID` and the unique id of the schematic part are the last part of `cmp:<source unique id>` (`project.native_unique_id`) when one component alone holds it; the instances of a repeated sheet share that id and get derived ones.
- A board read from an Altium document (`"altium" in board.native_ids`) MUST be written in the document's own frame (`pcbdoc.Frame.document()`: Y negated, nothing moved) with the origin that the import kept, so every coordinate keeps its units; a board of a build is written in the frame of a build (`pcbdoc.Frame.of`), and any other board (a conversion; change c0441) in that frame with its corner moved out to a multiple of 254 nm (`pcbdoc.Frame.on_units`), so every point moves by whole document units and a coordinate that was a unit stays one.
- An `Arc` of the board, and a graphic of kind `arc`, whose `altium` bag holds the pair `arc` (`altium-import`, "Extension bags"; change c0127) MUST be written with the centre, the radius and the two angles of that pair when the pair still says the entity's three points. `lower.kept_arc(entity, points, frame)` decides: it converts the pair as the import does (`adapter.units.arc_points`) and returns the record's geometry (`pcbrecords.ArcGeometry`) when each of the three points it gives lies within `lower.ARC_TOLERANCE` (2 nm per axis, the length tolerance of the written scope) of the entity's point in the frame of the written document; `from_design` puts it into `PcbDocSpec.arc_records` under the entity's id. It returns `None`, and the arc is written from its three points as an arc without the pair is, with no issue, when the pair is stale or unusable: a point lies further away (the arc was moved or reshaped in the model, or the board is written in another frame than the document's), the pair does not parse into three integers of 32 bits and two doubles, the radius is 0 or less, an angle is not finite, or the angles make a full turn. An arc that is written from its kept record MUST NOT be refused because its three points lie on one line: the record holds its circle.
- `rewrite=True` (change c0128) says that `design` is the reading of an Altium document and that the write gives that document back. A via whose drill equals its diameter MUST then be written (`PcbDocSpec.allow_full_drill`): a document that Altium saved holds such vias (`pcb-copper.md`, "Via"; `H-A-PCBX-VIA-FULL`). `full_drill=True` (change c0441) writes such a via too, without the rest of a rewrite: a conversion to Altium sets it, since the via may come from a saved document through KiCad. Without either such a via is left out and counted, as before: a design from a script or a build is written with the rule of a build. `rewrite=True` for a design whose board was not read from an Altium document (`"altium"` is no key of `board.native_ids`) MUST raise `ValueError`; a design without a board takes the argument without effect. The argument changes nothing else: the frame, the kept arc records and every other item are written the same with and without it; component bodies are written by `bodies` alone, in a rewrite as in any other write.
- The outline MUST be `Board.outline`, else the first closed ring of the `Edge.Cuts` graphics, else the box of the board's items; each approximation is counted under `outline`. An arc of the ring (`Outline.arcs`, or an `Edge.Cuts` arc) MUST be written as one arc vertex (change c0441; `PcbDocSpec.outline_arcs`, "Board outline arcs"), not as two straight edges through its mid; an arc whose three points lie on one line is a straight edge.
- An item that the writers do not carry MUST be left out, counted per kind in `AltiumInputs.not_lowered` with its id, and reported once per kind with `altium.not-lowered`: a pad with a per-layer padstack, a custom or trapezoid shape, a slot, no copper layer, no number, or a rounded rectangle without a known corner ratio; a track or arc on a layer that is no signal layer of the written stack; an arc whose three points lie on one line and that is not written from a kept record; a via that `pcbdoc.via_span` refuses or whose drill is not below its diameter (in a rewrite or with `full_drill`: is above its diameter), or is 0 or less; a zone without an outline in the model; a text, graphic or keep-out that `pcbdoc` refuses or whose layer has no layer in the document; a shape on a copper layer that "Board graphics and keep-out records" does not write (`copper-shape`: a shape on a plane, a filled circle, a shape that `pcbdoc.graphic_problem` refuses; change c0412); the poured copper of a zone (`zone-fill`: a polygon is written unpoured); a component body that "Component bodies are reported" does not write, which is every body when `from_design` is called without `bodies="extruded"` (change c0121); a graphic or a text of a footprint that the records do not carry (`footprint-graphic`, `footprint-copper`, `footprint-text`); a rule that `rulemap.lower` does not write; a net or net class whose name no record holds; an internal plane without a net of the document (`plane`); stack-up values that do not fit (`stackup`); and of the circuit (change c0083), each as an info: the pin-to-pad map of a component (`pin-pad-map`: `Component.pin_pad_map` with the bag key `pin_pads`), a module (`module`: the generated schematic is one sheet) and the channel of a repeated sheet (`channel`: the bag keys `sheet_symbol` and `channel_index` of a module).
- `AltiumInputs.written` MUST count the model items that the PCB document holds, per kind of `lower.KINDS`, which are the kinds of `lens.altium_copper.KINDS`.
- The schematic's design (`lower.schematic_design`) MUST give every component with a reference a symbol link, a value and pins, so that the schematic writer can generate a sheet from the circuit; a part of a link that no record holds is replaced by a generic one.

#### Scenario: Footprints without a library
- **GIVEN** a design read from a KiCad board whose footprint libraries are not present
- **WHEN** `lens.altium.write_model` runs
- **THEN** the PCB document holds every footprint as a component with its pads, and no library file is read

#### Scenario: Own documents
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k own_document` writes the models of `blink.PcbDoc`, `routed.PcbDoc` and `board6.PcbDoc`
- **THEN** each written project holds a PCB document, a schematic, its library and the project file, the reading of each PCB document equals the first reading inside the written scope, and the unique ids of the components are those of the first document

#### Scenario: Arc written from its record
- **GIVEN** the reading of a document with a free copper arc of centre (1 000 000, 2 000 000) units, radius 100 units and angles 30 to 35 degrees, whose three points give another centre and a radius of 93 units when a record is derived from them, and a second arc of the same centre and radius from 0 to 1 degree, whose three points lie on one line
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k kept_arc` writes the model with `AltiumBackend().write` and reads the written document
- **THEN** `PcbDocSpec.arc_records` names both arcs, both are counted as written, the two arc records of the written document hold the centre, the radius and the angles of the first document, and the second reading holds the same six points as the first

#### Scenario: Stale record ignored
- **GIVEN** the same reading with the first arc moved by 1 µm in the model, its bag unchanged
- **WHEN** `from_design` runs
- **THEN** `PcbDocSpec.arc_records` does not name that arc, no issue names it, and the written record's centre is the one derived from the moved points

#### Scenario: Full drill in a rewrite only
- **GIVEN** the reading of `tests/data/altium/routed/routed.PcbDoc` with the drill of its first via set to the via's diameter, and of a second via set above its diameter
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k full_drill` calls `from_design` without and with `rewrite=True`
- **THEN** without it both vias are counted as not written with the reason `the drill is not below the diameter`; with it the first via is written with a hole equal to its diameter, reads back with that drill, and only the second is counted; and `rewrite=True` on the design read from `tests/data/kicad/board/two_layer.kicad_pcb` raises `ValueError`

#### Scenario: Counted once per kind
- **WHEN** `from_design` runs on the model of `tests/data/altium/board6/board6.PcbDoc`
- **THEN** `counts()` is 1 graphic (the one on the keep-out layer), the one issue is an `altium.not-lowered` info for `graphic`, and `written` counts 27 under `footprint-graphic`

#### Scenario: Full drill in a conversion
- **GIVEN** the authored `routed` sample moved by 1 mm, its first via with a hole equal to its diameter, written as an Altium document
- **WHEN** `uv run pytest tests/unit/convert/test_round_trip_shape.py -k vias` converts it to KiCad and back to Altium
- **THEN** no via and no pad is lost, the via comes back with its full hole, every rounded-rectangle pad keeps its corner ratio, and every pad and via is its source moved by one translation, to the nanometre

### Requirement: Writer options for a model that was read
`backends.altium.pcbdoc` SHALL take what a model that was read needs, each with a default that keeps the bytes of every build.
- `PcbDocSpec.frame` (`None`: `Frame.of(outline)`) and `PcbDocSpec.origin` (`None`: 1000 mil, 1000 mil); `Frame.document()` is the frame of a document that was read, and `Frame.offset` defaults to 1000 mil.
- `PcbDocSpec.free_pads`: `FreePad(pad, extras, net)` values, written as pads without a component after the holes; `pad.position` and `pad.rotation` are those on the board.
- `PlacedComponent.record_unique_id` (`None`: derived from the file name and the link id) and `PlacedComponent.nets_by_pad` (pad id → net name; `None`: `pad_nets` by pad number), so two pads of one number may lie on different nets.
- `PcbDocSpec.arc_records` (entity id → `pcbrecords.ArcGeometry`; empty by default; change c0127): an arc of `PcbDocSpec.arcs` and a graphic of kind `arc` whose id it names are written with that centre, radius and pair of angles instead of the ones derived from their three points, on the entity's layer, net and width, and in the order that their points give. `graphic_problem(graphic, arc_known=True)` does not refuse an arc for three points on one line. `pcbdoc` reads no bag: the caller decides which records still say their entities.
- `PcbDocSpec.allow_full_drill` (`False` by default; change c0128): `True` lets `via_records` write a via whose drill equals its diameter ("Via records"). `lower.from_design` sets it for a rewrite only; the build (`lens/altium.py`, `lens/altium_copper.py`) never sets it and keeps refusing such a via with `altium.copper-invalid`.
- A component whose designator or comment is empty gets no text record for it, and a component text outside 7-bit ASCII is written with the 8-bit string of a free text beside its wide string.
- No format fact is added: every record is one of `docs/formats/altium/pcb-records.md` and `pcb-document.md`.

#### Scenario: Builds keep their bytes
- **WHEN** `uv run pytest tests/unit/lens -k "altium and (samples or golden)"` rebuilds the committed samples
- **THEN** every file under `tests/data/altium/` keeps its bytes

### Requirement: Body facts before body code
`docs/formats/altium/pcb-bodies.md` SHALL hold a section "Written form of an extruded body" with one row for each binary field and each key that `pcbrecords.body_record` writes, and the writer MUST NOT write a key or a field that has no row there.
- Each row MUST state the value rule (a constant, a value of the model, or a choice of Fenolite among values that saved records hold), a source of `docs/evidence/sources.md`, an evidence label and a hypothesis of `docs/hypotheses.md`.
- A row whose value no source supports MUST be marked `stand-in` and MUST name the hypothesis that an author report settles; this change has two, `MODELID` and `MODEL.CHECKSUM` (`H-A-PCBX-BODY-OPEN`). While a stand-in row exists, component bodies MUST be written only on request ("Component bodies in an Altium build" of `altium-build`).
- `pcbrecords.BODY_KEYS` MUST be the keys of the written record in order, and a unit test MUST compare it with the rows of the section in both directions.
- `tests/corpus/test_altium_bodies.py` MUST hold the rows over the extruded bodies (`MODEL.MODELTYPE=0`) of the public PCB documents of the corpus manifest and MUST print, per document, the number of bodies of each kind; it reports counts and value forms only.

#### Scenario: Keys and rows agree
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcb_bodies.py -k facts` reads the section and `BODY_KEYS`
- **THEN** every key of `BODY_KEYS` has exactly one row, every row of a key is in `BODY_KEYS`, the rows of `MODELID` and `MODEL.CHECKSUM` are marked `stand-in` and name `H-A-PCBX-BODY-OPEN`, and no other row is

#### Scenario: The rows hold over the public documents
- **WHEN** `uv run pytest tests/corpus/test_altium_bodies.py -rA` runs with the corpus cached
- **THEN** every extruded body holds the constants, the key order (apart from the two optional keys the section names), `MODEL.EXTRUDED.MINZ` equal to `STANDOFFHEIGHT`, `MODEL.EXTRUDED.MAXZ` equal to `OVERALLHEIGHT`, a `BODYPROJECTION` of 0 on a top component and 1 on a bottom one, whole units in every vertex and a twin with the same property text at the same index of `ShapeBasedComponentBodies6`; the documents with extruded bodies come from at least three repositories; and no `MODELID` of an extruded body is an entry of `Models`

### Requirement: Extruded component body records
`pcbrecords.body_record(layer, vertices, *, component, standoff, overall, bottom, identifier="", model_id="", shape_based=False, form="saved")` SHALL return one component body primitive (type 12) of an extruded body in the form that "Written form of an extruded body" states, and `pcbdoc.write_pcbdoc` SHALL write the bodies of `PcbDocSpec.bodies` into `ComponentBodies6` and `ShapeBasedComponentBodies6`.
- The primitive MUST be the type byte 12 and one subrecord: the common prefix with `layer`, no net, no polygon and the component index (`0xFFFF` for none), five zero bytes, the 32-bit length of the property text with its NUL, the text, the 32-bit vertex count and the vertices. `vertices` are binary units, at least three, without a closing vertex; fewer MUST raise `ValueError`. The plain form holds each vertex as two doubles; the shape-based form holds each as 37 bytes, none round, and repeats the first vertex after the last.
- `layer` MUST be a mechanical layer 1 to 16 (ids 57 to 72), else `ValueError`; `V7_LAYER` is its text.
- `standoff` and `overall` are binary units, written as mil text in `STANDOFFHEIGHT` and `OVERALLHEIGHT` and again in `MODEL.EXTRUDED.MINZ` and `MODEL.EXTRUDED.MAXZ`; `overall` not above `standoff`, and a negative `standoff` (no saved extruded body holds one), MUST raise `ValueError`. `BODYPROJECTION` MUST be 1 when `bottom` and 0 otherwise. `IDENTIFIER` MUST be the decimal character codes of `identifier` joined by commas, empty for an empty identifier. `MODEL.2D.X` and `MODEL.2D.Y` MUST be the centre of the bounding box of `vertices` as mil text, a half unit rounded towards zero.
- With `form="saved"` the text MUST hold the 35 keys of `BODY_KEYS` in order, `MODELID` being `model_id` and `MODEL.CHECKSUM` being `0`; an empty `model_id` MUST raise `ValueError`. With `form="short"` it MUST hold the first 21 keys, ending at `TEXTUREROTATION`.
- `pcbrecords.body_model_id(body_id)` MUST return a GUID text in braces that depends on `body_id` alone, so that a build is repeatable.
- `PcbDocSpec.bodies` holds one `PlacedBody` per body to write: the index of its component in `PcbDocSpec.components`, the Altium layer id, the outline placed in the frame of the placements, the heights in nanometres, the side, the identifier, the `MODELID` stand-in and the id of the model's body (for the caller's accounts; no record holds it). `PcbDocSpec.body_form` is `saved` (the default) or `short`; no command and no option of a build sets `short`. `write_pcbdoc` MUST convert each outline point with `to_units` after the document's frame, drop equal neighbours, and write record `i` of both storages from body `i`, in the order of `bodies`, with each `Header` the count. A body whose component index is outside `components`, or that keeps fewer than three vertices, MUST raise `ValueError`: the caller checks with `pcbdoc.body_problem` and places with `pcbdoc.place_body(body, *, component, at, rotation, bottom, frame)`, which returns the `PlacedBody` or the reason. The layers of the bodies MUST be among the layers in use of the board record.
- A spec without bodies MUST give the document it gave before this change, byte for byte. No record of `Models`, `ModelsNoEmbed`, `Textures` or `UniqueIDPrimitiveInformation` is written for a body.

#### Scenario: Rectangle on a top component
- **GIVEN** a body with the vertices `(0, 0), (10000, 0), (10000, 5001), (0, 5001)` on layer 69, component 2, standoff 0 and overall 984252 units, not bottom, the identifier `U1`
- **WHEN** `body_record` is called in the plain and in the shape-based form
- **THEN** both records hold the same 35 keys in the order of `BODY_KEYS`, `V7_LAYER=MECHANICAL13`, `OVERALLHEIGHT=98.4252mil`, `MODEL.EXTRUDED.MAXZ=98.4252mil`, `STANDOFFHEIGHT=0mil`, `BODYPROJECTION=0`, `IDENTIFIER=85,49`, `MODEL.2D.X=0.5mil`, `MODEL.2D.Y=0.25mil`, `MODEL.CHECKSUM=0` and `MODEL.MODELTYPE=0`; the plain record ends with four vertices of 16 bytes and the other with five of 37; and `read_bodies` frames each with an empty tail, the component 2 and the heights given

#### Scenario: Short form
- **WHEN** `body_record(..., form="short")` is called
- **THEN** the text holds 21 keys, the last is `TEXTUREROTATION`, and no key starts with `MODEL`

#### Scenario: Document with three bodies
- **GIVEN** a `PcbDocSpec` with three bodies on two components, one of them on the bottom side
- **WHEN** it is written and read with `read_pcbdoc` and `read_bodies`
- **THEN** each of the two storages holds three records and a `Header` of 3, record `i` of one has the text of record `i` of the other, and the same spec without bodies gives the bytes of the document before this change

### Requirement: Component bodies of a library footprint
`pcblib` SHALL write each body of `LibFootprint.bodies` as one component body primitive in the footprint's stream when bodies are asked for, and none otherwise.
- The primitive MUST be `body_record` in the plain form with no component (`0xFFFF`), `bottom=False`, the outline in the library's frame and the layer rule of "Component bodies are reported"; it MUST be counted in the stream's header as every primitive is, and written after the footprint's other primitives. The footprint's list of unique ids MUST hold no entry for a body: the one saved library with a body lists its pads only (`tests/corpus/test_altium_bodies.py -k library`).
- Only a body that "Component bodies are reported" writes is written; `check_footprint` MUST list each other body of the definition in its notes.
- A library without a written body MUST be the bytes it was before this change.
- The fact page MUST say that no extruded body of a saved library was read: the form is the document's, and the one library body of the corpus names a model (`H-A-PCBX-BODY-LIB`, `INFERRED`).

#### Scenario: Footprint with a body
- **GIVEN** a `FootprintDef` with two pads and one extruded body of 1.2 mm with a rectangle outline
- **WHEN** the library is written with bodies and read with `read_pcblib`
- **THEN** the footprint holds one primitive of type 12 after its pads, `read_bodies` frames it with no component, the overall height reads 1.2 mm within one unit, and the library written without bodies equals the library of today

### Requirement: Track layer rules in the Altium rule table
`fenolite.backends.altium.rulemap.TABLE` SHALL hold one row for the neutral kind `no_tracks` (`rules-model`, "Track layer rules"), thirteenth, after `creepage` and before the five pair and length kinds, as the kind stands in `RuleKind`, with the status `no-counterpart` and a note. This requirement extends "Rule lowering table": with it every kind of `model/rules.py`, eighteen of them with the five pair and length kinds, has exactly one row.
- The note MUST say that Altium's rule of the routing layers of a scope is the nearest counterpart and that its record (kind number, constraint keys) is in no public file read under the sources register, so the row cannot be `exact`.
- `lower` MUST write no record for a `no_tracks` rule and MUST name its kind, its selector and the reason `no-counterpart`; `fenolite build --target altium` then gives one `altium.not-lowered` (warning) with `where` `design-rules/no_tracks` and lists the rule in `result.rules.not_lowered` ("Rules in an Altium build"). The rule is never dropped without that issue.
- The table "The lowering table" of `docs/formats/altium/pcb-copper.md` MUST gain the row, with the source of the statement about Altium's rule (`S-0660`) and the label `INFERRED`.
- `lift` is unchanged: a record of that Altium kind in a document is counted among the records it does not map.
- The row MAY become `exact` only through a later change that registers a public file holding the record.

#### Scenario: Thirteen rows
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rulemap.py -k complete` compares the kinds of `model/rules.py` with `TABLE` and with the page's table
- **THEN** every kind has exactly one row, eighteen in all: the thirteen rows that change c0107 left keep their place, the thirteenth is `no_tracks` with the status `no-counterpart` and a note, the five pair and length kinds follow, and the page's table equals `TABLE`

#### Scenario: A track layer rule in an Altium build
- **GIVEN** the four-layer blink variant with `design.rules.rule("sig-outer", "no_tracks", where=select.netclass("SIG"), layers=("In1.Cu", "In2.Cu"))`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_rules.py -k no_tracks` builds it with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `issues` hold one `altium.not-lowered` warning with `where` `design-rules/no_tracks` naming `sig-outer`, `result.rules.not_lowered` holds it with the reason `no-counterpart`, and the PCB document holds the rule records of the same script without the rule

### Requirement: Locked copper records
`pcbrecords.track_record`, `arc_record` and `via_record` SHALL take `locked: bool = False`, and `pcbdoc.write_pcbdoc` SHALL pass the `locked` of each free `Track`, `Arc` and `Via` of the spec (`design-model`, "Copper locks in the board model"), so a locked item of the model is a locked primitive of the document (`H-A-PCB-CU-LOCK`).
- **Fact first.** `pcbrecords.LOCK_WRITTEN` MUST be the closed set of the record kinds, among `track`, `arc` and `via`, for which `docs/formats/altium/pcb-copper.md` holds a row saying that bit 2 of the first flag byte, clear, locks a free primitive of that kind, with a public source of `docs/evidence/sources.md` and a label. A kind MUST NOT enter the set before its row is on the page; a test MUST compare the set with the page.
- A record of a kind in `LOCK_WRITTEN` built with `locked=True` MUST differ from the unlocked record in that one bit. A record of a kind outside it MUST be the unlocked record whatever `locked` is; the build reports those items (`altium-build`, "Copper locks in an Altium build"), so a lock is never dropped without an issue.
- With `locked=False` every record MUST have the bytes it had before this change, and a document of a design without locked copper MUST keep its bytes.
- Component primitives, pads, fills, regions and texts are not changed: their flag bytes stay `0x0C 0x00`.
- The order of the records in `Tracks6`, `Arcs6` and `Vias6` MUST NOT depend on `locked`.

#### Scenario: Three locked items in a document
- **GIVEN** the routed sample's model with one track, one arc and one via set `locked=True`, and `LOCK_WRITTEN` holding the three kinds
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcbdoc_copper.py -k locked` writes the document and reads it with `backends.altium.read`
- **THEN** exactly those three primitives have `Prefix.locked` true, and the document differs from that of the unlocked model in three bytes

#### Scenario: The set follows the page
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcbrecords.py -k lock_written` compares `LOCK_WRITTEN` with the rows of the locked flag in `pcb-copper.md`
- **THEN** each kind of the set has its row with a source id and a label, and a kind without a row is not in the set

#### Scenario: A design without locks keeps its bytes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_copper.py -k bytes` builds the routed sample
- **THEN** `<name>.PcbDoc` has the SHA-256 it had before this change

### Requirement: Via tenting flags
`pcbrecords.via_record` SHALL take the keywords `tented_top=False` and `tented_bottom=False` and write them as bits 5 and 6 of the first flags byte of the via's subrecord, the bits that `read.pcbprims` reads as `ViaRecord.tented_top` and `ViaRecord.tented_bottom` (`docs/formats/altium/pcb-copper.md`, "Flags of a via"; S-0160, S-0172, S-0174, S-0175, S-0176; `H-A-PCB-CU-VIATENT`). This requirement refines the flags that "Via records" states; every other byte of the record is as that requirement states it.
- The first flags byte MUST be the byte that "Locked copper records" (c0108) states for the via's lock (`0x0C` unlocked, `0x08` locked), plus `0x20` when `tented_top` is true, plus `0x40` when `tented_bottom` is true: `0C`, `2C`, `4C` or `6C` for an unlocked via, `08`, `28`, `48` or `68` for a locked one. The lock bit and the two tenting bits are independent. The second flags byte stays `00`. With both keywords false the record MUST equal, byte for byte, the record written before this change.
- `pcbdoc.write_pcbdoc` MUST set the two keywords of each via of `PcbDocSpec.vias` with `pcbdoc.via_tenting(via, PcbDocSpec.via_protection)` (`altium-build`, "Via protection in an Altium build"): the via's own `tenting_front` and `tenting_back`, else the value of `PcbDocSpec.via_protection`, the board default that the lowering hands over (default `None`), else false. The vias of the spec keep the protection the model holds, so the model that a build stores does not change. It MUST write nothing for `covering_front`, `covering_back`, `plugging_front`, `plugging_back`, `capping` and `filling`, and MUST NOT raise for any value of them.
- The solder-mask expansions of the record (at 54 and at 242) MUST stay the values of "Via records": no fact recorded here ties them to the tenting flags.
- A via written with tenting flags MUST read back, through `read.pcbprims`, with `tented_top` and `tented_bottom` equal to the keywords.
- `docs/formats/altium/pcb-copper.md` MUST hold a fact row for the written flags with its sources, the label `INFERRED` and `H-A-PCB-CU-VIATENT`, MUST take "tented vias" out of its list of what is not written, and MUST say in "Vias" that the flags are `0C 00` only for a via that is not tented.

#### Scenario: Flags of the four cases
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcb_vias.py -k tenting` calls `via_record(393701, 393701, 236220, 118110, net=2)` with no tenting keyword, with `tented_top=True`, with `tented_bottom=True` and with both
- **THEN** bytes 0 to 4 of the subrecord are `4A 0C 00 02 00`, `4A 2C 00 02 00`, `4A 4C 00 02 00` and `4A 6C 00 02 00`, the four records are equal in every other byte, and the first equals the record of "Via bytes"

#### Scenario: Written flags read back
- **GIVEN** a PCB document written with four through vias, one per case
- **WHEN** it is read with the PCB reader
- **THEN** the four via records hold (`tented_top`, `tented_bottom`) = (false, false), (true, false), (false, true) and (true, true)

### Requirement: Footprint items of a written component
`backends.altium.lower` SHALL write the graphics, the fields and the texts of a footprint instance as primitives of its component, and SHALL count what the records do not carry.
- The definition that `lower` hands to `pcbdoc.place_component` MUST hold, in the top-side form, the instance's graphics that a definition can hold (a drawn `line`, `rect`, `circle` or `arc` on a layer of `pcbrecords.FLIP_PAIRS` that is no copper layer): for a bottom footprint each point is mirrored about the local X axis and each layer swapped for its other side, the inverse of what `place_component` applies, as the pads are (`lower._library_pad`). The order is the instance's. Every other written graphic of the instance (on a mechanical layer of a board that was read, on a paste or solder-mask layer, a filled shape, a polygon) MUST be handed over as the instance holds it, in `PlacedComponent.items` (`pcbdoc.ComponentGraphic`: the pad frame, the Altium id of its layer, no mirror and no layer flip), and is written after the definition's graphics.
- A `line`, an unfilled `rect`, an unfilled `circle` and an `arc` MUST be written with `pcblib.graphic_records` ("Footprint line and arc records"), with the component's index. An `arc` whose `altium` bag holds the pair `arc` MUST be written with the centre, the radius and the angles of that pair while `lower.kept_arc` finds that the pair still says its three points placed on the board (change c0127), as a free arc is.
- **Layers.** The layers are those of `pcbrecords.LAYER_MAP` that are no copper layer and, for a board that was read from an Altium document, `Mech.13` to `Mech.16` as the layers 69 to 72, which every written document enables. With the group of fills and regions, the paste and solder-mask layers of `pcbrecords.BOARD_LAYER_MAP` are layers of a footprint's graphics too. The same four names MUST be taken for the free texts and graphics of such a board. For such a board `Mech.<n>` for n from 1 to 12 MUST be the layer `56 + n`, for footprint and board items alike, and the board record MUST enable each mechanical layer that a primitive lies on; a document that uses none of them keeps its bytes. The meaning of the enable key MUST be a fact row with a public source before the code is written.
- A graphic on a copper layer MUST NOT be written: it is counted under `footprint-copper`, a kind of `lower.LOSS_KINDS`, so its loss is a warning and needs `allow_lossy`. A graphic on a layer without a layer in the document, a degenerate arc and, until its group is implemented, a `polygon` or a filled shape are counted under `footprint-graphic` (info). With the group of fills and regions, a filled `rect`, a filled `circle` and a `polygon` without holes are region records with the component's index.
- **Fields.** `pcbdoc.PlacedComponent.designator_place` and `.comment_place` (`TextPlace | None`, `None` by default; `.comment` is the comment's string) MUST carry the place of the fields `Reference` and `Value` of an instance that has them: position, layer, height, stroke, rotation, and whether the text is shown (`NAMEON`, `COMMENTON`). `None` MUST give the bytes the writer gave before.
- **Texts.** Until its group is implemented, a text of `texts` is counted under `footprint-text` (info). With it, a text is a text record with the component's index and its string as stored; a text that the record cannot hold (a line break, a height that is not positive, a layer without a layer in the document) stays counted.
- `footprint-graphic`, `footprint-copper` and `footprint-text` are kinds of `lower.MORE_KINDS`: `lower.KINDS`, and with it `result.pcb` of a build, do not change. `AltiumInputs.written` counts the written items under the same three keys.
- **Corner ratio.** The corner percentage of a rounded pad MUST come from `Pad.corner_ratio`, else from the pair `corner_percent` of its `altium` bag, else from the caller's `corner_ratios`; without any, the pad is not written and counted as today.
- `pcblib.check_footprint` is unchanged: a library footprint with a graphic on a copper layer is still refused, and its drops are those of "Footprint content checks".
- Every record field written MUST be a row of `docs/formats/altium/pcb-records.md` or `pcb-document.md`; a field without a row is not written, and its item is counted.

#### Scenario: Silkscreen survives a rewrite
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower_items.py -k own_document` writes the models of `blink.PcbDoc`, `routed.PcbDoc` and `board6.PcbDoc` and imports the written documents
- **THEN** each footprint of each reading holds the graphics of the first reading within 2 nm, 27 per document, and no `footprint-graphic` is counted as not written

#### Scenario: A bottom footprint
- **GIVEN** the model of `blink.PcbDoc`, whose `D1` is on the bottom side
- **WHEN** it is written and imported
- **THEN** the graphics of `D1` are on the bottom layers they were on, at the points they were at, within 2 nm

#### Scenario: Mechanical layers of a rewrite
- **GIVEN** an authored document, built in the test, whose one component owns a track on Mechanical 1 and a track on Mechanical 5
- **WHEN** it is imported, written with `AltiumBackend().write` and imported again
- **THEN** the footprint holds one `line` on `Mech.1` and one on `Mech.5` at the points of the first reading within 2 nm, the board record of the written document enables Mechanical 1 and 5, and no `footprint-graphic` is counted as not written

#### Scenario: Copper inside a footprint
- **GIVEN** the model of `blink.PcbDoc` with one `line` on `F.Cu` added to the graphics of `R1`
- **WHEN** `AltiumBackend().write(design)` runs, and again with `allow_lossy=True`
- **THEN** the first raises `LossyWriteError` with one `altium.not-lowered` warning whose `where` is `footprint-copper`, and the second writes the document without that line and counts it

#### Scenario: Designator at its place
- **GIVEN** the model of `blink.PcbDoc` with the field `Reference` of `R1` moved by 2 mm and its field `Value` made visible
- **WHEN** it is written and imported
- **THEN** the two fields of `R1` come back at those places within 2 nm, both visible

#### Scenario: Builds keep their bytes
- **WHEN** `uv run pytest tests/unit/lens -k "altium and (samples or golden)"` rebuilds the committed samples
- **THEN** every file under `tests/data/altium/` keeps its bytes

### Requirement: Removed pad shapes are counted, not written
`lower.write_design` SHALL write a via whose `altium` bag holds the pair `pad_removed` as the ordinary via record of 321 bytes, with a pad on every layer of its span, and SHALL count it (change c0132).
- Every such via that is written MUST be listed in `AltiumInputs.not_lowered` under the kind `via-pad-shape`, with the reason that the layers without a pad shape are not written. The kind MUST be in `MORE_KINDS` and MUST NOT be in `LOSS_KINDS`: the via is written, and a write is not refused for it.
- The via MUST stay in the comparison of RT-A3 (`altium-verification`, "Round-trip level RT-A3"): the kind names no model entity that the write left out.
- No byte of the table at 209 and no further byte of the 330-byte form MUST be written: no fact says what the nine further bytes of that form are (`docs/formats/altium/pcb-copper.md`, "Via").
- A via without the pair MUST be written and counted as before.

#### Scenario: A via with removed pad shapes in a rewrite
- **GIVEN** the reading of `tests/data/altium/routed/routed.PcbDoc` with the pair `("pad_removed", "2,4,5")` added to the bag of its first via
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k pad_shape` writes it without `allow_lossy`
- **THEN** the write is not refused, every via is written as a record of 321 bytes whose table at 209 is zero, the files are the bytes of the write without the pair, `not_lowered["via-pad-shape"]` holds the id of the first via alone, and the write has one `altium.not-lowered` information for the kind

### Requirement: Slotted drills of footprint pads
A footprint pad whose padstack holds only a slotted hole (`hole_shape` `slot`, `hole_length`, `hole_rotation`, no per-layer shapes and no offset) SHALL be written in the library and the document with hole shape 2, hole size the drill, slot length `hole_length` and slot rotation `hole_rotation` relative to the pad. A pad with an offset drill or per-layer shapes stays refused.

#### Scenario: An oval mounting slot
- **GIVEN** a KiCad footprint with an `np_thru_hole` oval pad of drill 1 × 3 mm turned 30°
- **WHEN** `uv run pytest tests/unit/backends/altium/test_slot_drills.py` writes the library and reads it back
- **THEN** the pad is read with hole shape 2, hole size 1 mm, slot length 3 mm and the pad's rotation, and the footprint is not refused

### Requirement: Full-stack pad records
A pad whose per-layer stack gives every copper layer a circle, an oval, a rectangle or a rounded rectangle with its corner ratio SHALL be written with stack mode 1 when the inner layers share one shape and size, and with stack mode 2 otherwise, by the write rows of `docs/formats/altium/pcb-library.md` that restate the read rows of `import.md`, "Pads and padstacks". A stack with a custom shape on any layer MUST stay a lost `pad` with its reason.

#### Scenario: Per-layer stack read back
- **GIVEN** a footprint with one pad of 1.6 mm round on top and bottom and 1.2 mm round on the inner layers of a 4-layer board
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcblib_stacks.py` writes it and reads the document back
- **THEN** the pad has stack mode 1, and its shape and size per copper layer equal the model's

#### Scenario: Distinct first and second inner layers in Full Stack
- **GIVEN** an authored four-layer pad with In1 round 1.2 x 1.2 mm and In2 rectangular 1.4 x 1.1 mm
- **WHEN** its PCB document and derived library are written with Full Stack mode and inspected in Altium, including placement from the library into a disposable four-layer PCB
- **THEN** In1 retains the main middle geometry and In2 retains the first extended geometry, and both native views show the requested shapes and sizes
- **AND** the reader maps the twenty-nine extended entries to Mid-Layer 2 through 30, including when the board chain skips Mid-Layer 1

### Requirement: Connector and free pads
A pad of kind `connect` SHALL be written as a surface pad whose paste and solder-mask expansions remove both openings. A pad without a number inside a footprint SHALL be written as a pad of that footprint with an empty designator, in the PCB document and in the derived library, as documents saved by Altium hold component pads without a name (`pcb-records.md`, "Pad": census of S-0172, S-0200, S-0601). Each such pad MUST be its own record with its own net, so several pads without a number in one footprint stay distinct; a pad that a writer cannot hold MUST be counted `lost` under `pad` with its reason.

#### Scenario: Connector pad
- **GIVEN** a footprint with one `connect` pad
- **WHEN** the board is written and read back
- **THEN** the pad is a surface pad on its copper layer with no paste and no mask opening, and the report has no lost `pad`

#### Scenario: Two pads without a number
- **GIVEN** a KiCad footprint with pads `1` and `2`, a surface pad without a number on the net of pad `1` and a non-plated hole pad without a number
- **WHEN** it is converted to Altium with `allow_lossy=True` and the PCB document and the derived library are read back
- **THEN** the row `pad` has `written` equal to `source` and no `changed` or `lost` item, the footprint read back holds four pads, two of them without a number at their own places, the surface one on its net, the library footprint holds four pads, and the comparison of the conversion holds no `pad-missing` and no `ref-ambiguous`

### Requirement: Mechanical layers of KiCad drawings
`lower.KICAD_MECHANICAL` SHALL map `User.1` to `User.8` to Mechanical 1 to 8, `Dwgs.User` to Mechanical 9, `Cmts.User` to Mechanical 10, and `Eco1.User` and `Eco2.User` to Mechanical 11 and 12; the fabrication and courtyard layers keep Mechanical 13 to 16. A user layer whose KiCad user name is `Mech.<n>` or `Mechanical <n>`, n from 1 to 16, SHALL be written on Mechanical n instead, whatever its number (change c0412).

#### Scenario: Detailed contract for mechanical layers of kicad drawings
- **WHEN** this behavior is exercised
- **THEN** the following detailed conditions MUST hold:

`lower.KICAD_MECHANICAL` SHALL map `User.1` to `User.8` to Mechanical 1 to 8, `Dwgs.User` to Mechanical 9, `Cmts.User` to Mechanical 10, and `Eco1.User` and `Eco2.User` to Mechanical 11 and 12; the fabrication and courtyard layers keep Mechanical 13 to 16. A `User.<k>` layer of `Board.layers` whose `kicad` bag holds the user name `Mech.<n>` or `Mechanical <n>` (1 ≤ n ≤ 16) MUST be mapped to Mechanical n, replacing its fixed position; another layer that the fixed map puts on Mechanical n keeps it. A graphic or text on a mapped layer MUST be written there and the document MUST name the layer after its KiCad name. A text on a copper layer MUST be written as a text record on that copper layer. A layer outside the map, a user layer above `User.8` without such a name among them, MUST stay a reported loss.

#### Scenario: Drawing on Dwgs.User
- **GIVEN** a board with one line on `Dwgs.User` and one text on `F.Cu`
- **WHEN** it is written and read back
- **THEN** the line is on Mechanical 9, the text on the top copper layer, and the report loses neither

#### Scenario: User layer named after a mechanical layer
- **GIVEN** a board whose layer `User.11` has the user name `Mech.13` and holds a line, and whose `User.12` has no user name and holds a line
- **WHEN** it is converted with `convert --to altium`
- **THEN** the first line is on Mechanical 13 and the report holds no loss for it, and the second is reported as a `graphic` loss naming `User.12`

### Requirement: Derived PCB library
A conversion to Altium SHALL write `<name>.PcbLib` with one footprint per distinct footprint name of the board (the part of `lib_ref` after its last `:`), built from the first instance in reference order in the footprint's frame, and every component of the document MUST link that library. An instance whose pads or graphics differ from its library footprint MUST be counted `changed` under `footprint` with the reason "differs from the library footprint"; the document keeps the instance as it is.

#### Scenario: Two instances, one edited
- **GIVEN** a board with `R1` and `R2` of footprint `R_0603`, and `R2` with one pad moved by 0.1 mm
- **WHEN** it is converted to Altium
- **THEN** the library holds one footprint `R_0603` with the pads of `R1`, both components link it, and the report counts one `changed` footprint

### Requirement: Board cut-out regions
`pcbrecords.cutout_region(ring)` SHALL write one inner ring of `lowered_outline` as a board cut-out region with the keys of the fact rows of `docs/formats/altium/pcb-records.md`, "Board cut-outs", and no net. The build writes such regions only when `pcbdoc.CUTOUT_REGIONS` is true, which MUST stay false until the maintainer's kit cases S3 to S5 are recorded.

#### Scenario: The merged L as one region
- **GIVEN** the lowered ring of slots `S2` and `S3` of the shared fixture
- **WHEN** `uv run pytest tests/unit/backends/altium/test_cutout_regions.py` writes it and Fenolite's reader reads it back
- **THEN** one region is read whose keys make a board cut-out and whose ring lies within 1 µm of the written one

#### Scenario: KiCad imports the region
- **WHEN** `uv run pytest tests/kicad/altium/test_slots_import.py -k region -rA` imports the written document with `kicad-cli pcb import` (10.0.6)
- **THEN** the imported board's `Edge.Cuts` holds the cut-out ring within 1 µm

### Requirement: Embedded board array records
`pcbrecords.embedded_board_array(...)` SHALL write an Embedded Board Array in the form that Part Q measured (`docs/formats/altium/pcb-document.md`, "Embedded board arrays"), naming the referenced document by its path relative to the panel document, never an absolute one. While `pcbdoc.EMBEDDED_ARRAYS` is false no build writes one; it MUST be set only by a Part Q report of Q7, Q8 and Q9 as passed.

#### Scenario: Array record read back
- **GIVEN** a panel of 2 × 2 copies of `board.PcbDoc` with spacing 42 and 32 mm
- **WHEN** `uv run pytest tests/unit/backends/altium/test_embedded_array.py` writes the record and reads it back
- **THEN** the counts, spacing, location and rotation equal the written ones, and the stored document name is `../board/board.PcbDoc`

#### Scenario: Gate off
- **WHEN** `EMBEDDED_ARRAYS` is false and a panel is written with `--altium-panel auto`
- **THEN** `EmbeddedBoards6` has `Header` 0 and an empty `Data`, and the document is the flattened panel

### Requirement: Flattened panel documents
A flattened Altium panel SHALL be written from the panel's model through the lowering of a model: the board shape is the frame's rectangle, gap rings are tracks and arcs on a mechanical layer named `Route Tool Path`, score lines tracks on one named `V-Cut`, mouse-bite and tooling holes free round non-plated pads, fiducials free round copper pads.

#### Scenario: Flattened panel document
- **GIVEN** `tests/data/panels/tabs.py` written with `--target altium`
- **WHEN** `uv run pytest tests/unit/panel/test_altium_flat.py` reads the document back
- **THEN** it holds 8 copies of each component, the board shape is the frame's rectangle, the two named mechanical layers hold the gap rings and no score line (the fixture is tabbed), and each mouse-bite hole is a free pad with plating off and no copper

### Requirement: Polygon pour modes
`pcbdoc.write_pcbdoc(spec, *, pour="outline")` SHALL take the pour mode `outline` or `computed`.

#### Scenario: Detailed contract for polygon pour modes
- **WHEN** this behavior is exercised
- **THEN** the following detailed conditions MUST hold:

`pcbdoc.write_pcbdoc(spec, *, pour="outline")` SHALL take the pour mode `outline` or `computed`.
- With `outline`, every polygon MUST be written unpoured with its net, layer, outline, priority (as the pour index) and island removal, the document's bytes MUST be those the writer gave for the same spec before change c0215, and the build MUST report `altium.zones-unpoured` (info) once, with the count.
- With `computed`, the writer MUST write the document without pour regions, read it back with Fenolite's reader, pour that reading with `pour.pour_reading` (capability `altium-pour`), and write the document again with the regions of every polygon that is not refused ("Refusal of a pour"). It MUST also write `OPTIMALVOIDROTATION=FALSE` in every polygon record and the Polygon Connect Style rules of "Polygon Connect Style records".
- `computed` without the `geo` extra MUST raise `BackendUnavailable` with a hint naming `fenolite[geo]`; a command maps it to exit 6.
- `pour_regions=False` (internal; for the kit's reference input and tests only) MUST give the bytes of the `computed` document without the regions of the polygons.

#### Scenario: Outline mode keeps the bytes
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pour_modes.py -k outline` writes every committed Altium sample with `pour="outline"`
- **THEN** each document equals its committed bytes

#### Scenario: Computed and reference inputs differ in the pour only
- **WHEN** the kit sample `pour` is written with `pour="computed"` and with `pour="computed", pour_regions=False`
- **THEN** the two documents differ only in `Regions6` and `ShapeBasedRegions6`, and in their headers' record counts

### Requirement: Poured regions
With the pour mode `computed`, `pcbdoc.write_pcbdoc` SHALL write each piece of a poured polygon as one region in `Regions6` and its twin at the same position in `ShapeBasedRegions6`, in the form of the fact rows of `docs/formats/altium/pcb-pour.md`, "Written form" (`H-A-POUR-REGION`).

#### Scenario: Detailed contract for poured regions
- **WHEN** this behavior is exercised
- **THEN** the following detailed conditions MUST hold:

With the pour mode `computed`, `pcbdoc.write_pcbdoc` SHALL write each piece of a poured polygon as one region in `Regions6` and its twin at the same position in `ShapeBasedRegions6`, in the form of the fact rows of `docs/formats/altium/pcb-pour.md`, "Written form" (`H-A-POUR-REGION`).
- The prefix MUST hold the polygon's layer, no net (`0xFFFF`: the net is the polygon's), the polygon's index (its position in `Polygons6`) and no component, with the flags `0C 00`.
- The keys and their order MUST be those of the census of poured regions in the public corpus (task 1.3 of change c0215). The plain form MUST hold the holes of the piece; the shape-based form MUST hold them in the form the census found, every vertex straight.
- The regions of the polygons MUST come together, in polygon order and then by the lowest point of each piece, at the place in the storage that the census found. Vertices MUST be whole units, each ring without a slit, at least three vertices.
- Fenolite's reader MUST read the written document back to zones whose fills equal the written pieces within one unit; KiCad's importer MUST read them as the zone's fills (`H-A-POUR-KICAD`).

#### Scenario: A piece with a hole read back
- **GIVEN** the poured `GND` polygon of the scenario "Clearance around a pad of another net" of `altium-pour`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pour_regions.py` writes it and reads it back
- **THEN** `Regions6` and `ShapeBasedRegions6` hold one region each, with the polygon's index and no net, and the read zone has one fill whose outer ring and hole equal the engine's within one unit

#### Scenario: KiCad imports the pour
- **WHEN** `uv run pytest tests/kicad/altium/test_pour_import.py -rA` imports the computed kit sample `pour` with `kicad-cli pcb import` (10.0.6)
- **THEN** each imported zone holds fills equal to the written pieces within 10 nm, and the zones of refused polygons hold none

Serialized native fill and hole counts may differ only when ALL imported copper passes the existing XOR-area limit AND a conservative continuous closed10nm band certificate around the written boundaries. Match every zone uniquely by layer/net and retain every fill/hole. Check exact rational differences before any integer realization; refuse unknown/resource-exhausted proofs. Remote narrow copper, missing interior copper, an out-of-band bridge and11nm displacement MUST fail. This does not alter the independent pourcompare M3 one-to-one topology contract.

### Requirement: Polygon Connect Style records
With the pour mode `computed` and at least one polygon, `pcbdoc.write_pcbdoc` SHALL write Polygon Connect Style rules (kind number 20) in `Rules6` after the kinds of "Design rule records", in the Advanced form of the fact rows of `docs/formats/altium/pcb-pour.md`, "Polygon Connect Style" (`H-A-POUR-CONNECT`), lowered from the zones (the maintainer's decision of 2026-10-26):

#### Scenario: Detailed contract for polygon connect style records
- **WHEN** this behavior is exercised
- **THEN** the following detailed conditions MUST hold:

With the pour mode `computed` and at least one polygon, `pcbdoc.write_pcbdoc` SHALL write Polygon Connect Style rules (kind number 20) in `Rules6` after the kinds of "Design rule records", in the Advanced form of the fact rows of `docs/formats/altium/pcb-pour.md`, "Polygon Connect Style" (`H-A-POUR-CONNECT`), lowered from the zones (the maintainer's decision of 2026-10-26):
- One rule scoped `InNet('<net>')` per net whose zones agree on `ZoneSettings.connection`, `thermal_gap`, `thermal_spoke_width` and `clearance` (through `effective()`): `thermal` is Relief Connect for through-hole and SMD pads; `thru_hole_only` is Relief Connect for through-hole pads and Direct Connect for SMD pads; `solid` is Direct Connect for both; `none` is No Connect for both with `clearance` as the air gap. A relief MUST have 4 conductors at 90°, the conductor width `thermal_spoke_width` and the air gap `thermal_gap`. Vias MUST be Direct Connect in every rule.
- One `All` rule from `ZoneSettings()`, with the last priority; priorities count from 1 within the kind, the net rules in net-name order.
- A net whose zones disagree MUST get the rule of its zone of highest priority (then the lowest zone id); each other zone of the net, and each pad with its own `zone_connection`, MUST give one `altium.not-lowered` with `where` `zone/<id>` or `pad/<id>`.
- In a rewrite of a read document, Polygon Connect Style records that map exactly (`connectstyle.read_connect_styles`) MUST be written back as they were read, and the lowering above applies only when one does not map; each record that does not map MUST be reported.
- Fenolite's reader MUST map the written records back to the same `connectstyle.ConnectStyle` values.

#### Scenario: One rule per net and a default
- **GIVEN** the kit sample `pour`, whose four probe nets of P2 hold zones with the connections `thermal`, `thru_hole_only`, `solid` and `none`
- **WHEN** it is written with `pour="computed"` and its rules are read back
- **THEN** `Rules6` holds the records of kind 20 of those four nets scoped `InNet`, the other probe nets' rules, and one `All` rule with the last priority; each maps back to the style of its net, and every via setting is Direct Connect

#### Scenario: Zones of one net disagree
- **GIVEN** two `GND` zones, the first of priority 1 with `thermal` and the second of priority 0 with `solid`
- **WHEN** the document is written with `pour="computed"`
- **THEN** the `GND` rule is Relief Connect, and one `altium.not-lowered` names the second zone

### Requirement: Kept rule records written back
The PCB document of a board that was read SHALL hold its kept rule records again.
- `pcbdoc.rule_records` MUST write each `kept_rule` record after the records it writes itself, with the record's kind number and keys.
- A kept record of a kind that the document already writes MUST take the next priorities of that kind, in its original priority order. Otherwise it MUST keep its own priority.
- A kept record whose name is already written MUST get the suffix `_kept`.
- A kept Plane Connect or Plane Clearance record MUST replace the default plane rule of its kind.

#### Scenario: Kept records survive a write
- **GIVEN** the imported document of "Rule records the writer cannot rebuild are kept"
- **WHEN** `uv run pytest tests/unit/backends/altium/test_kept_rules.py -k written` writes it and reads the written document back
- **THEN** the read-back holds the disabled width with `ENABLED=FALSE` and the Routing Topology record with its keys

### Requirement: Copper of a net-tie footprint

The Altium writer SHALL write each copper graphic of a footprint instance with net-tie groups as a primitive
of its component on the graphic's signal layer, without a net: a line as a track, an arc or a circle as an
arc, a filled rectangle or polygon as a region, a rectangle or polygon outline as tracks. It SHALL count each
under `footprint-copper` as written. A copper graphic of a footprint without net-tie groups, one on an
internal plane, and one that `pcbdoc.graphic_problem` refuses SHALL stay a `footprint-copper` loss.

#### Scenario: A net tie keeps its copper

- **GIVEN** the authored board `net_tie_copper.kicad_pcb`, whose net tie `NT1` holds an F.Cu line from pad 1
  (net `A`) to pad 2 (net `B`)
- **WHEN** it is converted to Altium without `--allow-lossy`
- **THEN** the conversion succeeds with no `footprint-copper` loss and nothing unexplained
- **AND** the PcbDoc holds one track on the top layer with the component's index and no net, and the
  component record holds `COMPONENTKIND=4`

#### Scenario: Copper no record holds stays refused

- **GIVEN** the same board with a filled circle on F.Cu in place of the line
- **WHEN** it is converted to Altium
- **THEN** the conversion is refused for a `footprint-copper` loss, and with `--allow-lossy` the
  `net-tie-copper` difference it causes is explained by that row

### Requirement: Source rule records written back
`PcbDocSpec.source_rules` SHALL hold the rule records of the Altium document a conversion started from (change c0434), each its kind number and its keys from `RULEKIND` on; it is empty for every build. With records there, `rule_records` SHALL write:
- first each record as it is, in its order, after the common keys;
- then each lowered rule of `spec.design_rules` with the next priority of its kind and a name not yet written (`_2`, `_3`…);
- then the kept records (change c0424).
- No rule of a net class and no `All` default MUST be written. The Plane Connect and Plane Clearance rules of c0389 are written only for a kind that no record holds. The Polygon Connect Style records lowered from the zones MUST NOT be written when a record is of that kind.

#### Scenario: Records and one lowered rule
- **GIVEN** a spec whose `source_rules` hold a Width named `Signal Width` of priority 3 and whose design rules lower to one Width named `Signal Width`
- **WHEN** `write_pcbdoc` runs
- **THEN** `Rules6` holds the record as given, then a Width named `Signal Width_2` of priority 4, and no other Width, Clearance or Routing Via Style record

### Requirement: Straight arcs and generated holes in a written document
The Altium lowering SHALL write an arc whose middle point lies on the segment between its two distinct ends
as the track from start to end with the arc's width, layer, net and lock, counted `changed` under `arc`
(`ARC_STRAIGHT`), and SHALL NOT leave it out. It SHALL write a footprint of the generated hole library
(`Fenolite_Holes`) without a reference and with one unplated pad as a free pad at the pad's board position,
counted `changed` under `footprint`, and SHALL NOT write a component for it (change c0435).

#### Scenario: A flat arc
- **WHEN** `uv run pytest tests/unit/backends/altium/test_straight_arc.py -q` writes the committed two-layer board whose first track is replaced by an arc through its middle
- **THEN** the write reports no loss, counts the arc changed, the read-back document holds one arc fewer and a track in its place, and `equivalent` reports no `equiv.route-length`

#### Scenario: Flow B with free holes
- **WHEN** `uv run pytest tests/unit/convert/test_flow_b_fidelity.py -k equivalent -q` converts an authored Altium document with two free holes to KiCad and back
- **THEN** the result holds the two free holes and no component for them, and `equivalent` of source and result exits 0

### Requirement: Rule areas of poured copper alone
A rule area that restricts poured copper and nothing else (no tracks, vias, pads or footprints), on the board or in a footprint, SHALL be written as a polygon cut-out: a region record with `KIND=1` and without the keep-out flag or restriction keys, on Multi-Layer (`V7_LAYER=MULTILAYER`) when it lies on every copper layer, else one per copper layer it names, owned by its component when it belongs to a footprint. This is the form of the cut-outs of documents saved by Altium (`pcb-records.md`, "Regions and keep-outs") and the form the import reads as such a rule area, so a document read and written again keeps each cut-out a cut-out instead of turning it into a keep-out that Altium's clearance rules check against every track, pad and via.

#### Scenario: Cut-outs stay cut-outs
- **GIVEN** a two-layer board with pour-only rule areas on both copper layers, on `F.Cu` and on `B.Cu`, a rule area that forbids tracks on both layers, and a pour-only rule area on `*.Cu` in a footprint
- **WHEN** the PCB document is written and read back
- **THEN** it holds free cut-out regions on Multi-Layer, Top and Bottom, one cut-out region of the component on Multi-Layer and one keep-out region (on the Keep-Out layer, for the track rule area), and the import reads the pour-only rule areas again with their layers and the footprint's area in its footprint

#### Scenario: The authored cut-out board
- **GIVEN** the authored board `polygon_cutouts.kicad_pcb`
- **WHEN** it is converted to Altium
- **THEN** its pour-only areas give two `KIND=1` regions (one on Top for the area on `F.Cu`, one on Multi-Layer for the area on both copper layers) with no keep-out flag and no net, its area that forbids tracks too is a keep-out region of restrictions 6, and the reading holds the two pour-only rule areas on their layers

### Requirement: Board outline arcs
`pcbdoc.board_record(..., arcs=...)` SHALL write vertex k of the outline whose index `PcbDocSpec.outline_arcs` holds as an arc vertex: `KIND<k>=1`, `CX<k>`, `CY<k>` and `R<k>` the circle through vertex k, the next point (the arc's mid, which is no vertex) and the point after it, in the document's frame, and `SA<k>`, `EA<k>` the start and end angle of the counter-clockwise sweep between the two ends that holds the mid (`docboard.OutlineArc`). The closing vertex MUST repeat vertex 0 with `KIND=0`. Three points on one line MUST give a straight edge.

#### Scenario: An arc of the edges
- **GIVEN** a KiCad board whose `Edge.Cuts` ring has three lines and an arc from (60, 40) mm through (30, 50) mm to (0, 40) mm
- **WHEN** `uv run pytest tests/unit/convert/test_convert_slots.py -k board_ring` converts it to Altium
- **THEN** nothing is counted under `outline`, the written outline has four vertices, one an arc vertex of radius 50 mm sweeping 73.74 degrees

### Requirement: Keep-out lines of the Keep-Out layer

The writer SHALL write a rule area whose name carries a stroke (`Altium.KeepOut/<kind>/<numbers>`, change
c0442) as that stroke when the area is intact. Intact means three things:

- its outline is the band of the stroke within 10 nm;
- it forbids tracks, vias, pads and poured copper;
- it does not forbid footprints.

The stroke SHALL be a track or an arc on the Keep-Out layer without the keep-out flag, free for a board's
area and owned by its component for a footprint's, with the stroke's width. The two rings of a circle
SHALL give one full arc, and only when both are intact. Each such area SHALL be counted written under
`keep-out`. A marked area that is not intact SHALL be written as any rule area is.

#### Scenario: A keep-out line comes back as a line

- **GIVEN** a board whose Keep-Out layer holds a line, an arc and a circle without a keep-out record, and a
  footprint holding such a line, converted into rule areas
- **WHEN** the board is written as a PCB document
- **THEN** the Keep-Out layer holds one free track, two free arcs and one track of the component, none with
  the keep-out flag, and no keep-out region for them

#### Scenario: An edited keep-out line stays an area

- **GIVEN** those rule areas, the line's no longer forbidding vias and the arc's moved by 1 mm
- **WHEN** the board is written
- **THEN** both are written as keep-out regions and only the circle comes back as an arc

### Requirement: Board cut-outs of a footprint

The writer SHALL write each closed `Edge.Cuts` outline of a footprint (a polygon of three vertices or more,
or a rectangle with an area) as one board cut-out region of its component: `KIND=0`, `ISBOARDCUTOUT=TRUE`,
the Keep-Out layer, no keep-out flag, the component's index. A board cut-out ring of the written outline
that is such an outline within 10 nm SHALL NOT be written again as a free cut-out. A line, an arc or a
circle of a footprint's edge SHALL be counted lost under `footprint-graphic`.

#### Scenario: A cut-out of a component comes back as one

- **GIVEN** a board whose footprint holds a closed `Edge.Cuts` outline, and an outline whose cut-outs hold
  that ring and another one
- **WHEN** the board is written
- **THEN** the document holds one board cut-out region of the component and one free one

### Requirement: Free pads of a converted board
`lower.converted_free_pad(fp, ref)` SHALL say whether a footprint is the form a free pad takes through an
Altium → KiCad conversion (change c0447): no reference, exactly one pad, and a link whose item name (after
its last `:`) starts with `fenolite.core.libnames.FREE_PAD_PREFIX` (`FREE_`). `from_design` MUST write
such a footprint as a free pad with its net, as it writes the import's reading of one, and count it
changed under `footprint` with `lower.FREE_PAD_REASON`. A footprint with a reference MUST be written as a
component whatever its link.

#### Scenario: A converted free pad
- **GIVEN** a design with a footprint `p:FREE_fp_1` holding one pad of net `N` and no component, and a
  footprint `p:FREE_fp_2` of component `R9`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower_free_pads.py -n 0 -q` runs `from_design`
- **THEN** the first is one free pad of net `N` and no component, counted changed with `FREE_PAD_REASON`;
  the second is the component `R9`

### Requirement: Empty texts of a component
The PCB document writer SHALL write the comment text record of a component whose model holds a placed
`Value` field (`PlacedComponent.comment_place`) also when the comment is empty, with that place and its
shown flag, as a saved document holds it (change c0451; four records of `altium-third-party-pcbdoc-01`). A
component without a placed field and without a comment MUST get no comment record, as before. A text of a
footprint without characters MUST be written (`pcbdoc.text_problem_of(text, footprint=True)` is `None` for
it); a board text without characters MUST stay refused.

#### Scenario: Empty value and empty text
- **GIVEN** the authored `routed` sample whose component `R1` has an empty value and a hidden `Value` field,
  and whose footprint `U1` holds a text without characters on `F.SilkS`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower_empty_texts.py -n 0 -q` writes it with
  `lower.write_design(..., rewrite=True)` and reads it back
- **THEN** `R1` holds a hidden `Value` field at its place, `U1` holds the empty text, and a board text
  without characters is counted under `text` as not written

### Requirement: Derived libraries named by the source
`lower.derived_library` SHALL put the derived footprint of a footprint whose link names an Altium library
(`project.is_altium_footprint`: its library part ends with `.PcbLib`) into a library of that file name, and
every other derived footprint into `<name>.PcbLib`, one definition per file and pattern; each component
links the file of its footprint (`footprint_library`, and the schematic part's footprint link).
`lower.write_design` and `project.write_project(..., extra_footprints=...)` MUST write each such file and
list it in the project file (change c0451). A design without such a link writes `<name>.PcbLib` alone, as
before.

#### Scenario: A source library comes back as a file
- **GIVEN** the KiCad project of the conversion of the authored `routed` sample whose `D1` links `Lib_A`
- **WHEN** `uv run pytest tests/unit/convert/test_round_trip_texts.py -n 0 -q -k links` converts it to Altium
- **THEN** the written project holds `Lib_A.PcbLib` with `Mini_LED_THT_3mm` and `Sym_A.SchLib`, the project
  file lists both, and `D1` links them

### Requirement: Embedded model bodies
`pcbdoc.write_pcbdoc` SHALL write each `PlacedBody` of `PcbDocSpec.bodies` that carries a model (`PlacedBody.model`, change c0449) as a body record that names an embedded model, and SHALL write the models it names into the `Models` storage (`pcb-bodies.md`, "Written form of a model body"; S-0816, S-2080; `H-A-BODY-MODEL-PLACE`).
- `Models/Data` MUST hold one record per distinct model data, in the order of first use: a 32-bit length and the property text `EMBED=TRUE|MODELSOURCE=Undefined|ID=<id>|ROTX=<x>|ROTY=<y>|ROTZ=<z>|DZ=<dz>|CHECKSUM=0|NAME=<name>` ending in a NUL, with the turns and the rise of the first body that names it (`DZ` as integer file units). `ID` MUST be `pcbrecords.model_id(data)`: a GUID in braces upper-case from the SHA-256 of `fenolite.altium.model:` and the hex SHA-256 of the data. `Models/Header` MUST be the record count as a 32-bit integer, and `Models/<n>` MUST be record `n`'s data deflated by `zlib` at level 6.
- The body record MUST hold the 34 keys of a saved model body, in order: the first 21 keys of an extruded body, `MODELID` (the record's `ID`), `MODEL.CHECKSUM=0`, `MODEL.EMBED=TRUE`, `MODEL.NAME`, `MODEL.2D.X`, `MODEL.2D.Y`, `MODEL.2D.ROTATION=0.000`, `MODEL.3D.ROTX`, `MODEL.3D.ROTY`, `MODEL.3D.ROTZ`, `MODEL.3D.DZ`, `MODEL.MODELTYPE=1` and `MODEL.MODELSOURCE=Undefined`; `BODYCOLOR3D=8421504`; the turns as degrees in [0, 360) with three decimals; `STANDOFFHEIGHT` MAY be negative. Both body storages MUST hold it, as an extruded body's twin.
- A spec without a model body MUST write `Models` with `Header` 0 and an empty `Data`, as before.
- A model whose data is empty, a name that the record cannot hold (empty, or a character other than a letter, a digit, a space or one of `_.()+-`), or an overall height not above the standoff MUST raise `ValueError` naming the body.

#### Scenario: One model named by two bodies
- **GIVEN** a spec with two components whose bodies carry the same STEP data, the second turned by 90 degrees, and a third body that carries other data
- **WHEN** `uv run pytest tests/unit/backends/altium/test_model_bodies.py -k records` writes and reads the document
- **THEN** `Models/Data` holds two records, `Models/Header` is 2, `Models/0` inflates to the first data, the three body records hold `MODEL.MODELTYPE=1` and the `MODELID` of their record, the first record holds the first body's `ROTZ`, and `ComponentBodies6` and `ShapeBasedComponentBodies6` hold three records each

#### Scenario: No model, no entry
- **WHEN** a spec without a model body is written
- **THEN** `Models/Header` is 0, `Models/Data` is empty (`test_model_bodies.py -k records`), and the document's bytes equal those written before change c0449 (`uv run python tools/gen_altium_graduation.py --check`)

### Requirement: Keep-out fills of a converted board

The writer SHALL write a rule area named with the marker of a keep-out fill
(`Altium.KeepOut/flag<r>/fill/<corners>`) as a fill record of its signal layer in the 50-byte form, with the
keep-out flag and the restriction byte r at 46, of the area's component for an area of a footprint, when the
area is still its fill's: one layer, what r forbids and no more, and the four corners, a rectangle, as its
outline. Any other area SHALL stay a keep-out region.

#### Scenario: A keep-out fill comes back as a fill

- **GIVEN** a KiCad board converted from an Altium document with a keep-out fill of a component on the
  bottom layer with the restriction byte 24
- **WHEN** the board is converted to Altium
- **THEN** the document holds one fill record of the component on the bottom layer with the keep-out flag
  and the byte 24, and no keep-out region in its place

#### Scenario: An edited keep-out fill stays an area

- **GIVEN** the area of a keep-out fill edited to forbid vias too
- **WHEN** the board is written as an Altium document
- **THEN** the area is a keep-out region and no fill record is written for it

### Requirement: Kept classes, xSignals and differential pairs

Given carried storages (`PcbDocSpec.kept_storages`), the writer SHALL:
- write the records of `Classes6.Kept` into `Classes6` after its own, leaving out a record whose kind and
  casefolded name a written class holds;
- write the records of `SignalClasses.Kept` after `All xSignals`;
- write the `Board6.PinPairs` keys in `Board6` in place of `PINPAIRCOUNT=0`;
- write the records of `DifferentialPairs6` into that storage.

With `Classes6.Kept` given, the writer SHALL NOT write its own sheet component classes. It SHALL NOT write a
net class without members whose name no rule scope names.

#### Scenario: A class of another kind shares a net class's name

- **GIVEN** a spec with the net class `CELL` and a kept kind-5 class `Cell`
- **WHEN** the document is written
- **THEN** `Classes6` holds both

### Requirement: A carried origin keeps the document frame

Given a document origin (`write_design(frame_origin=…)`), the Altium writer SHALL write a board that was
not read from a PCB document in the document frame, each point at `(x, −y)`, and SHALL write `ORIGINX` and
`ORIGINY` at that origin. When a point of the outline would lie at a negative coordinate, it SHALL anchor
the board at its corner as without an origin and record a change of kind `outline`.

#### Scenario: An origin above the corner

- **GIVEN** a board read from KiCad whose outline's low corner is at (25.4 mm, −55.4 mm) in the frame of the
  design, and the frame origin (25.4 mm, 26.162 mm) in the document's
- **WHEN** it is written
- **THEN** the outline's lowest vertex is at 1000 mil, 1000 mil, `ORIGINX` is 1000 mil and `ORIGINY`
  1030 mil

#### Scenario: A board below KiCad's X axis is anchored

- **GIVEN** a board read from KiCad whose outline lies at positive KiCad Y, and a frame origin
- **WHEN** it is written
- **THEN** it is anchored at its corner, `ORIGINX` and `ORIGINY` are 1000 mil, and one `outline` change
  holds the reason `FRAME_ANCHORED`

### Requirement: Copper of a footprint with a net

The writer SHALL write a copper graphic of a footprint without net-tie groups whose `net_id` names a net of
the written board as records of its component on its signal layer, each with that net's index: a filled
rectangle or polygon as one region, a line, a drawn shape, a circle or an arc as tracks and arcs. A copper
graphic of such a footprint without a net, or on a plane, SHALL stay counted lost under `footprint-copper`.

#### Scenario: A component region comes back with its net

- **GIVEN** a board whose footprint holds a filled polygon on `F.Cu` with the net `5V`
- **WHEN** the board is written
- **THEN** the document holds one region of the component on the top layer with the index of `5V`

### Requirement: Fills of a converted board

The writer SHALL write a filled rectangle, or a filled polygon of four corners that is a rectangle within
10 nm, whose KiCad uuid is tagged as an Altium fill as one fill record of its layer, net and owner: the
50-byte form with the rotation of its first edge. Any other filled shape SHALL stay a region.

#### Scenario: A fill comes back as a fill

- **GIVEN** a KiCad board converted from an Altium document with a free fill and a fill of a component
- **WHEN** the board is converted to Altium
- **THEN** the document holds two fill records, one of them with the component's index, and no region in
  their place

#### Scenario: A component's copper fill of no net comes back

- **GIVEN** a footprint without net ties that holds a tagged fill of no net on a copper layer (row `-04`'s
  J1 holds six on the Top Layer)
- **WHEN** the board is converted to Altium
- **THEN** each is a fill record of no net on that layer with the component's index, and a copper graphic
  of no net that is not tagged stays refused

### Requirement: Keep-out strokes of a converted board

The writer SHALL write a rule area named with the marker of a keep-out stroke (`Altium.KeepOut/flag<r>/…`)
as a keep-out track or arc of its signal layer, with the keep-out flag and the restriction byte r in the
long form (49 bytes for a track, 60 for an arc), of the area's component for an area of a footprint, when the
area is still its stroke's: one layer, what r forbids and no more, and the band of the stroke as its outline.
The two rule areas of a circle SHALL give one arc. Any other area SHALL stay a keep-out region.

#### Scenario: A keep-out stroke comes back as a stroke

- **GIVEN** a KiCad board converted from an Altium document with a keep-out circle of a component on the top
  layer that forbids everything (r = 31)
- **WHEN** the board is converted to Altium
- **THEN** the document holds one keep-out arc of the component on the top layer, in the 60-byte form with
  the byte 31, and no keep-out region in its place

#### Scenario: An edited keep-out stroke stays an area

- **GIVEN** the area of a keep-out stroke edited to forbid vias too
- **WHEN** the board is written as an Altium document
- **THEN** the area is a keep-out region and no keep-out track is written for it

#### Scenario: A plain circle of the Keep-Out layer comes back whole

- **GIVEN** the two rule areas that a conversion makes of a circle drawn on the Keep-Out layer without the
  keep-out flag (change c0442)
- **WHEN** the board is written as an Altium document
- **THEN** the document holds one arc of the Keep-Out layer for them and no keep-out region

### Requirement: Texts on Mechanical 17 to 32

The writer SHALL write a text on Mechanical 17 to 32 whose Altium bag holds the source's bytes from 137 on
of its first subrecord (`text_tail`) in the source's 232- or 252-byte form: the layer byte of Mechanical 16,
its 137 bytes, then those bytes with the layer's long id at 226. Every other text SHALL keep the 137-byte
form.

#### Scenario: A text on Mechanical 17 to 32 keeps its long id

- **GIVEN** an Altium document with a 252-byte text whose layer byte is 72 and whose long id at 226 is
  Mechanical 20, and a 137-byte text on Mechanical 16
- **WHEN** it is converted to KiCad and back
- **THEN** the first text comes back with 252 bytes, the byte 72, the long id of Mechanical 20 and the same
  bytes from 137, and the second in the 137-byte form

### Requirement: Width 0 on mechanical layers

The writer SHALL write a line or an arc of width 0 on a layer the document names as Mechanical 1 to 32
(`Mech.<n>` of a board that was read, or a KiCad user layer named after a mechanical layer), free or of a
component, with width 0. A drawn shape of width 0 on any other layer (copper, `F.Fab` and the other
layers of the fixed KiCad map), a drawn rectangle, circle or polygon of width 0 and a
negative width SHALL stay refused.

#### Scenario: A line of width 0 on a mechanical layer

- **GIVEN** an Altium document with a free track, a component track and a component arc of width 0 on
  Mechanical 1
- **WHEN** it is converted to KiCad and back
- **THEN** the document holds the three of them on Mechanical 1 with width 0, and a line of width 0 on a
  silkscreen or copper layer is still refused

### Requirement: A text with a font face is a TrueType text

The Altium PCB writer SHALL write a text or a field that has a `face` as a text record of font type 1,
with the face as its font name and its bold and italic bytes. It SHALL NOT refuse such a text unless its
face is longer than the record's 31 characters. It SHALL still refuse bold or italic without a face, and
knockout.

#### Scenario: A free text with a face

- **GIVEN** a free board text with the face `Arial` and `bold` set
- **WHEN** the board is written
- **THEN** its text record holds font type 1, bold 1 and the font name `Arial`

### Requirement: Zero-height TrueType footprint text keeps its record

The Altium PCB writer SHALL write an ordinary footprint text with both dimensions zero, a valid
TrueType face and positive stroke width as a component text of height zero. Free board texts,
footprint fields and footprint stroke texts SHALL continue to require positive height.

#### Scenario: A zero-height TrueType footprint text returns from KiCad

- **GIVEN** a KiCad footprint text with size `0 0`, a TrueType face and positive stroke width
- **WHEN** the board is converted to Altium
- **THEN** its text record keeps the owning component, text, face, rotation, stroke and height zero

### Requirement: Union members are written with their index

The Altium PCB writer SHALL write the union index that `PcbDocSpec.unions` gives an entity id at offset 70
of the via record of that id, and as `UNIONINDEX` of the region or component record of that id. It SHALL
write a free track or arc that is a union member in the long form of its record (49 and 60 bytes) with the
index at offset 36 and 48, the long id of its layer and the restriction byte 0. It SHALL write the index of
a free text member, and of a member component for its designator and comment, at offset 119 of the text
record. Every other record SHALL keep 0.

#### Scenario: A via written with its union

- **GIVEN** a `PcbDocSpec` whose `unions` give the via `v1` the index 1048581
- **WHEN** the document is written
- **THEN** the record of `v1` holds 1048581 at offset 70 and every other via holds 0

#### Scenario: A text keeps its union

- **GIVEN** a board whose free text and whose first footprint are members of the union 77
- **WHEN** the document is written
- **THEN** the free text's record and the component's designator and comment records hold 77 at offset 119,
  and every other text 0

#### Scenario: A length tuning comes back in its union

- **GIVEN** a board whose first track is a member of the union 17 and whose arc is a member of the union 19
- **WHEN** the document is written
- **THEN** the track record is 49 bytes with 17 at offset 36 and the arc record 60 bytes with 19 at offset
  48, and every other track keeps 36 bytes

### Requirement: A stroke text is written with the font its bag names

The Altium PCB writer SHALL write a text or a field without a face whose `altium` bag holds a well-formed
`stroke_font` as a text record of font type 0 with that font name, bold and italic. A text without one, or
with a value that is not two flags, a space and a name of at most 31 characters, SHALL be written with no
font name, as before.

#### Scenario: A stroke free text with its font

- **GIVEN** a free board text without a face whose `altium` bag holds `stroke_font` = `11 Trebuchet MS`
- **WHEN** the board is written
- **THEN** its text record holds font type 0, bold 1, italic 1 and the font name `Trebuchet MS`

### Requirement: Empty texts and line breaks are written

The Altium PCB writer SHALL write a board text whose string is empty as a text record with an empty
string, and SHALL write each line feed of a text's string as CR LF (`H-A-TEXT-CRLF`) in the record and in
its wide string. It SHALL still refuse a text that holds any other control character.

#### Scenario: An empty text and a two-line text

- **GIVEN** a board with a free text whose string is empty and one whose string is `two\nlines`
- **WHEN** the board is written
- **THEN** both texts have a record, the second holds `two\r\nlines`, and reading the document back gives
  an empty string and `two\nlines`

### Requirement: Carried plane splits, names and pull-backs

Given split polygons for an internal plane (`PcbDocSpec.plane_splits`), the writer SHALL write one Split
Plane polygon per split, on the split's net, instead of the board outline on the plane's net. It SHALL
accept `(Multiple Nets)` as the net of such a plane. It SHALL write each plane's pull-back
(`StackSpec.pullbacks`, else 20 mil), and it SHALL name a plane after `PcbDocSpec.copper_names` where the
spec gives a name. Without them, the document SHALL be as before.

#### Scenario: A (Multiple Nets) plane with two splits

- **GIVEN** a four-layer spec whose first plane is `(Multiple Nets)` with splits on `GND` and `VCC`, named
  `Ground Plane`, with a pull-back of 30 mil
- **WHEN** the document is written
- **THEN** `PLANE1NETNAME` is `(Multiple Nets)` and Internal Plane 1 is named `Ground Plane`
- **AND** `Polygons6` holds two Split Plane polygons on that layer, on `GND` and `VCC`
- **AND** the plane's `PULLBACKDISTANCE` is 30 mil

### Requirement: Carried signal layer names

The writer SHALL name a signal layer (ids 1 to 32) after `PcbDocSpec.copper_names` where the spec gives a
name, in every `Board6` key that holds the layer's name. For a design read from KiCad, the spec SHALL give a
signal layer its row's user name, unless a property record cannot hold it, it is the name of another Altium
layer, or two layers take it; such a layer keeps Altium's name.

#### Scenario: A KiCad row's user name names its layer

- **GIVEN** a two-layer KiCad board whose `F.Cu` row is named `Component Side` and whose `B.Cu` row is named
  `Top Overlay`
- **WHEN** it is converted to Altium
- **THEN** the top layer is named `Component Side` and the bottom layer `Bottom Layer`

