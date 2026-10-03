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
- The common prefix of a track, arc and pad geometry MUST be: layer byte, flags `0x0C 0x00` (unlocked), net index, polygon index `0xFFFF`, component index (all uint16, `NO_INDEX = 0xFFFF` for none), then `FF FF FF FF`.
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
- Subrecord 5 MUST be 114 bytes: the prefix; x, y; top, middle and bottom size equal to the pad size; hole size (the drill, 0 for SMD); top, middle and bottom shape; rotation; plated (1 only for `thru_hole`); pad mode 0; the values S-0150 writes at offsets 63 to 85; mask expansions 0; paste mode 0 and solder mode 1; the int32 at 106 and the bytes 110 to 113 zero.
- Shapes: `circle` and `oval` MUST be shape 1 (round; an oval has unequal sizes), `rect` shape 2, `roundrect` shape 1 with subrecord 6.
- Subrecord 6 MUST be empty, except for a `roundrect` pad: 596 bytes, every inner size equal to the pad size, every inner shape 1, hole shape 0, no slot, zero offsets, the rounded-rectangle flag 1, every alternate shape 9 and every corner percentage `round(200 · ratio)` clamped to 0 … 100, where `ratio` is the pad's corner ratio (`H-A-PCB-PAD`).
- The pad rotation MUST be the pad angle in degrees; KiCad's and Altium's positive angles both turn counter-clockwise on screen (`H-G-ROT-DIR`).

#### Scenario: Roundrect pad
- **WHEN** a `roundrect` pad `1` of 0.9 × 0.95 mm at (−0.8, 0) mm with ratio 0.25 is written
- **THEN** the test decoder reads subrecord 5 of 114 bytes with shape 1, sizes 354331 × 374016, x −314961 and y 0, and subrecord 6 of 596 bytes with alternate shape 9 and percentage 50

#### Scenario: Through-hole pads
- **WHEN** the mini LED footprint's pads are written
- **THEN** both are on layer 74 with hole size 354331 and plated 1, pad `1` has shape 2 and pad `2` shape 1, and both have an empty subrecord 6

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
`pcbrecords.LAYER_MAP` SHALL also map the inner copper layers as signal layers, `pcbrecords.COPPER_LAYER_TEXT` SHALL give the layer text of each signal copper layer in a property record, and `pcbrecords.copper_stack` SHALL give the Altium ids of a stack whose inner layers are signal layers or internal planes (S-0002, S-0160, S-0176, S-0199, S-0200). This requirement extends c0035's "PCB layer map", whose eight rows and pairs hold unchanged.

| Fenolite layer | as | Altium id | Altium name | layer text |
|---|---|---|---|---|
| `F.Cu` | signal | 1 | Top Layer | `TOP` |
| `In1.Cu` | signal | 2 | Mid-Layer 1 | `MID1` |
| `In2.Cu` | signal | 3 | Mid-Layer 2 | `MID2` |
| `B.Cu` | signal | 32 | Bottom Layer | `BOTTOM` |
| first inner layer that is a plane | plane | 39 | Internal Plane 1 | (no primitive is written on it) |
| second inner layer that is a plane | plane | 40 | Internal Plane 2 | (no primitive is written on it) |

- `pcbrecords.copper_stack(names, planes=())` MUST return the Altium ids of a board's copper layers from top to bottom. `names` MUST be exactly `("F.Cu", "B.Cu")` or `("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")`; `planes` MUST name only inner layers of `names`, without repeats. Any other input MUST raise `ValueError` naming it.
- A signal inner layer keeps its row of the table whatever the other inner layer is. Planes are numbered from the top: the first plane is Internal Plane 1, the second Internal Plane 2. So Mid-Layer 2 may be written without Mid-Layer 1, a state Altium saves (S-0200).
- `LAYER_MAP` and `COPPER_LAYER_TEXT` MUST NOT hold a plane: a primitive on a plane layer has no id (`ValueError`).
- No inner layer has a flip partner: `FLIP_PAIRS` MUST stay as c0035 wrote it.

#### Scenario: Four signal layers
- **WHEN** `pcbrecords.copper_stack(("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"))` runs
- **THEN** it returns `(1, 2, 3, 32)`

#### Scenario: Planes numbered from the top
- **WHEN** `copper_stack` runs for the four layers with `planes=("In1.Cu",)`, with `planes=("In2.Cu",)` and with `planes=("In1.Cu", "In2.Cu")`
- **THEN** it returns `(1, 39, 3, 32)`, `(1, 2, 39, 32)` and `(1, 39, 40, 32)`

#### Scenario: Other stacks refused
- **WHEN** `copper_stack` gets `("F.Cu", "In1.Cu", "B.Cu")`, `("F.Cu", "In2.Cu", "In1.Cu", "B.Cu")`, `planes=("F.Cu",)` with four layers, or `planes=("In1.Cu",)` with two layers
- **THEN** each call raises `ValueError` that names the input

### Requirement: Four-layer stack
`docboard.board_records(..., stack=…)` SHALL write the layer stack of a `docboard.StackSpec` with two or four copper layers, each inner layer a signal layer or an internal plane with a net (`docs/formats/altium/pcb-copper.md`, "Layer stack"; S-0160, S-0176, S-0199, S-0200; `H-A-PCB-CU-STACK`, `H-A-PCB-CU-PLANE`).
- `StackSpec` MUST hold `copper` (the Altium ids from top to bottom, as `copper_stack` gives them), one copper thickness per layer, one `Dielectric(kind, thickness, epsilon_r, material)` between each pair of neighbours (`kind` is `unspecified`, `core` or `prepreg`; lengths in nanometres), and `plane_nets`, one net name per plane of `copper`, in plane order. A `plane_nets` whose length differs from the number of planes, or a net name that fails `text_problem`, MUST raise `ValueError`.
- `StackSpec.default(copper, plane_nets=())` MUST give 1.4 mil copper and, for two layers, the dielectric of c0035 (`unspecified`, 12.6 mil, `4.800`, `FR-4`); for four layers a prepreg of 0.2 mm, a core of 1.0 mm and a prepreg of 0.2 mm, each `4.800` and `FR-4`. These values are Fenolite's choices.
- For two copper layers and the default stack, the record MUST equal the record of c0035 byte for byte.
- For four copper layers the numbered keys MUST link the four ids of `copper` in order through `LAYER<id>PREV` and `LAYER<id>NEXT` (0 before the first and after the last); every other copper link stays 0. Each linked layer MUST carry its `COPTHICK`, and each but the bottom the dielectric below it (`DIELTYPE`, `DIELCONST`, `DIELHEIGHT`, `DIELMATERIAL`).
- The physical stack of the `V9_STACK_LAYER<i>` list and the head of the `LAYER_V8_<i>` list MUST hold 13 layers: paste, overlay, solder, `Top Layer`, `Dielectric 1`, the first inner layer, `Dielectric 2`, the second inner layer, `Dielectric 3`, `Bottom Layer`, solder, overlay, paste. The dielectrics MUST have the long ids 17039361, 17039362 and 17039363 from the top (the numbering S-0199 saves).
- A **signal** inner layer MUST be written as S-0199 and S-0200 save it: `NAME` (`Mid-Layer <n>`), `LAYERID` (16777217 + n), `USEDBYPRIMS`, `COPTHICK` and `COMPONENTPLACEMENT=1`.
- A **plane** MUST be written as S-0176 saves it: `NAME` (`Internal Plane <k>`), `LAYERID` (16842752 + k), `USEDBYPRIMS`, `COPTHICK` and `PULLBACKDISTANCE=20mil`; and line 1 of the record MUST hold `PLANE<k>NETNAME=<net name>`. Every other `PLANE<n>NETNAME` stays `(No Net)`.
- No primitive is written for a plane: no `Split Plane` polygon record, no pull-back track and no region (`H-A-PCB-CU-PLANE`); its `USEDBYPRIMS` is `FALSE`. Split planes are not written.
- The cache list MUST hold every layer once, in the form S-0176 saves (found when the written stack was compared with it, 2026-10-03): the 102 layers of a two-layer document in their order, then `Dielectric 2` and `Dielectric 3`. A mid layer or a plane of the stack keeps its place in its run and carries its stack keys.
- `pcbdoc.write_pcbdoc` MUST take the stack from `PcbDocSpec.stack` (`None` is `StackSpec.default` for `PcbDocSpec.copper_layers` without planes) and MUST raise `ValueError` when `stack.copper` does not hold one id per name of `copper_layers`, or when a plane's net is not in `PcbDocSpec.nets`.
- `DIELTYPE` MUST be 0 for `unspecified`, 1 for `core` and 2 for `prepreg`; `DIELCONST` three decimals; `DIELHEIGHT` and `COPTHICK` mil text.
- The layer set `&Signal Layers` MUST also list the signal inner layers (`MidLayer1`, `MidLayer2`), `&Plane Layers` the planes (`InternalPlane1`, `InternalPlane2`), and `&All Layers` both. The drill pair stays `LAYERPAIR0LOW=TOP`, `LAYERPAIR0HIGH=BOTTOM`.
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
`pcbrecords.via_record(x, y, diameter, hole, *, net=NO_INDEX)` SHALL write one through via as record type 3 with one subrecord of 321 bytes, the form Altium saves (S-0150, S-0160, S-0173, S-0172, S-0174, S-0175, S-0176; `H-A-PCB-CU-VIA`).
- The subrecord MUST start with the common prefix on layer 74 with flags `0C 00`, polygon and component `0xFFFF`; then x at 13, y at 17, the diameter at 21, the hole at 25, the start layer 1 at 29 and the end layer 32 at 30.
- The later fields MUST follow the rows of `pcb-copper.md`, "Via": thermal-relief air gap 10 mil at 32, 4 conductors at 36, conductor width 10 mil at 38, 20 mil at 42 and at 46, solder-mask expansion 4 mil at 54 and at 242, stack mode 0 at 74, thirty-two diameters at 75, the 16-bit 15 and the 32-bit 259 at 203, `2A` at 254, `0x7FFFFFFF` at 291 and at 295, the entry size 30 at 304, 9 at 308 and 1 at 320; every other byte 0.
- `pcbdoc.write_pcbdoc` MUST write each `model.board.Via` of `PcbDocSpec.vias` in `Vias6`, sorted by net name, position, diameter and then entity id, at its converted position, with its net's index. It MUST raise `ValueError` for a via whose `via_type` is not `through`, whose `layers` are not the top and the bottom copper layer, or whose drill is not below its diameter.
- Vias MUST NOT be listed in `UniqueIDPrimitiveInformation`.

#### Scenario: Via bytes
- **WHEN** `via_record(393701, 393701, 236220, 118110, net=2)` runs
- **THEN** the record is `03`, the length 321 and a subrecord whose bytes 0 to 4 are `4A 0C 00 02 00`, whose bytes 29 and 30 are `01 20`, and whose 32-bit values at 21, 25, 75 and 199 are 236220, 118110, 236220 and 236220

#### Scenario: Blind via refused
- **WHEN** a spec holds a via with `via_type="blind"` between `F.Cu` and `In1.Cu`
- **THEN** `write_pcbdoc` raises `ValueError` naming the via's id

### Requirement: Polygon pour records
`pcbdoc.write_pcbdoc` SHALL write each `model.board.Zone` of `PcbDocSpec.zones` as one `Polygons6` property record per zone layer, without poured copper (S-0160, S-0172, S-0174, S-0175, S-0176, S-0195, S-0196; `H-A-PCB-CU-REPOUR`).
- A record MUST hold, in this order: the seven common keys with `LAYER` = the layer text; `PRIMITIVELOCK=TRUE`, `POLYGONTYPE=Polygon`, `POUROVER=TRUE`, `REMOVEDEAD=TRUE`, `GRIDSIZE=20mil`, `TRACKWIDTH=8mil`, `HATCHSTYLE=Solid`, `USEOCTAGONS=FALSE`, `MINPRIMLENGTH=3mil`; per vertex `KIND<k>=0`, `VX<k>`, `VY<k>`, `CX<k>`, `CY<k>`, `SA<k>`, `EA<k>`, `R<k>` as the board outline writes them, the first vertex repeated last; `SHELVED=FALSE`, `RESTORELAYER=UNKNOWN`, `RESTORENET` (empty), `REMOVEISLANDSBYAREA=TRUE`, `REMOVENECKS=TRUE`, `AREATHRESHOLD=250000000000.000000`, `ARCRESOLUTION=0.5mil`, `NECKWIDTHTHRESHOLD=5mil`, `POUROVERSTYLE=1`, `NAME`, `POURINDEX`, `IGNOREVIOLATIONS=FALSE`, `AUTONAME` (only when the name is generated), `OPTIMALVOIDROTATION=TRUE`, and `NET` (the net's index; left out without a net).
- `NAME` MUST be the character codes of the name in decimal, joined by commas. The name is `Zone.name`, or `<net name>_L<layer position, two digits from 01>_P<pour index, three digits>` when it is empty (`NONET` stands for a missing net), in upper case, with `AUTONAME=TRUE`.
- `POURINDEX` MUST number the records from 0 in the order of falling `Zone.priority`, then net name, first outline point, zone id and stack position, so a zone of higher priority is poured first.
- `Regions6` and `ShapeBasedRegions6` MUST stay empty, and `Zone.fills` MUST NOT be written: the polygons are unpoured, and Altium fills them on a repour.
- A zone with fewer than three outline points, a zone layer outside the copper layers or on a plane, or a name that fails `text_problem` MUST raise `ValueError` naming the zone's id.

#### Scenario: Ground zone on two layers
- **GIVEN** a zone on `In1.Cu` and `B.Cu` with the net `GND`, four outline points and priority 0, and a second zone on `F.Cu` with priority 2
- **WHEN** `Polygons6` is read
- **THEN** it holds three records; the `F.Cu` record has `POURINDEX=0`; the two `GND` records have `LAYER=MID1` and `LAYER=BOTTOM`, five vertices, `NET` equal to the index of `GND`, and names that decode to `GND_L02_P001` and `GND_L04_P002`; `Regions6` is empty

#### Scenario: Zone without an outline refused
- **WHEN** a spec holds a zone whose `outline` is empty
- **THEN** `write_pcbdoc` raises `ValueError` naming the zone's id

### Requirement: Net class records
`pcbdoc.write_pcbdoc` SHALL write one `Classes6` property record per `pcbdoc.NetClassSpec` of `PcbDocSpec.net_classes`, in name order (S-0160, S-0161, S-0172, S-0174, S-0175, S-0176; `H-A-PCB-CU-CLASS`).
- A record MUST hold, in this order: the seven common keys with `LAYER=MULTILAYER`, `NAME`, `KIND=0`, `SUPERCLASS=FALSE`, the members `M0`, `M1`, … (the class's net names in name order), `SELECTED=FALSE`, `SCHAUTOGENERATEDCLUSTER=FALSE` and `UNIQUEID` = `project.unique_id("pcbdoc:<filename>:class:<name>")`.
- A class without a member MUST still be written. The super classes and the generated component classes of Altium-saved documents are not written.
- A class name that fails `text_problem` or holds `'`, or a member that `PcbDocSpec.nets` does not hold, MUST raise `ValueError`.

#### Scenario: Class of the blink sample
- **WHEN** `Classes6` of the blink sample is read
- **THEN** it holds one record with `NAME=PWR`, `KIND=0`, `M0=GND`, `M1=VIN` and no `M2`

### Requirement: Design rule records
`pcbdoc.write_pcbdoc` SHALL write `Rules6` with Clearance, Width and Routing Via Style rules from the net classes (S-0160, S-0161, S-0172, S-0174, S-0175, S-0176; `H-A-PCB-CU-RULES`). This requirement is the change's cut: when it is cut, `Rules6` stays empty. Rules MUST be written only when the spec holds a track, an arc, a via, a zone or a net class; otherwise `Rules6` MUST be empty.
- Each rule MUST be a 16-bit rule-kind number (0 Clearance, 2 Width, 11 RoutingVias), then one property block with, in this order: the seven common keys with `LAYER=TOP`, `RULEKIND`, `NETSCOPE` (`DifferentNets` for Clearance, `AnyNet` otherwise), `LAYERKIND=SameLayer`, `SCOPE1EXPRESSION`, `SCOPE2EXPRESSION=All`, `NAME`, `ENABLED=TRUE`, `PRIORITY`, `COMMENT` (empty), `UNIQUEID` = `project.unique_id("pcbdoc:<filename>:rule:<name>")`, `DEFINEDBYLOGICALDOCUMENT=FALSE`, then the kind's keys.
- Kind keys: Clearance `GAP`, `GENERICCLEARANCE`, `IGNOREPADTOPADCLEARANCEINFOOTPRINT=FALSE`, `OBJECTCLEARANCES` (empty); Width `MAXLIMIT`, `MINLIMIT`, `PREFEREDWIDTH`; RoutingVias `HOLEWIDTH`, `WIDTH`, `VIASTYLE=Through Hole`, `MINHOLEWIDTH`, `MINWIDTH`, `MAXHOLEWIDTH`, `MAXWIDTH`; lengths as mil text.
- Per kind, one rule `<Kind>_<class>` with `SCOPE1EXPRESSION=InNetClass('<class>')` MUST be written for each class that holds the kind's value (clearance; track width; via diameter and drill), in class-name order with `PRIORITY` from 1, then one rule named `Clearance`, `Width` or `RoutingVias` with `SCOPE1EXPRESSION=All` and the next priority. The rules of one kind are written together, in the order Clearance, Width, RoutingVias.
- The `All` rules MUST use `pcbdoc.DEFAULT_CLEARANCE` (0.2 mm), `DEFAULT_TRACK_WIDTH` (0.25 mm), `DEFAULT_VIA_DIAMETER` (0.6 mm) and `DEFAULT_VIA_DRILL` (0.3 mm), Fenolite's choices.
- A width rule's `MINLIMIT` and `MAXLIMIT` MUST be the smallest and the largest of the preferred width and the widths of the written tracks and arcs in its scope; a via rule's minimum and maximum likewise over the written vias. So the written copper never breaks its own width or via rule.

#### Scenario: Rules of the blink sample
- **WHEN** `Rules6` of the blink sample is read
- **THEN** it holds five rules in this order: `Clearance_PWR` (kind 0, `GAP=7.874mil`, priority 1), `Clearance` (priority 2, `GAP=7.874mil`), `Width_PWR` (kind 2, `PREFEREDWIDTH=19.685mil`, priority 1), `Width` (priority 2, `PREFEREDWIDTH=9.8425mil`) and `RoutingVias` (kind 11, priority 1, `WIDTH=23.622mil`, `HOLEWIDTH=11.811mil`)

#### Scenario: Limits follow the copper
- **GIVEN** a class `PWR` with track width 0.5 mm and tracks of 0.4 mm and 1.0 mm on its nets
- **WHEN** `Width_PWR` is read
- **THEN** `MINLIMIT` is `15.748mil`, `PREFEREDWIDTH` is `19.685mil` and `MAXLIMIT` is `39.3701mil`

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

