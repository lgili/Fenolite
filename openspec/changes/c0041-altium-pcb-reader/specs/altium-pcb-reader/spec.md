## ADDED Requirements

### Requirement: PCB reader package
Fenolite SHALL provide the product reader of Altium PCB files as the modules `pcbprops`, `pcbprims`, `pcbstack`, `pcb` and `pcblib` of the package `fenolite.backends.altium.read` (the package of change c0039).
- `read.pcb.read_pcbdoc(source, *, file="", strict=False)` MUST return a `PcbDocument`, and `read.pcblib.read_pcblib(source, *, file="", strict=False)` a `PcbLibrary`. `source` is the file's bytes or a `read.cfb.CompoundFile` (change c0039). Bytes MUST be opened with `read.cfb.open_compound(source, file=file)` after `read.cfb.is_compound(source)` is true; a `CompoundError` MUST be passed on unchanged, and `CompoundFile.notes` MUST be the first issues of the result.
- `read.pcb.detect_pcb(source)` MUST return `"pcblib"` for a compound file whose root holds `Library/Data`, `"pcbdoc"` for one whose root holds `Board6/Data`, and `None` otherwise.
- The five modules MUST import only the standard library, `fenolite.core` and `fenolite.backends.altium.read`. They MUST NOT import the writer modules `pcbrecords`, `pcblib`, `pcbdoc`, `libboard` and `docboard` of `fenolite.backends.altium`, nor `fenolite.model`.
- The container MUST be reached only through `read.cfb`. The reader MUST NOT write a file and MUST NOT run a subprocess.
- Every record type MUST be a frozen dataclass. Lengths are integers in the file's unit of 1/10 000 mil; angles are the stored doubles in degrees. `pcbprims.to_nm_exact(units)` MUST return the exact `Fraction` `units · 127 / 50`, and `pcbprims.to_nm(units)` MUST return `fenolite.core.units.u_to_nm(units)`: that value rounded half to even, the project rule of `docs/formats/units.md`. The reader has no rounding rule of its own.

#### Scenario: A document and a library are told apart
- **GIVEN** `tests/data/altium/blink/blink.PcbDoc` and `blink.PcbLib`
- **WHEN** `detect_pcb` reads each file's bytes
- **THEN** it returns `"pcbdoc"` and `"pcblib"`, and `None` for `blink.SchLib`

#### Scenario: The reader does not import the writers
- **GIVEN** the five modules
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_pcb_imports.py` walks their import statements
- **THEN** no module imports a writer module or `fenolite.model`, and `tests/unit/test_import_graph.py` passes with no `ALLOWED` change

#### Scenario: Unit conversion
- **GIVEN** 354331 units
- **WHEN** `to_nm_exact` and `to_nm` convert it
- **THEN** they return `Fraction(45000037, 50)` and `900001`

#### Scenario: Ties round to even
- **WHEN** `to_nm` converts 25, 75, 125 and -25 units
- **THEN** it returns 64, 190, 318 and -64, the values of `fenolite.core.units.u_to_nm`

### Requirement: Lossless PCB records
The reader SHALL lose no byte and no key of a file it reads.
- Every record MUST carry `raw`, the bytes of the record as stored: for a primitive the type byte and every subrecord with its length word; for a property record the length word and the text with its NUL; for a rule its two leading bytes too.
- Every typed storage MUST satisfy the identity: the `raw` of its records joined in order, followed by the storage's `trailing` bytes, equals the `Data` stream. `PcbDocument.rebuild(storage)` and `LibFootprint.rebuild()` MUST return that concatenation.
- A typed field MUST be a view of `raw`. A primitive MUST expose `tail`: the bytes of each subrecord after the last offset the reader knows.
- A property record MUST keep its fields as an ordered tuple of `(key, value)` with duplicates and unknown keys.
- Every stream of the compound file that no typed storage owns MUST be returned unchanged in `storages` (a mapping from the storage name to its streams), including `Header` streams and root streams.

#### Scenario: A long track keeps its tail
- **GIVEN** an authored track record whose subrecord has 49 bytes, the last 13 being `01 02 … 0D`
- **WHEN** `decode_primitives` reads it
- **THEN** the track's ends and width are those of the first 33 bytes, `tail` is the 13 bytes after offset 36, and `raw` equals the input

#### Scenario: A stream is rebuilt
- **GIVEN** `tests/data/altium/blink/blink.PcbDoc`
- **WHEN** `read_pcbdoc` reads it and `rebuild` is called for each typed storage
- **THEN** each result equals the `Data` stream of that storage, and every other stream of the file is found unchanged in `storages`

#### Scenario: An unknown key and a duplicate survive
- **GIVEN** a `Nets6` record `|NAME=GND|XYZZY=1|XYZZY=2`
- **WHEN** it is read
- **THEN** its fields are `(("NAME", "GND"), ("XYZZY", "1"), ("XYZZY", "2"))` and the net's name is `GND`

### Requirement: Property records
`read.pcbprops` SHALL read the property text of PCB files as `docs/formats/altium/pcb-records.md` states it.
- A property block is a 32-bit little-endian word whose low 24 bits are the payload length, then the payload. The payload's last byte, a NUL, MUST be dropped from the text and kept in `raw`. A payload without the NUL MUST be read whole.
- Fields are separated by `|`. A CR or LF directly before a `|` or at the end belongs to the separator. A piece without `=` is kept as a field with an empty value when it is not empty.
- Text MUST be decoded as ISO-8859-1, so that every byte maps to one character. A key that starts with `%UTF8%` holds UTF-8: `PropertyRecord.get(key)` MUST prefer the value of `%UTF8%<key>` when it is present and decodes.
- `get(key)` and `get_all(key)` MUST compare keys without case and return the first value or every value.
- `parse_mil(text)` MUST return the length in units as a `Fraction` for decimal text ending in `mil`, and `None` for any other text. `parse_bool` accepts `TRUE`, `FALSE`, `T` and `F`. `parse_angle` reads Altium's scientific form with its leading space.
- `parse_blocks(data, *, lead=0, where)` MUST return the records, the trailing bytes and the issues; `lead` is the number of bytes before each length word (2 for `Rules6`).
- A length word that runs past the end of the stream MUST end the parse: the remaining bytes become `trailing` and one `altium.pcb-read.truncated` issue is returned.

#### Scenario: A board record of many lines
- **GIVEN** a block whose text is `|A=1\r|RECORD=Board|B=2` followed by a NUL
- **WHEN** it is parsed
- **THEN** the fields are `A=1`, `RECORD=Board`, `B=2`, and `raw` holds the CR and the NUL

#### Scenario: UTF-8 key preferred
- **GIVEN** a record with `NAME=R?sistance` and `%UTF8%NAME` holding the UTF-8 bytes of `Résistance`
- **WHEN** `get("name")` is called
- **THEN** it returns `Résistance`

#### Scenario: Length in mils
- **GIVEN** the texts `0.5mil`, `-0.0001mil` and `0.5mm`
- **WHEN** `parse_mil` reads them
- **THEN** it returns `Fraction(5000)`, `Fraction(-1)` and `None`

#### Scenario: Truncated block
- **GIVEN** a stream whose second length word says 100 bytes while 20 remain
- **WHEN** `parse_blocks` reads it
- **THEN** one record is returned, `trailing` holds the 24 remaining bytes, and the issue's `where` names the byte offset

### Requirement: Record length tolerance
`read.pcbprims.decode_primitives` SHALL read every record length that Altium saves and that Fenolite writes, and MUST NOT depend on a length being one of a known list.
- A primitive is a type byte and a fixed number of subrecords: 1 for an arc (type 1), via (3), track (4), fill (6), region (11) and component body (12); 6 for a pad (2); 2 for a text (5).
- `MINIMUMS` MUST state the shortest subrecord the reader types: track 33, arc 45, via 31, fill 37, text first subrecord 40, pad fifth subrecord 110, pad sixth subrecord 0 or at least 596, region 26.
- A field whose offset lies past the end of a subrecord MUST be `None`. Each such field is named in the field table with the length from which it exists.
- A subrecord shorter than its minimum MUST give a `RawPrimitive` (type, subrecords, `raw`) and one `altium.pcb-read.short-record` warning; the parse continues with the next record.
- A component body MUST always be a `RawPrimitive`, without an issue. The streams of `ComponentBodies6` and `ShapeBasedComponentBodies6` are not typed storages, so they stay in `PcbDocument.storages` as bytes. This is the hand-over to change c0043: its `read.bodies.read_bodies` decodes those `Data` streams and the `raw` of a library footprint's type 12 primitives, and this reader types no body field.
- A type byte outside the eight types, or a subrecord length that runs past the end, MUST end the parse of that stream: the remaining bytes become `trailing`, with one `altium.pcb-read.unknown-type` or `altium.pcb-read.truncated` error.
- The lengths observed in the corpus MUST be listed in `docs/formats/altium/pcb-read.md`: track 45 and 49; arc 56 and 60; via 299, 321 and 351; fill 46 and 50; text 232 and 252; pad fifth subrecord 170, 171, 185, 186 and 194; pad sixth subrecord 0 and 651.

#### Scenario: Every observed length is read
- **GIVEN** authored records with a track of 36, 45 and 49 bytes, an arc of 47, 56 and 60, a via of 31, 209, 299, 321 and 351, a fill of 37, 46 and 50, a text of 40, 137, 232 and 252, and a pad whose fifth subrecord has 110, 114, 170, 171, 185, 186 and 194 bytes
- **WHEN** `decode_primitives` reads them
- **THEN** every record is typed, the fields of the shortest form are equal in every length of a kind, and no issue is returned

#### Scenario: A longer record than any seen
- **GIVEN** a track of 80 bytes
- **WHEN** it is read
- **THEN** it is a `TrackRecord` with a `tail` of 44 bytes and no issue

#### Scenario: A short record is kept
- **GIVEN** a stream with a track of 20 bytes followed by a track of 49 bytes
- **WHEN** it is read
- **THEN** the result is a `RawPrimitive` and a `TrackRecord`, with one `altium.pcb-read.short-record` warning that names the stream and the record index

#### Scenario: An unknown type stops the stream
- **GIVEN** a stream with one track and then the type byte 9
- **WHEN** it is read
- **THEN** one track is returned, `trailing` starts at the byte 9, and the issue is `altium.pcb-read.unknown-type`

### Requirement: Board record and layer stack
`read.pcbstack.BoardRecord` SHALL give the board record of a document (`Board6/Data`) or a library (`Library/Data`) as one property record with typed views.
- `kind`, `version`, `filename`, `origin` (two lengths, `None` in a library) and `display_unit`.
- `outline`: the vertices `KIND<k>`, `VX<k>`, `VY<k>`, `CX<k>`, `CY<k>`, `SA<k>`, `EA<k>`, `R<k>` from k = 0 until the first missing `VX<k>`; a missing arc key reads as zero.
- `layers`: for each numbered layer i from 1 until the first missing `LAYER<i>NAME`, the name, `PREV`, `NEXT`, `MECHENABLED`, `COPTHICK`, `DIELTYPE`, `DIELCONST`, `DIELHEIGHT` and `DIELMATERIAL`, with the texts kept.
- `copper_chain`: the layer ids from 1 following `NEXT` until 0. A link to a layer without a name, or a loop, MUST end the chain with one `altium.pcb-read.bad-stack` error.
- `stack`: the physical list `V9_STACK_LAYER<i>_…` when present, each entry with its name, long layer id, copper thickness or dielectric keys, and every other key of the entry kept; an empty tuple in a record without those keys.
- `plane_nets`: the mapping from the plane number n to `PLANE<n>NETNAME` for the values other than `(No Net)`.
- `layer_pairs`: the drill pairs `LAYERPAIR<i>LOW` and `HIGH`.
- `LAYER_NAMES` MUST map the layer ids 1 to 74 to their names, and `long_layer_id(value)` MUST split a long id into its kind (signal, plane, mechanical, other, dielectric) and number, as `docs/formats/altium/pcb-library.md` states them.
- The reader MUST NOT merge the numbered layers and the physical list; both are returned.

#### Scenario: Two-layer stack of Fenolite's document
- **GIVEN** `tests/data/altium/blink/blink.PcbDoc`
- **WHEN** the board record is read
- **THEN** `kind` is `Protel_Advanced_PCB`, `version` is `5.01`, `copper_chain` is `(1, 32)`, `stack` has nine entries from `Top Paste` to `Bottom Paste`, `plane_nets` is empty, `layer_pairs` is `(("TOP", "BOTTOM"),)` and `outline` has five vertices, the first equal to the last

#### Scenario: Four layers with a plane
- **GIVEN** an authored record whose numbered layers link 1 → 39 → 3 → 32 with `PLANE1NETNAME=GND`
- **WHEN** it is read
- **THEN** `copper_chain` is `(1, 39, 3, 32)` and `plane_nets` is `{1: "GND"}`

#### Scenario: Broken chain
- **GIVEN** a record whose `LAYER1NEXT` is 2 and whose `LAYER2NEXT` is 1
- **WHEN** it is read
- **THEN** `copper_chain` is `(1, 2)` and one `altium.pcb-read.bad-stack` error is returned

#### Scenario: Library record
- **GIVEN** `tests/data/altium/blink/blink.PcbLib`
- **WHEN** `read_pcblib` reads it
- **THEN** its board record has `kind` `Protel_Advanced_PCB_Library`, `version` `3.00`, `origin` `None` and the same nine stack entries

### Requirement: Nets, components and classes
`read.pcb` SHALL read `Nets6`, `Components6` and `Classes6` as property records with typed views.
- `NetRecord`: `name` and `unique_id`. A net's index is its position in `Nets6`.
- `ComponentRecord`: `layer` (the `LAYER` text), `x`, `y` (units), `rotation` (degrees), `pattern`, `locked`, `name_on`, `comment_on`, `source_designator`, `source_unique_id`, `source_hierarchical_path`, `source_footprint_library`, `source_component_library`, `source_lib_reference`, `unique_id`. A missing key gives `None` (texts) or the documented default.
- `ClassRecord`: `name`, `kind` (the number), `superclass`, and `members`, the values of `M0`, `M1`, … until the first missing key.
- `PcbDocument.net_name(index)` MUST return the net's name, and `None` for `0xFFFF` or an index past the count.
- `PcbDocument.primitives_of(index)` MUST return the pads, tracks, arcs, texts, fills, regions and vias whose component index is `index`, each kind in stream order.

#### Scenario: Components of Fenolite's document
- **GIVEN** `tests/data/altium/blink/blink.PcbDoc`
- **WHEN** it is read
- **THEN** it has three components whose `source_designator` values are `D1`, `R1` and `U1` in some order, `D1` has `layer` `BOTTOM`, and each component's pads carry net indexes that `net_name` resolves

#### Scenario: Class members
- **GIVEN** a `Classes6` record with `NAME=PWR`, `KIND=0`, `SUPERCLASS=FALSE`, `M0=GND`, `M1=VIN`
- **WHEN** it is read
- **THEN** the class has `kind` 0, `superclass` `False` and `members` `("GND", "VIN")`

### Requirement: Pad records
`read.pcbprims.PadRecord` SHALL give a pad in every form of its six subrecords.
- `name` from the first subrecord (a length byte and the characters); a first subrecord of length 0 gives an empty name.
- From the fifth subrecord: the common prefix (`layer`, `flags`, `net`, `polygon`, `component`), `x`, `y`, the top, middle and bottom sizes, `hole`, the three shapes, `rotation`, `plated`, `stack_mode`, the paste and solder mask expansions and their modes, and `hole_rotation` when the subrecord is longer than 110 bytes.
- From the sixth subrecord when it has at least 596 bytes: the 29 inner sizes and shapes, `hole_shape`, `slot_length`, `slot_rotation`, the 32 offsets, and the 32 alternate shapes and corner percentages. With an empty sixth subrecord these are `None`.
- `tail` MUST hold the bytes of the fifth subrecord after offset 114 and of the sixth after offset 596. The second, third and fourth subrecords are kept in `raw` only.
- Fields of the long forms beyond these MUST be typed only when the fact page has a row for them at `CORPUS-VERIFIED` or above (see "Field evidence table").

#### Scenario: Short and long pad agree
- **GIVEN** the worked pad of `pcb-records.md` (114 and 596 bytes) and the same pad authored with a fifth subrecord of 194 bytes and a sixth of 651 bytes
- **WHEN** both are read
- **THEN** both give x −314961, sizes 354331 × 374016, hole 0, alternate shape 9 and percentage 50; the long one has tails of 80 and 55 bytes

#### Scenario: Through-hole pad without a layer block
- **GIVEN** a pad on layer 74 with hole 393701, plated 1 and an empty sixth subrecord
- **WHEN** it is read
- **THEN** `hole` is 393701, `plated` is `True` and `hole_shape` is `None`

### Requirement: Track, arc, via and fill records
`read.pcbprims` SHALL give tracks, arcs, vias and fills with the common prefix and their geometry.
- `TrackRecord`: `x1`, `y1`, `x2`, `y2`, `width`; `sub_polygon` when the subrecord reaches 35 bytes.
- `ArcRecord`: `cx`, `cy`, `radius`, `start_angle`, `end_angle`, `width`; `sub_polygon` when it reaches 47 bytes.
- `ViaRecord`: `x`, `y`, `diameter`, `hole`, `start_layer`, `end_layer`; `tented_top` and `tented_bottom` from the flag bits 5 and 6.
- `FillRecord`: `x1`, `y1`, `x2`, `y2`, `rotation`.
- The prefix MUST give `locked` (bit 2 of the first flag byte clear) and the three indexes, with `0xFFFF` read as `None`. A polygon index of `0xFFFE` MUST be kept as the number.
- The reader MUST NOT derive a 32-bit layer id from the tail unless its row is at `CORPUS-VERIFIED` or above.

#### Scenario: Via of 321 bytes
- **GIVEN** the via record `pcbrecords.via_record(0, 0, 236220, 118110)` of change c0038, built in the test
- **WHEN** it is read
- **THEN** the via has diameter 236220, hole 118110, layers 1 and 32, no net and a tail of 290 bytes

#### Scenario: Rotated fill
- **GIVEN** an authored fill of 50 bytes with corners (0, 0) and (1000000, 500000) and rotation 90.0
- **WHEN** it is read
- **THEN** the corners and the rotation are those values and `tail` has 13 bytes

### Requirement: Region and polygon records
The reader SHALL give regions and polygon pours.
- `RegionRecord` (type 11, one subrecord): the common prefix, `hole_count` (16-bit at offset 14), `properties` (at offset 18 a 32-bit length and the property text, which starts without `|`; returned as a `PropertyRecord`), `outline` and `holes`.
- In `Regions6` and in a library footprint an outline vertex is two doubles in units. In `ShapeBasedRegions6` the outline has one more vertex than its count, and each vertex is a round flag, a position, a centre, a radius (32-bit each) and two angles (doubles): 37 bytes. Holes are, in both, a 32-bit count and that many pairs of doubles.
- `decode_primitives(..., shape_based=True)` selects the second form. Vertices MUST be returned as stored (doubles are not rounded).
- Bytes after the last hole MUST be the region's `tail`. A vertex count that runs past the subrecord MUST give a `RawPrimitive` and an `altium.pcb-read.short-record` warning.
- `PolygonRecord` (a property record of `Polygons6`): `layer` (text), `net` (index or `None`), `polygon_type`, `hatch_style`, `pour_index`, `name`, and `vertices` with the eight keys per vertex of the board outline. `name` MUST decode a value made only of decimal numbers joined by commas as character codes; any other value is the name itself.
- A polygon's index is its position in `Polygons6`; `PcbDocument.regions_of(index)` MUST return the regions whose polygon index is `index`.

#### Scenario: Region with a hole
- **GIVEN** an authored region with four outline vertices, one hole of three vertices and the properties `V7_LAYER=TOP|KIND=0`
- **WHEN** it is read in both forms
- **THEN** each has four outline vertices (five stored in the shape-based form), one hole of three, `properties.get("KIND")` equal to `0`, an empty tail and `raw` equal to the input

#### Scenario: Polygon name in character codes
- **GIVEN** a polygon record with `NAME=71,78,68`, `LAYER=MID1`, `POURINDEX=0` and `NET=2`
- **WHEN** it is read
- **THEN** `name` is `GND`, `layer` is `MID1`, `pour_index` is 0 and `net` is 2

### Requirement: Text records and wide strings
The reader SHALL give texts with the string that Altium shows.
- `TextRecord`: the common prefix, `x`, `y`, `height`, `stroke_font`, `rotation`, `mirrored`, `stroke_width`; from 123 bytes on `is_comment`, `is_designator`, `font_type`, `bold`, `italic`, `font_name` (64 bytes of UTF-16LE up to the first NUL), `inverted`, `margin` and `wide_index`; `short_text`, the 8-bit string of the second subrecord.
- In a document, `WideStrings6/Data` is a table of entries (a 32-bit index, a 32-bit byte length that counts a 2-byte NUL, UTF-16LE text). `TextRecord.text` MUST be the entry named by `wide_index` when it exists, else `short_text`.
- In a library footprint, `WideStrings` is one property block of `ENCODEDTEXT<i>` values, each a list of decimal character codes joined by commas; `text` MUST be the decoded entry `i` equal to `wide_index` when it exists, else `short_text`.
- A wide-string table that does not parse MUST give one `altium.pcb-read.bad-frame` warning and texts with `short_text`.

#### Scenario: Designator text
- **GIVEN** `tests/data/altium/blink/blink.PcbDoc`
- **WHEN** it is read
- **THEN** each component has one text with `is_designator` set whose `text` equals the component's `source_designator`

#### Scenario: Long text
- **GIVEN** an authored text of 252 bytes with the font name `Arial`, bold set, and a wide string `Ω1` at its index
- **WHEN** it is read
- **THEN** `font_name` is `Arial`, `bold` is `True`, `text` is `Ω1` and `tail` holds the bytes after offset 119

### Requirement: Rules kept opaque
The reader SHALL keep design rules without interpreting them.
- A record of `Rules6` is a 16-bit kind number and one property block. `RuleRecord` MUST give `kind_number`, `rule_kind` (the `RULEKIND` text), `name`, `enabled`, `priority`, `scope1` and `scope2` (the texts of `SCOPE1EXPRESSION` and `SCOPE2EXPRESSION`, unparsed), `comment`, `unique_id` and `fields`. `fields` MUST be every `(key, value)` pair of the record in order, the typed keys included, so that `fields` is the input record of c0042's `read.rules.map_rules`.
- No other key MUST be typed, and no scope expression MUST be parsed.
- `PcbDocument.rules` MUST keep the stream order.

#### Scenario: A width rule for a class
- **GIVEN** a rule with the kind number 2 and `RULEKIND=Width|NAME=Width_1A|ENABLED=TRUE|PRIORITY=1|SCOPE1EXPRESSION=InNetClass('PWR')|SCOPE2EXPRESSION=All|MINLIMIT=10mil|FUTUREKEY=7`
- **WHEN** it is read
- **THEN** `kind_number` is 2, `rule_kind` is `Width`, `priority` is 1, `scope1` is `InNetClass('PWR')`, and `fields` holds all eight pairs in order, from `("RULEKIND", "Width")` to `("FUTUREKEY", "7")`

### Requirement: PCB library reading
`read.pcblib.read_pcblib` SHALL read a PCB library as `docs/formats/altium/pcb-library.md` states it.
- `PcbLibrary`: `header_text`, `version` and `unique_id` from `FileHeader` (`None` for parts a shorter header lacks), `board` (the record of `Library/Data`), `names` (the footprint names of `Library/Data`), `footprints`, `storages`, `issues` and `evidence`.
- A footprint's storage MUST be found, in this order, by the `SectionKeys` stream, by a root storage whose `Parameters` holds the name as `PATTERN`, and by a root storage whose name equals the name without case.
- `LibFootprint`: `name`, `storage`, `parameters` (the property record), `description`, `height`, `primitives` (every primitive of `Data` in order, after the name string), `pads`, `unique_ids` (the mapping from a primitive index to its id from `UniqueIDPrimitiveInformation`), `wide_strings`, and `streams` (every stream of the storage).
- A root storage with a `Data` and a `Parameters` stream that `names` does not list MUST also be returned as a footprint, with one `altium.pcb-read.unlisted-footprint` info. A listed name without a storage MUST give one `altium.pcb-read.missing-stream` error and no footprint.
- A `Header` count that differs from the number of primitives read MUST give one `altium.pcb-read.count-mismatch` warning.
- `PcbLibrary.footprint(name)` MUST return the footprint or `None`.

#### Scenario: Fenolite's library
- **GIVEN** `tests/data/altium/blink/blink.PcbLib`
- **WHEN** it is read
- **THEN** `header_text` is `PCB 6.0 Binary Library File`, `version` is 5.01, three footprints are returned in the order of `names`, every pad's primitive index is a key of `unique_ids`, and `issues` is empty

#### Scenario: Footprint under a section key
- **GIVEN** an authored library whose footprint `A/VERY-LONG-NAME-OF-MORE-THAN-31-CHARACTERS` is stored under a shortened storage name listed in `SectionKeys`
- **WHEN** it is read
- **THEN** the footprint has the full name and `storage` is the shortened one

#### Scenario: Listed footprint without a storage
- **GIVEN** a library whose `Library/Data` lists `X` and no storage holds it
- **WHEN** it is read
- **THEN** no footprint `X` is returned and the issue is `altium.pcb-read.missing-stream` with `where` `Library/Data`

### Requirement: PCB document reading
`read.pcb.read_pcbdoc` SHALL read a binary PCB document as `docs/formats/altium/pcb-document.md` states it.
- `PcbDocument`: `header_text` and `unique_id` (from `FileHeaderSix`, else `FileHeader`), `board`, `nets`, `components`, `classes`, `rules`, `polygons`, `pads`, `vias`, `tracks`, `arcs`, `texts`, `fills`, `regions`, `shape_regions`, `wide_strings`, `pad_unique_ids`, `storages`, `issues` and `evidence`.
- The typed storages are `Board6`, `Nets6`, `Components6`, `Classes6`, `Rules6`, `Polygons6`, `Pads6`, `Vias6`, `Tracks6`, `Arcs6`, `Texts6`, `Fills6`, `Regions6`, `ShapeBasedRegions6`, `WideStrings6` and `UniqueIDPrimitiveInformation`. Storage and stream names MUST be matched without case. A typed storage that is absent reads as empty, without an issue, except `Board6`.
- A source that is not a compound file, or that has no `Board6/Data`, MUST raise `PcbReadError` in both modes; the message MUST say that only the binary form is read.
- A `Header` count that differs from the records read MUST give one `altium.pcb-read.count-mismatch` warning per storage.
- A net, component or polygon index that names no record MUST give one `altium.pcb-read.bad-index` warning per storage and kind, with the count of such records; the polygon index `0xFFFE` is not counted.
- A stream type that differs from the storage (a pad in `Tracks6`) MUST give one `altium.pcb-read.wrong-type` warning; the record is returned in the storage's `others`.
- `evidence` MUST be `Evidence(level=CORPUS-VERIFIED, hypotheses=…)` once the corpus tests of this capability have passed and are recorded, and `INFERRED` before.

#### Scenario: Fenolite's document
- **GIVEN** `tests/data/altium/blink/blink.PcbDoc`
- **WHEN** it is read
- **THEN** it has the nets, three components, their pads, tracks, arcs and texts that `tests/_altium_pcb_read.read_pcbdoc` returns for the same bytes, no fill and no region, and no issue

#### Scenario: Not a binary document
- **GIVEN** the bytes of a text file
- **WHEN** `read_pcbdoc` reads them
- **THEN** it raises `PcbReadError` whose message says that only the binary form is read

#### Scenario: Header count differs
- **GIVEN** an authored document whose `Tracks6/Header` says 5 while `Data` holds 4 tracks
- **WHEN** it is read
- **THEN** four tracks are returned with one `altium.pcb-read.count-mismatch` warning whose `where` is `Tracks6/Header`

#### Scenario: Index past the nets
- **GIVEN** an authored document with three nets and two tracks whose net index is 9
- **WHEN** it is read
- **THEN** both tracks are returned, `net_name(9)` is `None`, and one `altium.pcb-read.bad-index` warning says 2 records in `Tracks6`

### Requirement: Read issues and strict mode
The reader SHALL report problems as located issues and fail only when asked.
- `PCB_READ_ISSUE_CODES` MUST map each code to its severity: `altium.pcb-read.truncated` error, `altium.pcb-read.unknown-type` error, `altium.pcb-read.missing-stream` error, `altium.pcb-read.bad-stack` error, `altium.pcb-read.short-record` warning, `altium.pcb-read.count-mismatch` warning, `altium.pcb-read.bad-index` warning, `altium.pcb-read.wrong-type` warning, `altium.pcb-read.bad-frame` warning, `altium.pcb-read.bad-value` warning (a typed key whose text does not parse; the view gives `None`), `altium.pcb-read.unlisted-footprint` info.
- Every issue MUST have `where` as `<storage>/<stream>` followed, for a record, by `#<index>` and, for a byte position, by `@<offset>`.
- An issue's message MUST NOT contain a value of the file other than a storage name, a key name, a number or a length.
- With `strict=True` the first issue of severity error MUST raise `PcbReadError`, a subclass of `fenolite.core.errors.FormatError`, with `file`, `locator` and `offset` set.
- With `strict=False` the reader MUST return what it read, with every issue in `issues`.
- An error of c0039's container reader is not caught.

#### Scenario: Lenient and strict
- **GIVEN** an authored document whose `Pads6/Data` ends in the middle of a subrecord
- **WHEN** it is read with the default and with `strict=True`
- **THEN** the default returns the pads before the cut with one `altium.pcb-read.truncated` error, and the strict read raises `PcbReadError` with `locator` `Pads6/Data` and the byte offset

#### Scenario: Codes are closed
- **GIVEN** the reader's modules
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_pcb_issues.py` collects every code they emit
- **THEN** the set equals the keys of `PCB_READ_ISSUE_CODES`

### Requirement: Field evidence table
Every typed field SHALL have an evidence level that equals its row of the fact page.
- `docs/formats/altium/pcb-read.md` MUST hold the table "Fields" with the columns record, field, subrecord, offset, from length, source, label and hypothesis, one row per typed field of a binary record, and the table "Keys" with one row per typed key of a property record.
- `read.pcbprims.FIELD_LEVELS` MUST map `"<record>.<field>"` to the level of its row, and `field_level(record, field)` MUST return it.
- A field MUST NOT be typed when its only source is a page that attributes the fact to the vendor's software, and S-0173 MUST NOT be the only source of a row.
- A row whose label is `ORACLE-VERIFIED(kicad-cli)` MUST name the oracle test that compares the field.

#### Scenario: Table and code agree
- **GIVEN** the fact page and the module
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_pcb_field_levels.py` runs
- **THEN** every typed field of every binary record has exactly one row, and each level of `FIELD_LEVELS` equals the label of its row

#### Scenario: A field without a row
- **GIVEN** a record class that gains a field with no row
- **WHEN** the same test runs
- **THEN** it fails naming the record and the field

### Requirement: Altium PCB corpus rows
`tests/corpus/manifest.toml` SHALL hold the public Altium-saved PCB files this capability is measured on. Every row follows `corpus-policy`, "Second-backend corpus rows" (change c0039): its id pattern, the pinned commit, the licence rule, the uses `altium` and `origin:third-party`, and its `notes` rule.
- Seven rows with the use `altium-pcbdoc` (the documents of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199 and S-0200) and four with the use `altium-pcblib` (the two libraries of S-0170 and the two of S-0171), each at the commit and with the SHA-256 that `docs/evidence/sources.md` records.
- Every row MUST carry `origin:third-party`, `embeddable = false`, the SPDX licence of its repository, and MUST NOT carry `rt0` or `oracle`. The six rows that change c0039 lists (`altium-third-party-pcbdoc-01` to `-04` and `altium-third-party-pcblib-01` and `-02`) MUST be reused by adding the use to them; this change adds `altium-third-party-pcbdoc-05` to `-07` (S-0174, S-0175, S-0200) and `altium-third-party-pcblib-03` and `-04` (S-0171), without `cfb`.
- Row ids MUST match `^altium-third-party-(pcbdoc|pcblib)-\d{2}$`. `notes` MUST describe a row as c0039 rules: by its source id, kind, size in bytes and save year only.
- No file of these rows MUST be committed, and no value read from them (a file path, a net name, a component name) MUST appear in the repository or in test output; counts and lengths may.
- Tests on these rows MUST be marked `needs_corpus`.

#### Scenario: Rows are valid
- **GIVEN** the manifest
- **WHEN** `uv run pytest tests/corpus/test_manifest.py tests/corpus/test_altium_pcb_rows.py` runs
- **THEN** the schema test passes and the second test counts seven `altium-pcbdoc` rows and four `altium-pcblib` rows, each with `origin:third-party` and without `rt0`

#### Scenario: Corpus absent
- **GIVEN** an empty corpus cache
- **WHEN** `uv run pytest tests/corpus/test_altium_pcb_census.py` runs
- **THEN** every test is skipped with the message `run: uv run python tools/corpus_fetch.py`

### Requirement: Corpus census and identity
`tests/corpus/test_altium_pcb_census.py` SHALL read every corpus row with the product reader and check what holds for all of them (`H-A-RD-PCB-FRAME`, `H-A-RD-PCB-IDENTITY`, `H-A-RD-PCB-LENGTHS`, `H-A-RD-PCB-REGION`, `H-A-RD-PCB-TEXT`, `H-A-RD-PCB-RULE`, `H-A-RD-PCB-POLYNAME`, `H-A-RD-PCB-CODEC`).
- Every row MUST be read with no issue of severity error and no `short-record` warning.
- Every typed storage MUST rebuild to its stream, with empty `trailing`.
- Every subrecord length MUST be in the list of "Record length tolerance"; a new length fails the test with the kind and the length, so that the list is extended on purpose.
- Every region MUST have an empty tail, and `Regions6` and `ShapeBasedRegions6` MUST hold the same number of records.
- Every text with `is_designator` MUST have a `text` equal to its component's `source_designator`.
- Every rule's kind number MUST map to one `RULEKIND` text over the whole corpus.
- Every non-empty polygon `name` MUST decode to printable text, and the numbers of non-ASCII bytes and of `%UTF8%` keys MUST be counted per row.
- The test MUST write nothing but counts and lengths to its output. `docs/evidence/altium-pcb-read.md` MUST record, per row id, the record counts per storage and the lengths seen.

#### Scenario: Census passes
- **GIVEN** the eleven rows fetched
- **WHEN** `uv run pytest tests/corpus/test_altium_pcb_census.py -m needs_corpus` runs
- **THEN** eleven files are read and every check passes

#### Scenario: A new length
- **GIVEN** a document with a track of 53 bytes
- **WHEN** the length check runs on it
- **THEN** the product reader types the track, and the census check fails naming `track` and `53`

### Requirement: PCB document import oracle
`tests/kicad/altium/test_pcbdoc_read_oracle.py` SHALL compare the product reader with `kicad-cli pcb import --format altium` on each `altium-pcbdoc` row (S-0020, S-0161, S-0166; `H-A-RD-PCB-KICAD-DOC`, `H-A-UNIT`). The test is marked `needs_kicad`, `needs_corpus` and `kicad_min_major(10)`.
- `kicad-cli` MUST exit 0. Its board is read with `fenolite.backends.kicad.pcb.read_board`.
- Positions are compared after the one translation that maps the reader's first pad onto KiCad's, with Y negated; the tolerance is 2 nm per coordinate.
- The comparison MUST cover: the set of net names; the number of footprints and the multiset of their references against `source_designator`; per footprint the pad count, pad names, pad positions, pad nets and hole sizes; the vias with position, diameter, hole and net; the tracks on copper layers that carry a net, with ends, width, layer position in the copper chain and net; the number of copper layers against the length of `copper_chain`; and the number of zones against the polygons KiCad converts.
- A reader record that KiCad does not return MUST belong to a documented exclusion of `docs/formats/altium/pcb-read.md` ("What KiCad does not import"), each with its count per row in the evidence page. An item of KiCad's board without a reader record fails the test.
- A row on which `kicad-cli` fails MUST be listed in the evidence page with its exit code, and is excluded by its row id in the test.
- The largest position difference found MUST be recorded in the `H-A-UNIT` row.

#### Scenario: A public board agrees
- **GIVEN** the seven `altium-pcbdoc` rows fetched and `kicad-cli` 10.0
- **WHEN** `uv run pytest tests/kicad/altium/test_pcbdoc_read_oracle.py` runs
- **THEN** on every row that KiCad imports, the nets, footprints, pads, vias, copper tracks and copper layer count agree within the tolerance, apart from the documented exclusions

#### Scenario: KiCad 9
- **GIVEN** `kicad-cli` 9.0
- **WHEN** the test runs
- **THEN** it is skipped, because `pcb import` exists from 10.0

### Requirement: PCB library conversion oracle
`tests/kicad/altium/test_pcblib_read_oracle.py` SHALL compare the product reader with `kicad-cli fp upgrade` on each `altium-pcblib` row (`H-A-RD-PCB-KICAD-LIB`). The test is marked `needs_kicad` and `needs_corpus`.
- `kicad-cli fp upgrade <row>.PcbLib -o <dir>.pretty` MUST exit 0, and each `.kicad_mod` is read with Fenolite's footprint reader.
- The comparison MUST cover: the set of footprint names; per footprint the pad count, pad names, positions (Y negated, 2 nm), sizes on the top layer, hole sizes and plating; and the number of lines and arcs on the overlay layers.

#### Scenario: Public libraries agree
- **GIVEN** the four `altium-pcblib` rows fetched and `kicad-cli`
- **WHEN** `uv run pytest tests/kicad/altium/test_pcblib_read_oracle.py` runs
- **THEN** every footprint of every row agrees with the converted footprint of the same name

### Requirement: Own files read
The product reader SHALL read every PCB file Fenolite writes, and agree with the independent test reader.
- For each committed `.PcbLib` and `.PcbDoc` under `tests/data/altium/`, the product reader MUST return no issue, and the values it shares with `tests/_altium_pcb_read.py` (pads, tracks, arcs, texts, nets, components, footprint names, and vias, polygons, classes and rules where the test reader returns them) MUST be equal.
- Every typed storage MUST rebuild to its stream.
- The test reader MUST stay independent: it does not import the product reader, and the product reader does not import it.

#### Scenario: Golden files agree
- **GIVEN** the committed Altium PCB files
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_pcb_own_files.py` runs
- **THEN** both readers return equal values for every file and no issue is reported

### Requirement: PCB reader is documented
The reader SHALL be documented where its users look.
- `docs/formats/altium/pcb-read.md` MUST state, in Fenolite's own words and with a source, a label and a hypothesis per row: the record lengths observed, the fields and keys typed, the region forms, the wide-string tables, the rule framing, the storages kept as bytes, and what KiCad does not import.
- `docs/altium.md` MUST gain the section "Reading PCB files" with the two functions, the record types, the lossless rule, the issue codes and the evidence levels, and MUST say that import into the model is change c0043.
- `docs/evidence/altium-pcb-read.md` MUST hold the census and both oracle results per row id.

#### Scenario: Pages are checked
- **GIVEN** the three pages
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_docs_altium_read.py` runs
- **THEN** every row of `pcb-read.md` has a registered source, a label and a registered hypothesis, and `docs/altium.md` names `read_pcbdoc`, `read_pcblib` and every code of `PCB_READ_ISSUE_CODES`
