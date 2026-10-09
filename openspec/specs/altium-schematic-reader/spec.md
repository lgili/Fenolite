# altium-schematic-reader Specification

## Purpose
Read Altium schematic documents and schematic libraries, in the binary and the ASCII form, into typed records that keep every field: framing, text decoding, the owner tree, pins, parts and display modes, embedded files, the issue codes and the bounds for untrusted files. Mapping the records onto the design model belongs to altium-import.

## Requirements

### Requirement: Schematic reader entry points
The package `fenolite.backends.altium.read.sch` SHALL export `read_schematic(data: bytes, *, file: str = "", codepage: str = DEFAULT_CODEPAGE, issues: list[Issue] | None = None) -> SchDocument` and `detect(data: bytes) -> str | None`, and the module `fenolite.backends.altium.read.schlib` SHALL export `read_schlib(data: bytes, *, file: str = "", codepage: str = DEFAULT_CODEPAGE, issues: list[Issue] | None = None) -> SchLibrary`.
- Both functions MUST take the file's bytes, MUST NOT open, create or change any file, and MUST return frozen dataclasses whose sequences are tuples.
- `detect` MUST return `"ascii"` when the bytes, after an optional UTF-8 byte-order mark, start with `|HEADER=`; for a compound file it MUST return `"binary"` or `"library"` from the header text of the first record of `FileHeader`; otherwise `None`. It MUST NOT look at a file name.
- `read_schematic` MUST read a schematic document and a schematic template alike (`.SchDoc`, `.SchDot`), in the binary and in the ASCII form. Given a library it MUST raise `FormatError` that names `read_schlib`; `read_schlib` given a schematic MUST raise `FormatError` that names `read_schematic`.
- The compound file MUST be opened only through `fenolite.backends.altium.read.cfb.open_compound` (change c0039), and the notes of the `CompoundFile` MUST be added to `issues`. No module of this capability parses a sector, a FAT or a directory entry.
- The modules MUST import only the standard library, `fenolite.core`, `fenolite.backends.altium.read` and themselves. They MUST NOT import the writer modules (`ascii`, `binary`, `schdoc`, `schlib`, `altsym`, `layout`, `project`) or anything under `tests/`.
- Two calls with equal arguments MUST return equal results and equal issue lists, whatever `PYTHONHASHSEED` is.
- `read.sch.HYPOTHESES` MUST hold every registered `H-A-RD-SCH-*` id and `read.sch.REFUTED` those among them whose row is refuted. `read.sch.EVIDENCE` MUST be an `Evidence` whose hypotheses are the ids of `HYPOTHESES` that are not in `REFUTED`, and whose level is the lowest level among the rows it names: a refuted row supports no claim (`verification-evidence`, "Declared levels agree with the register").

#### Scenario: Binary schematic by content
- **GIVEN** the bytes of `tests/data/altium/blink/blink.SchDoc` (a committed binary sample written by Fenolite) passed with `file="x.bin"`
- **WHEN** `detect` and `read_schematic` run
- **THEN** `detect` returns `"binary"`, and the result is a `SchDocument` with `form == "binary"` whose record 0 is a `Sheet`

#### Scenario: Library given to the schematic reader
- **GIVEN** the bytes of a schematic library
- **WHEN** `read_schematic(data, file="a.SchLib")` runs
- **THEN** it raises `FormatError` whose `file` is `a.SchLib` and whose message names `read_schlib`

#### Scenario: Neither form
- **GIVEN** the bytes `b"hello"`
- **WHEN** `detect` and `read_schematic` run
- **THEN** `detect` returns `None` and `read_schematic` raises `FormatError` with `offset` 0

#### Scenario: Reader does not import the writer
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_sch_imports.py` walks the imports of `fenolite.backends.altium.read.sch` and `read.schlib`
- **THEN** no writer module of `fenolite.backends.altium` and no `tests` module is among them

### Requirement: Binary record framing
`read.sch.framing.deframe(stream: bytes, *, where: str, file: str = "") -> tuple[Frame, ...]` SHALL split a stream into frames: a 4-byte little-endian word whose low 24 bits are the payload length and whose top byte is the kind, then the payload.
- A `Frame` MUST hold `kind`, `payload` (the exact bytes) and `offset` (the byte offset of its length word in the stream).
- A length word or a payload cut by the end of the stream MUST raise `FormatError` with `locator` `<where>/record <n>` and `offset` the offset of the length word.
- `framing.enframe(frames) -> bytes` MUST be the inverse: `enframe(deframe(s)) == s` for every stream that `deframe` accepts.
- A frame of kind 0 is a property list. Its payload SHOULD end with one NUL. A payload of kind 0 without a final NUL MUST be kept as an `UnknownRecord` with one `altium.sch.malformed-record` warning; it MUST NOT raise.
- An empty stream MUST give no frame.

#### Scenario: Two records
- **GIVEN** a 17-byte stream: the word `06 00 00 00`, the payload `|A=1` with two NUL bytes, the word `03 00 00 01` and the payload `abc`
- **WHEN** `deframe` runs
- **THEN** it returns two frames, kind 0 with a 6-byte payload at offset 0 and kind 1 with payload `abc` at offset 10, and `enframe` gives the stream back

#### Scenario: Cut payload
- **GIVEN** a stream whose only length word announces 20 bytes and that holds 8 bytes after it
- **WHEN** `deframe(stream, where="FileHeader", file="a.SchDoc")` runs
- **THEN** it raises `FormatError` with `file` `a.SchDoc`, `locator` `FileHeader/record 0` and `offset` 0

#### Scenario: Property list without its NUL
- **GIVEN** a binary schematic whose third record has kind 0 and a payload `|RECORD=27` with no NUL
- **WHEN** `read_schematic` runs with an `issues` list
- **THEN** that record is an `UnknownRecord` whose `payload` is the 10 bytes, `issues` holds one `altium.sch.malformed-record` warning naming `FileHeader/record 2`, and every other record is read

### Requirement: Property lists keep every field
`read.sch.props.parse(payload: bytes) -> PropertyList` SHALL split the text of a record into fields at `|` and each field into key and raw value at its first `=`, and SHALL keep every field in file order.
- A `Prop` MUST hold `key` (the spelling in the file, decoded as Latin-1) and `raw` (the value's bytes, unchanged, with any surrounding spaces).
- `PropertyList.to_bytes()` MUST return the bytes that were parsed, for every input, including a text without a leading `|`, an empty field, a field without `=`, a trailing `|`, and a repeated key. Fields that are not `KEY=VALUE` MUST be kept as `Prop` items with `key` equal to the field text and `raw` equal to `None`.
- Lookup MUST fold letter case: `props.get("LOCATION.X")` finds `Location.X`. When a key occurs twice after folding, lookup MUST return the first, and `PropertyList.duplicates` MUST list the folded key.
- `PropertyList.keys()` MUST return the folded keys in file order without repeats. `PropertyList.has(key)` MUST be `True` when the key is present.
- `props.int(key, default=0)`, `props.bool(key)` and `props.text(key, default="")` MUST read a missing key as 0, `False` and `""`. A boolean is `True` only for the value `T`. An integer value MAY carry surrounding spaces and a sign.
- A modelled key whose value does not parse MUST give one `altium.sch.bad-value` warning naming the record and the key at read time; the typed accessor then returns the default, and the key joins the record's `unknown_keys`.

#### Scenario: Mixed-case and unknown keys survive
- **GIVEN** the payload `|RECORD=27|OwnerPartId=-1|FROB=x=y|LOCATIONCOUNT=2|X1=10|Y1=20|X2=30|Y2=20|`
- **WHEN** `parse` runs
- **THEN** `get("OWNERPARTID")` is `-1`, the raw value of `FROB` is `b"x=y"`, `keys()` is `("RECORD", "OWNERPARTID", "FROB", "LOCATIONCOUNT", "X1", "Y1", "X2", "Y2")`, and `to_bytes()` equals the payload, trailing `|` included

#### Scenario: Missing values
- **GIVEN** the payload `|RECORD=14|ISSOLID=T`
- **WHEN** it is parsed
- **THEN** `bool("ISSOLID")` is `True`, `bool("TRANSPARENT")` is `False`, `int("LINEWIDTH")` is `0` and `text("NAME")` is `""`

#### Scenario: Value that is not an integer
- **GIVEN** a wire record `|RECORD=27|LOCATIONCOUNT=two` with no point key
- **WHEN** `read_schematic` runs with an `issues` list
- **THEN** `issues` holds one `altium.sch.bad-value` warning naming the record and `LOCATIONCOUNT`, the wire's `points` is `()`, and `LOCATIONCOUNT` is in its `unknown_keys`

### Requirement: Text decoding
Values SHALL stay bytes, and `PropertyList.text(key)` SHALL give the text view by these rules, in order:
- when the list holds a field `%UTF8%<key>`, the text is that field's value decoded as UTF-8;
- in an ASCII file whose whole content is valid UTF-8, the text is the value decoded as UTF-8;
- otherwise the text is the value decoded in the code page given to the reader. `DEFAULT_CODEPAGE` MUST be `cp1252`. Any single-byte code page that Python's standard library names MAY be passed; another name MUST raise `ValueError` before any reading.

A byte that the chosen decoding does not define MUST become U+FFFD in the text view, with one `altium.sch.text-undecodable` warning per record; the raw bytes are unchanged. The twin and the plain value MAY differ (saved files write the byte 0x8E for U+00A6, and files saved under another system code page hold their plain values in it); the twin MUST win. Spaces around a value MUST be trimmed in the text view only. The `%UTF8%` field MUST stay a field of the list, MUST count as modelled when its plain key is modelled, and MUST NOT be returned by `keys()` as a separate unknown key.

#### Scenario: UTF-8 twin wins
- **GIVEN** a record with `|TEXT=` followed by the bytes `B5 46` and `|%UTF8%TEXT=` followed by the bytes `C2 B5 46`
- **WHEN** it is read with the default code page
- **THEN** `text("TEXT")` is `µF`, and `to_bytes()` holds both fields unchanged

#### Scenario: Code page fallback
- **GIVEN** a binary schematic with `|TEXT=` followed by the bytes `63 61 66 E9` and no twin
- **WHEN** it is read with the default code page, then with `codepage="cp1251"`
- **THEN** the text is `café` in the first reading and `cafй` in the second, and both results hold the same raw bytes

#### Scenario: Undefined byte
- **GIVEN** a value holding the byte `81`, which `cp1252` does not define
- **WHEN** it is read with an `issues` list
- **THEN** the text holds U+FFFD at that place, `issues` holds one `altium.sch.text-undecodable` warning, and the raw value holds `81`

#### Scenario: Unknown code page
- **WHEN** `read_schematic(data, codepage="klingon")` runs
- **THEN** it raises `ValueError` naming the code page

### Requirement: Schematic document streams
`read_schematic` on a compound file SHALL read the stream `FileHeader` and, when present, `Additional` and `Storage`, and SHALL keep every other stream.
- A missing `FileHeader` MUST raise `FormatError` with `locator` `FileHeader`.
- The first record of `FileHeader` is the header. Its `HEADER` text MUST equal `Protel for Windows - Schematic Capture Binary File Version 5.0`, compared without letter case; another text MUST raise `FormatError` with `locator` `FileHeader/record 0`. The header is `SchDocument.header`, a `PropertyRecord`; it is not counted in the record index.
- `SchDocument.records` MUST hold the records after the header, in stream order; record `n` has `ref == RecordRef("main", n)`.
- A `WEIGHT` that differs from the number of records after the header MUST give one `altium.sch.weight-mismatch` warning and MUST NOT stop the reading.
- `Additional`, when present, MUST start with a header record of the same text. `SchDocument.additional_header` holds it and `SchDocument.additional` the records after it, with `ref == RecordRef("additional", n)`. A missing `WEIGHT` there is accepted. An `Additional` stream of 0 bytes MUST give one `altium.sch.empty-stream` warning and an empty `additional`. A document without the stream has `additional_header is None`.
- `Storage` MUST be read by "Storage stream and embedded files".
- Every other stream of the root and every storage MUST be kept in `SchDocument.extra_streams` (path to bytes, in directory order) with one `altium.sch.unknown-stream` info each.
- Stream names MUST be matched without letter case.
- `SchDocument.streams` MUST map each stream that was read to its exact bytes, and `read.sch.encode_stream(document, name) -> bytes` MUST return those bytes rebuilt from the records (header, frames, property lists), for `FileHeader`, `Additional` and `Storage`.

#### Scenario: Three streams
- **GIVEN** an authored binary schematic with `FileHeader` (header and 4 records), `Additional` (header with `WEIGHT=3` and 3 records) and `Storage`
- **WHEN** `read_schematic` runs
- **THEN** `len(records)` is 4, `len(additional)` is 3, `additional[0].ref` is `RecordRef("additional", 0)`, and `encode_stream` returns the exact bytes of each of the three streams

#### Scenario: Empty Additional header
- **GIVEN** an `Additional` stream that holds only the header record, without `WEIGHT`
- **WHEN** the document is read with an `issues` list
- **THEN** `additional` is `()`, `additional_header` is not `None`, and `issues` is empty

#### Scenario: Wrong weight
- **GIVEN** a `FileHeader` whose header says `WEIGHT=9` and that holds 4 records
- **WHEN** the document is read with an `issues` list
- **THEN** 4 records are returned and `issues` holds one `altium.sch.weight-mismatch` warning with both numbers

#### Scenario: Unknown stream kept
- **GIVEN** a compound file with one more root stream `Extra` of 5 bytes
- **WHEN** the document is read with an `issues` list
- **THEN** `extra_streams["Extra"]` is those 5 bytes and `issues` holds one `altium.sch.unknown-stream` info naming `Extra`

### Requirement: ASCII schematic form
`read_schematic` on bytes that start with `|HEADER=` SHALL read the ASCII form into the same `SchDocument`, with `form == "ascii"`.
- A UTF-8 byte-order mark before the first line MUST be accepted and kept in `SchDocument.preamble`.
- Lines end with CR LF or LF. Each record MUST keep its exact bytes, line end included, in `payload`; a last line without a line end is accepted.
- A line that ends with the two characters `|>` MUST be joined with the next line into one record; the record's `payload` holds both lines as they are.
- An empty line MUST be kept as an `UnknownRecord` (in `SchDocument.blank_lines`) and MUST NOT be counted as a record by the owner index.
- The first line is the header. Its `HEADER` text MUST equal `Protel for Windows - Schematic Capture Ascii File Version 5.0` without letter case, else `FormatError` with `locator` `line 1`.
- A later line whose first key is `HEADER` starts a new section, and the record index restarts at 0 after it. A section whose header text is the ASCII or the binary schematic header is the `Additional` section; one whose text is `Icon storage` is the storage section; any other is kept in `SchDocument.extra_sections` with one `altium.sch.unknown-stream` info.
- `encode_stream(document, "ascii")` MUST return the file's bytes.
- Property lists, text decoding, typed records, lengths and the owner tree follow the same requirements as the binary form.

#### Scenario: Fenolite's own ASCII sample
- **GIVEN** the bytes of `tests/data/altium/sample/altium_sample.SchDoc` (ASCII) and of `tests/data/altium/sample/binary/altium_sample.SchDoc`
- **WHEN** `read_schematic` runs with an `issues` list
- **THEN** `form` is `"ascii"`, `issues` is empty, the record classes and their property lists equal those of the binary file record for record, and `encode_stream(document, "ascii")` equals the ASCII file

#### Scenario: Line ends and continuation
- **GIVEN** an authored ASCII schematic whose lines end with LF, with one record split after `|>` over two lines
- **WHEN** it is read
- **THEN** the split record is one record with the keys of both lines, and `encode_stream` returns the bytes with LF ends and the split in place

#### Scenario: Second header starts the Additional section
- **GIVEN** an authored ASCII schematic with a second schematic header line followed by a record 215 and a record 216
- **WHEN** it is read
- **THEN** `additional` holds the two records with refs `("additional", 0)` and `("additional", 1)`, and `records` holds only the records before that header

#### Scenario: Byte-order mark
- **GIVEN** the ASCII sample with the bytes `EF BB BF` put before it
- **WHEN** `detect` and `read_schematic` run
- **THEN** `detect` returns `"ascii"`, `preamble` is those 3 bytes, and the records are unchanged

### Requirement: Typed records
`read.sch.records` SHALL define the frozen base class `SchRecord` and one subclass per record id of the table below; `RECORD_TYPES` SHALL map each id to its class, and the table SHALL be closed.

| id | class | id | class | id | class |
|---|---|---|---|---|---|
| 1 | `Component` | 15 | `SheetSymbol` | 34 | `Designator` |
| 2 | `Pin` | 16 | `SheetEntry` | 37 | `BusEntry` |
| 3 | `IeeeSymbol` | 17 | `PowerPort` | 39 | `Template` |
| 4 | `Label` | 18 | `Port` | 41 | `Parameter` |
| 5 | `Bezier` | 22 | `NoErc` | 43 | `WarningSign` |
| 6 | `Polyline` | 25 | `NetLabel` | 44 | `ImplementationList` |
| 7 | `Polygon` | 26 | `Bus` | 45 | `Implementation` |
| 8 | `Ellipse` | 27 | `Wire` | 46 | `MapDefinerList` |
| 9 | `PieChart` | 28 | `TextFrame` | 47 | `MapDefiner` |
| 10 | `RoundRectangle` | 29 | `Junction` | 48 | `ImplementationParameters` |
| 11 | `EllipticalArc` | 30 | `Image` | 215 | `HarnessConnector` |
| 12 | `Arc` | 31 | `Sheet` | 216 | `HarnessEntry` |
| 13 | `Line` | 32 | `SheetName` | 217 | `HarnessType` |
| 14 | `Rectangle` | 33 | `SheetFileName` | 218 | `SignalHarness` |
| | | | | 226 | `Hyperlink` |

- Every `SchRecord` MUST hold `ref`, `kind`, `payload`, `offset`, `props` (`None` for a binary record), `record_id` (`None` when there is no integer `RECORD`), `owner`, `children`, `owner_part` (`OWNERPARTID`, default -1) and `owner_display_mode` (`OWNERPARTDISPLAYMODE`, default 0).
- A record whose id is not in the table, a binary record that is not a pin, and a malformed record MUST be an `UnknownRecord`. One `altium.sch.unknown-record` info per distinct unknown id and file MUST name the id and its count. An `UnknownRecord` takes part in the owner tree like any other record.
- Each class MUST declare `MODELED`, the folded keys and key patterns it reads (such as `X<n>` and `Y<n>` of a polyline), and MUST expose `unknown_keys`, the folded keys of its property list that `MODELED` does not cover, in file order. `RECORD`, `OWNERINDEX`, `OWNERPARTID`, `OWNERPARTDISPLAYMODE`, `OWNERINDEXADDITIONALLIST`, `INDEXINSHEET` and `UNIQUEID` are modelled by the base class.
- Typed attributes MUST be read-only views of `props`: no attribute stores a value that `props` does not hold. Each attribute and its key MUST be a row of `docs/formats/altium/schematic-records.md` with a source and an evidence label.
- The attributes that later changes rely on MUST exist with these names: `Component.lib_reference`, `.design_item_id`, `.source_library`, `.location`, `.orientation`, `.mirrored`, `.unique_id`, `.part_count`, `.current_part`, `.display_mode_count`, `.display_mode`; `Pin.name`, `.designator`, `.electrical`, `.location`, `.length`, `.direction`, `.hidden`, `.name_shown`, `.designator_shown`, `.hot_end`; `Wire.points`, `Bus.points`, `SignalHarness.points`; `NetLabel.text`, `.location`; `PowerPort.text`, `.location`, `.style`, `.orientation`; `Port.name`, `.location`, `.width`, `.height`, `.io_type`, `.harness_type`, `.unique_id`; `SheetSymbol.location`, `.x_size`, `.y_size`, `.unique_id`; `SheetEntry.name`, `.side`, `.distance`, `.io_type`, `.harness_type`; `SheetName.text`, `SheetFileName.text`; `Junction.location`; `NoErc.location`; `Designator.text`; `Parameter.name`, `.text`; `Implementation.model_name`, `.model_type`, `.is_current`, `.data_files`; `HarnessConnector.location`, `.x_size`, `.y_size`, `.side`, `.primary_position`; `HarnessEntry.name`, `.side`, `.distance`; `HarnessType.text`; `Sheet.fonts`, `.sheet_style`, `.custom_size`, `.portrait`, `.title_block`, `.border`; `Template.file_name`; `Image.file_name`, `.embedded`, `.location`, `.corner`; `Label.text`, `.location`, `.font_id`, `.orientation`.
- A colour MUST be `Color(red, green, blue)` from the integer's bits 0-7, 8-15 and 16-23. An orientation in quarter turns MUST be an integer 0 to 3. An angle given as a decimal number of degrees MUST be an integer number of microdegrees parsed from the decimal text without a float.

#### Scenario: Wire with an unknown key
- **GIVEN** a record `|RECORD=27|OWNERPARTID=-1|LINEWIDTH=1|COLOR=8388608|LOCATIONCOUNT=2|X1=10|Y1=20|X2=30|Y2=20|FUTUREKEY=7`
- **WHEN** it is read
- **THEN** it is a `Wire` with two points, `color == Color(0, 0, 128)`, `unknown_keys == ("FUTUREKEY",)`, and `props.to_bytes()` equals the record's text

#### Scenario: Unknown record id
- **GIVEN** a schematic with two records `|RECORD=209|…` between known records
- **WHEN** it is read with an `issues` list
- **THEN** both are `UnknownRecord` with `record_id == 209` and their full property lists, `issues` holds one `altium.sch.unknown-record` info naming `209` and the count 2, and the indexes of the later records count them

#### Scenario: Table and page agree
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_sch_records_table.py` compares `RECORD_TYPES` and every class's `MODELED` with the tables of `docs/formats/altium/schematic-records.md`
- **THEN** every id, class and modelled key has a row with a registered source, and no row names a key that no class models

#### Scenario: Angle without a float
- **GIVEN** an arc record with `|STARTANGLE=45.500|ENDANGLE=270`
- **WHEN** it is read
- **THEN** `start_angle` is `45_500_000` and `end_angle` is `270_000_000` microdegrees, both `int`

### Requirement: Lengths and fractions
`read.sch.units.SchLength` SHALL hold a length as `value`, an integer count of 1/100 000 of the schematic unit of 10 mil.
- A length key `<K>` with the optional key `<K>_FRAC` MUST give `value = int(<K>) × 100_000 + int(<K>_FRAC)`, a missing key counting as 0 and each integer keeping its own sign.
- `SchLength.units` MUST be `value` divided by 100 000 rounded towards negative infinity, and `SchLength.frac` the remainder, 0 to 99 999.
- `SchLength.nm()` MUST return `value × 127 / 50` nanometres rounded half to even, and `SchLength.exact` MUST be `True` exactly when `value` is a multiple of 50. `UNIT_NM` MUST be `254_000`.
- `SchLength.mils()` MUST return a `fractions.Fraction`. No length is a float anywhere in the reader.
- A point is a pair `(SchLength, SchLength)` in the file's frame: X rightwards, Y upwards. The reader MUST NOT flip, rotate or translate a coordinate.
- The distance of a sheet entry and of a harness entry MUST be `DISTANCEFROMTOP × 1_000_000 + DISTANCEFROMTOP_FRAC1` (steps of 10 units, and a fraction in 1/100 000 unit).
- The `<n>`-th point of a polyline MUST use `X<n>`, `Y<n>`, `X<n>_FRAC` and `Y<n>_FRAC`. Saved files leave out a key whose value is zero, so the points are 1 to `LOCATIONCOUNT`, a point whose keys are all left out being (0, 0), when `LOCATIONCOUNT` is at most the record's length in bytes; any point with a key past the count is read too.
- Lengths of a binary pin follow "Binary pin records".
- Every `_FRAC` key of a modelled length MUST count as modelled.

#### Scenario: Whole units
- **GIVEN** `|LOCATION.X=115|LOCATION.Y=76`
- **WHEN** the location is read
- **THEN** it is `(SchLength(11_500_000), SchLength(7_600_000))`, `nm()` gives `29_210_000` and `19_304_000`, and both are exact

#### Scenario: Half a unit
- **GIVEN** `|LOCATION.X=12|LOCATION.X_FRAC=50000`
- **WHEN** the length is read
- **THEN** `value` is `1_250_000`, `mils()` is `Fraction(125)`, `nm()` is `3_175_000` and `exact` is `True`

#### Scenario: A fraction that is not a whole nanometre
- **GIVEN** `|LOCATION.X=12|LOCATION.X_FRAC=1`
- **WHEN** the length is read
- **THEN** `nm()` is `3_048_003` and `exact` is `False`

#### Scenario: Negative coordinate
- **GIVEN** `|LOCATION.X=-3|LOCATION.X_FRAC=-50000`
- **WHEN** the length is read
- **THEN** `value` is `-350_000`, `units` is `-4` and `frac` is `50_000`

#### Scenario: Sheet entry distance
- **GIVEN** a sheet entry with `|DISTANCEFROMTOP=4|DISTANCEFROMTOP_FRAC1=500000`
- **WHEN** it is read
- **THEN** `distance.value` is `4_500_000`, which is 45 units

### Requirement: Owner tree of a schematic document
`read_schematic` SHALL set `owner` and `children` of every record from `OWNERINDEX`, so the records form a forest rooted at the sheet level.
- In `FileHeader` (and the first section of the ASCII form), `OWNERINDEX=<i>` names record `i` of `records`. A record without `OWNERINDEX` is at the sheet level: its `owner` is `None`.
- The owner MUST be an earlier record. An `OWNERINDEX` that is negative, not earlier, or past the end MUST leave the record at the sheet level with one `altium.sch.orphan-record` warning naming the record and the index. No record is dropped.
- `children` MUST list the refs of the records that name this record, in stream order.
- `SchDocument.sheet` MUST be record 0 when it is a `Sheet`, else `None` with one `altium.sch.no-sheet` warning.
- `SchDocument.roots` MUST list the refs of the records without owner, `main` first and then `additional`.
- `SchDocument.get(ref)`, `.owner_of(record)`, `.children_of(record)`, `.walk(record)` (the record and its descendants, depth first, in stream order) and `.of_type(cls)` MUST exist. `walk` MUST NOT recurse without bound: it MUST work on a chain of 100 000 records.
- A component's designator, parameters, pins, graphics and implementation list are its children; an implementation's map definer list and parameters are children of the implementation, as the indexes say. The reader MUST NOT infer an owner from position in a schematic document.

#### Scenario: Footprint chain
- **GIVEN** records 5 (`RECORD=1`), 9 (`RECORD=44`, `OWNERINDEX=5`), 10 (`RECORD=45`, `OWNERINDEX=9`), 11 (`RECORD=46`, `OWNERINDEX=10`) and 12 (`RECORD=48`, `OWNERINDEX=10`)
- **WHEN** the document is read
- **THEN** `walk(records[5])` yields 5, 9, 10, 11, 12 among the component's other children, and `owner_of(records[11])` is the `Implementation`

#### Scenario: Owner that comes later
- **GIVEN** record 3 with `OWNERINDEX=8` in a file of 10 records
- **WHEN** the document is read with an `issues` list
- **THEN** record 3 has `owner is None`, its ref is in `roots`, and `issues` holds one `altium.sch.orphan-record` warning naming record 3 and index 8

#### Scenario: Sheet-level records
- **GIVEN** the binary sample `tests/data/altium/blink/blink.SchDoc`
- **WHEN** it is read
- **THEN** every `Wire`, `NetLabel`, `PowerPort`, `Component` and the `Sheet` has `owner is None`, and every `Pin` has a `Component` as owner

### Requirement: Additional stream and harness records
Records of the `Additional` stream SHALL be read into `SchDocument.additional` with the same classes, and SHALL get their owner by these rules:
- with `OWNERINDEXADDITIONALLIST=T`, the owner is record `OWNERINDEX` of `additional`, and a missing `OWNERINDEX` means index 0;
- without that key, a present `OWNERINDEX` names a record of `records`, and a missing one leaves the record at the sheet level.

The orphan rule of "Owner tree of a schematic document" applies in each index space. A record of `additional` MAY own records of `additional` only.
- `HarnessConnector.side` MUST read `HARNESSCONNECTORSIDE` and, when that key is absent, `SIDE`; `primary_position` MUST read `PRIMARYCONNECTIONPOSITION` as a `SchLength` in units.
- `SchDocument.harnesses()` MUST return, per `HarnessConnector` in stream order, a `Harness(connector, entries, type)` with its `HarnessEntry` children in stream order and its `HarnessType` child or `None`.
- The reader MUST accept records 215 to 218 in `FileHeader` too, and any other record in `Additional`, without a warning.
- `Port.harness_type` and `SheetEntry.harness_type` MUST read `HARNESSTYPE`, `""` when absent.
- The reader MUST NOT read `.Harness` definition files. Change c0042 lists them as project documents of the kind `harness`; no v0.3 change reads their content, and harness connectivity comes from the records above.

#### Scenario: Children of the first connector
- **GIVEN** an `Additional` stream with record 0 a connector, records 1 and 2 entries with `OWNERINDEXADDITIONALLIST=T` and no `OWNERINDEX`, record 3 a type with the same key, and record 4 a signal harness line
- **WHEN** the document is read
- **THEN** `harnesses()` returns one `Harness` with two entries and a type, record 4 has `owner is None`, and `issues` is empty

#### Scenario: Second connector
- **GIVEN** the same stream followed by a connector at index 5 and an entry with `OWNERINDEXADDITIONALLIST=T` and `OwnerIndex=5`
- **WHEN** the document is read
- **THEN** the entry's owner is `RecordRef("additional", 5)` and `harnesses()` returns two items

#### Scenario: Connector side key
- **GIVEN** a connector with `HARNESSCONNECTORSIDE=1` and another with only `SIDE=1`
- **WHEN** both are read
- **THEN** both have `side == 1`, and both keys are modelled

#### Scenario: No Additional stream
- **GIVEN** the binary sample `tests/data/altium/blink/blink.SchDoc`, which has no `Additional` stream
- **WHEN** it is read
- **THEN** `additional` is `()`, `additional_header` is `None` and `harnesses()` is `()`

### Requirement: Storage stream and embedded files
The `Storage` stream SHALL be read into `SchDocument.storage_header` (its first record, a property list) and `SchDocument.embedded`, one `EmbeddedFile` per later record, with every frame kept.
- An `EmbeddedFile` MUST hold `kind`, `payload` (the exact bytes) and, when the payload has the layout of `docs/formats/altium/schematic-records.md` ("Storage"), `name` and `packed` (the compressed bytes); otherwise `name` is `""` and `packed` is `None`, with one `altium.sch.storage-opaque` info.
- `EmbeddedFile.data(limit: int = MAX_EMBEDDED)` MUST decompress `packed` on request only, MUST stop and raise `FormatError` when the output would pass `limit`, and `MAX_EMBEDDED` MUST be 64 MiB. Reading a document MUST NOT decompress anything.
- A `Storage` stream that holds only its header gives `embedded == ()`. A document without the stream has `storage_header is None`.
- `Image.embedded` MUST be `True` for `EMBEDIMAGE=T`; `SchDocument.image_data(image)` MUST return the `EmbeddedFile` whose `name` equals the image's `FILENAME`, or `None`.

#### Scenario: Icon storage only
- **GIVEN** the binary sample `tests/data/altium/blink/blink.SchDoc`, whose `Storage` is the one record `|HEADER=Icon storage`
- **WHEN** it is read
- **THEN** `storage_header.props.text("HEADER")` is `Icon storage`, `embedded` is `()`, and `encode_stream(document, "Storage")` equals the stream

#### Scenario: Unknown storage payload
- **GIVEN** a `Storage` stream with a second record of kind 1 and 7 arbitrary bytes
- **WHEN** it is read with an `issues` list
- **THEN** `embedded[0].payload` is the 7 bytes, `packed` is `None`, and `issues` holds one `altium.sch.storage-opaque` info

#### Scenario: Decompression limit
- **GIVEN** an authored embedded file whose packed bytes expand to 2 MiB
- **WHEN** `data(limit=1_048_576)` runs
- **THEN** it raises `FormatError` naming the limit, and `data()` returns the 2 MiB

### Requirement: Parts and display modes
The reader SHALL expose the parts and the display modes of a component, in a schematic and in a library, without choosing among them.
- `Component.part_count` MUST be `PARTCOUNT - 1`, and 1 when the key is missing or the result is below 1. `current_part` MUST read `CURRENTPARTID` (default 1), `display_mode_count` `DISPLAYMODECOUNT` (default 1) and `display_mode` `DISPLAYMODE` (default 0).
- A child's `owner_part` is -1 (no part: designator, parameters, implementation records), 0 (Part Zero: on every part) or a part number from 1. Its `owner_display_mode` is a 0-based mode.
- `SchDocument.children_of(component, part=None, mode=None)` and `SchLibComponent.children(part=None, mode=None)` MUST return the direct children, filtered when a filter is given: `part=k` keeps children whose `owner_part` is `k`, 0 or -1; `mode=m` keeps children whose `owner_display_mode` is `m` or whose `owner_part` is -1.
- `SchDocument.shown_children(component)` MUST equal `children_of(component, part=component.current_part, mode=component.display_mode)`.
- `SchLibComponent.parts` MUST be `range(1, part_count + 1)` and `SchLibComponent.modes` `range(display_mode_count)`.
- A child whose `owner_part` is above `part_count`, or whose `owner_display_mode` is not below `display_mode_count`, MUST be kept and MUST give one `altium.sch.part-out-of-range` warning per component.
- In a schematic, several component records MAY carry the same designator text (one record per placed part). The reader MUST return each as its own `Component`; grouping them is change c0043's.

#### Scenario: Two parts and a common pin
- **GIVEN** a library component with `PARTCOUNT=3`, pins 1 and 2 with `OWNERPARTID` 1, pins 3 and 4 with `OWNERPARTID` 2, a pin 5 with `OWNERPARTID` 0, and a designator with `OWNERPARTID` -1
- **WHEN** it is read
- **THEN** `part_count` is 2, `children(part=1)` holds pins 1, 2 and 5 and the designator, and `children(part=2)` holds pins 3, 4 and 5 and the designator

#### Scenario: Alternate display mode
- **GIVEN** a component with `DISPLAYMODECOUNT=2`, one rectangle with no `OWNERPARTDISPLAYMODE` and one with `OWNERPARTDISPLAYMODE=1`
- **WHEN** `children(part=1, mode=0)` and `children(part=1, mode=1)` run
- **THEN** each returns exactly one of the two rectangles, and both return the designator

#### Scenario: Placed part of a multi-part component
- **GIVEN** a schematic component with `PARTCOUNT=3`, `CURRENTPARTID=2` and the children of both parts
- **WHEN** `shown_children` runs
- **THEN** it returns the children of part 2, the Part Zero children and the children without a part, and none of part 1

#### Scenario: Part out of range
- **GIVEN** a component with `PARTCOUNT=2` and a pin with `OWNERPARTID=3`
- **WHEN** it is read with an `issues` list
- **THEN** the pin is among the component's children and `issues` holds one `altium.sch.part-out-of-range` warning naming the component

### Requirement: Schematic library container
`read_schlib` SHALL read the library header, the section keys and one component per storage into a `SchLibrary`.
- `FileHeader` MUST exist, and its first record's `HEADER` MUST equal `Protel for Windows - Schematic Library Editor Binary File Version 5.0` without letter case; otherwise `FormatError` with `locator` `FileHeader` or `FileHeader/record 0`.
- `SchLibrary.header` is that record. `SchLibrary.header_tail` MUST hold the bytes of `FileHeader` after it, unchanged; when they have the layout of the name list (`docs/formats/altium/schematic-library.md`), `SchLibrary.listed_names` holds the names, else it is `()`.
- `SchLibrary.fonts` MUST read the font table of the header (`FONTIDCOUNT`, `SIZE<i>`, `FONTNAME<i>`), as `Sheet.fonts` does.
- `SectionKeys`, when present, MUST give `SchLibrary.section_keys`, a mapping from lib ref to storage name, from `KEYCOUNT`, `LIBREF<i>` and `SECTIONKEY<i>`.
- Every root storage that holds a stream `Data` is a component. `SchLibrary.components` MUST list them in the order of the header's `LIBREF<i>` keys (each mapped through `section_keys`, then matched to a storage name without letter case, a `/` of the section key matching `_` of the storage name), then every storage the header does not list, in directory order, with one `altium.schlib.unlisted-component` info each. A listed lib ref with no storage MUST give one `altium.schlib.missing-component` warning.
- A `SchLibComponent` MUST hold `name` (the header's lib ref, else the component record's `LIBREFERENCE`, else the storage name), `storage_name`, `description`, `records` (refs `RecordRef("data", n)`), `component` (record 0 when it is a `Component`, else `None` with one `altium.schlib.no-component` warning), `pins`, `side_streams` and `extra_streams`.
- `Data` has no header record. An empty `Data` MUST give a component with no record and one `altium.sch.empty-stream` warning. A storage without `Data` MUST be kept in `SchLibrary.extra_streams` with its streams.
- Owner rule in `Data`: a record with an `OWNERINDEX` that names an earlier record of the same `Data` has that owner; any other record after record 0 is owned by record 0. No orphan warning is given in a library.
- `Storage` MUST be read as in a schematic. Every other root stream MUST be kept in `SchLibrary.extra_streams` with one `altium.sch.unknown-stream` info.
- `COMPCOUNT` and `WEIGHT` MUST be compared with what was read; a difference MUST give one `altium.sch.weight-mismatch` warning each and MUST NOT stop the reading.
- `read.schlib.encode_stream(library, path) -> bytes` MUST return the exact bytes of `FileHeader`, `SectionKeys`, `Storage` and every `<storage>/Data`.
- `SchLibrary.get(name)` MUST find a component by lib ref without letter case and raise `KeyError` otherwise.

#### Scenario: Fenolite's own library
- **GIVEN** the bytes of `tests/data/altium/sample/FenoliteSample.SchLib`
- **WHEN** `read_schlib` runs with an `issues` list
- **THEN** six components are returned in the header's order, each with a `Component` as record 0, `issues` is empty, and `encode_stream` returns the bytes of every stream read

#### Scenario: Section key
- **GIVEN** an authored library whose header lists a lib ref of 40 characters, stored under a 31-character storage name through `SectionKeys`
- **WHEN** it is read
- **THEN** the component's `name` is the 40-character lib ref and its `storage_name` the 31-character key

#### Scenario: Storage the header does not list
- **GIVEN** an authored library whose header has `COMPCOUNT=1` and that holds two component storages
- **WHEN** it is read with an `issues` list
- **THEN** two components are returned, the listed one first, and `issues` holds one `altium.schlib.unlisted-component` info and one `altium.sch.weight-mismatch` warning

#### Scenario: Owner inside Data
- **GIVEN** a `Data` stream with the component, a record 44 without `OWNERINDEX`, a record 45 with `OWNERINDEX=1` and a record 45 with `OWNERINDEX=7` in a stream of 4 records
- **WHEN** it is read with an `issues` list
- **THEN** the first 45 is owned by the 44, the second 45 and the 44 are owned by the component, and `issues` is empty

### Requirement: Binary pin records
A record of kind other than 0 whose payload starts with the little-endian 32-bit integer 2 SHALL be read as a `Pin`, by the field table "Pin fields" of `docs/formats/altium/schematic-library.md`, in a library and in a schematic document alike.
- The `Pin` MUST expose the same attributes as a text pin (`RECORD=2`): `owner_part`, `owner_display_mode`, `name`, `designator`, `electrical`, `location`, `length`, `direction`, `hidden`, `name_shown`, `designator_shown`, `hot_end`, plus `description`, `formal_type`, `inner_edge`, `outer_edge`, `inside`, `outside`, `swap_group`, `part_and_sequence`, `default_value` and `color`. `binary` MUST be `True` and `props` `None`.
- `direction` is bits 0 and 1 of the conglomerate byte (0 right, 1 up, 2 left, 3 down); `hot_end` is `location` moved by `length` in that direction.
- A short string is decoded by "Text decoding" with the reader's code page; its raw bytes stay in `payload`.
- The strings after the designator are optional from the end: a payload that ends after the designator, after the swap group or after the part-and-sequence string MUST be read, the missing strings being `""`, and `Pin.strings_read` MUST say how many of the five strings were present.
- Bytes after the last known field MUST be kept in `Pin.tail` with one `altium.sch.pin-trailing-bytes` info per component. A payload cut inside a fixed field or inside the name or designator MUST become an `UnknownRecord` with one `altium.sch.malformed-record` warning.
- `Pin.unknown_byte` MUST hold the byte at offset 4.
- A binary record whose first integer is not 2 MUST be an `UnknownRecord`.
- `read.sch.pins.encode_pin(pin) -> bytes` MUST return the payload that was read.

#### Scenario: Worked pin of the format page
- **GIVEN** the 34-byte payload of the worked pin of `schematic-library.md` (pin `1` named `IN`, passive, leftwards, length 20 units, body end (-30, 10), part 1)
- **WHEN** it is read
- **THEN** `designator` is `1`, `name` is `IN`, `electrical` is 4, `direction` is 2, `length.value` is `2_000_000`, `location` is `(SchLength(-3_000_000), SchLength(1_000_000))`, `hot_end` is `(SchLength(-5_000_000), SchLength(1_000_000))`, `strings_read` is 5 and `tail` is `b""`

#### Scenario: Pin without its last strings
- **GIVEN** the same payload cut after the designator
- **WHEN** it is read with an `issues` list
- **THEN** it is a `Pin` with `strings_read == 2`, `swap_group == ""`, and `issues` is empty

#### Scenario: Bytes after the last string
- **GIVEN** the same payload followed by `01 02 03`
- **WHEN** it is read with an `issues` list
- **THEN** `tail` is those 3 bytes, `encode_pin` returns the 37 bytes, and `issues` holds one `altium.sch.pin-trailing-bytes` info

#### Scenario: Text pin and binary pin agree
- **GIVEN** a text pin and a binary pin authored with the same values
- **WHEN** both are read
- **THEN** every shared attribute is equal, and only `binary`, `props`, `payload` and `strings_read` differ

### Requirement: Pin side streams
The streams `PinFrac`, `PinWideText`, `PinTextData` and `PinSymbolLineWidth` of a component storage SHALL be kept in `SchLibComponent.side_streams` (name to exact bytes), and any other stream of the storage in `SchLibComponent.extra_streams`.
- Names MUST be matched without letter case, and the spellings with `Pins` (`PinsFrac`, …) MUST be accepted as the same streams.
- A side stream MUST be decoded only when its layout is a fact row of `docs/formats/altium/schematic-library.md` with a permitted source and the stream matches that layout to its last byte. A stream that is not decoded MUST give one `altium.schlib.side-stream-opaque` info naming the component and the stream, and MUST change no pin.
- A decoded `PinFrac` MUST add its fractions to `location` and `length` of the pin it names, in 1/100 000 unit; `Pin.fraction_source` MUST then be `"PinFrac"`.
- A decoded `PinWideText` MUST replace the text view of the name or designator it names; the short string stays in `payload`.
- An entry that names no pin MUST give one `altium.schlib.side-stream-orphan` warning and MUST be kept in the raw bytes.
- `SIDE_STREAMS_DECODED` MUST list the streams the reader decodes; it MAY be empty.

#### Scenario: Opaque side stream
- **GIVEN** an authored component storage with `Data` and a stream `PinSymbolLineWidth` of 12 arbitrary bytes
- **WHEN** the library is read with an `issues` list
- **THEN** `side_streams["PinSymbolLineWidth"]` is the 12 bytes, every pin equals the pin read without the stream, and `issues` holds one `altium.schlib.side-stream-opaque` info

#### Scenario: Unknown stream of a component
- **GIVEN** a component storage with one more stream `Whatever`
- **WHEN** the library is read
- **THEN** `extra_streams["Whatever"]` holds its bytes and `side_streams` does not

#### Scenario: Decoded streams are documented
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_schlib_side.py -k documented` runs
- **THEN** every name in `SIDE_STREAMS_DECODED` has a layout row in `schematic-library.md` that cites a registered source other than S-0142, and every decoded stream has an authored fixture that changes a pin

### Requirement: Nothing read is lost
Reading SHALL be lossless: for every input that `read_schematic` or `read_schlib` accepts, the bytes of every stream can be rebuilt from the result, and every byte of the input that is not container structure belongs to exactly one kept item.
- `encode_stream` MUST rebuild each stream from the parsed parts, not return a stored copy: property lists through `PropertyList.to_bytes()`, pins through `encode_pin`, frames through `enframe`. `SchDocument.streams` and `SchLibrary.streams` hold the bytes as read, for comparison.
- `read.sch.check_identity(document_or_library) -> tuple[str, ...]` MUST return the paths of the streams whose rebuilt bytes differ from the bytes read, and `()` for every accepted input.
- An item the reader does not understand MUST be kept as one of: an unknown key (`unknown_keys`), an `UnknownRecord`, a pin `tail`, an opaque `EmbeddedFile`, a side stream, `header_tail`, `extra_streams` or `extra_sections`. The reader MUST NOT normalise letter case, key order, spaces, line ends or number formats.
- `census()` of a `SchDocument` and of a `SchLibrary` MUST return a JSON-ready mapping with: the form, the header text, the number of records per record id, the unknown record ids with counts, the unknown keys per record id (key names with counts), the duplicated keys, the number of lengths with a fraction and of lengths that are not exact in nanometres, the stream names with sizes, and the issue codes with counts. It MUST hold key names, ids and numbers only, never a value of a record.

#### Scenario: Identity on the authored fixtures
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_sch_identity.py` reads every authored fixture of `tests/unit/backends/altium/read/` and every Altium file under `tests/data/altium/`
- **THEN** `check_identity` returns `()` for each

#### Scenario: Identity under mutation
- **GIVEN** a hypothesis strategy that builds property lists with arbitrary keys, repeated keys, empty fields, bytes from 0x01 to 0xFF except `|`, and frames of kinds 0 to 255
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_sch_identity.py -k property` runs
- **THEN** every generated stream that `deframe` accepts is rebuilt byte for byte

#### Scenario: Census holds no value
- **GIVEN** an authored schematic whose label text is `SECRET_NET`
- **WHEN** `census()` is dumped as JSON
- **THEN** the text `SECRET_NET` does not occur in it

### Requirement: Located errors and issue codes
The reader SHALL raise `fenolite.core.errors.FormatError` only when it cannot return a result, and SHALL report everything else as an `Issue` of the closed set `read.sch.ISSUE_CODES`.
- `FormatError` MUST carry `file` (the `file` argument), a `locator` (`<stream path>/record <n>`, `line <n>` in the ASCII form, or the stream path) and, where one exists, the byte `offset` inside that stream or file.
- Fatal cases: neither form; a missing `FileHeader`; a header text that is not the expected one; a frame cut by the end of its stream; a `CompoundError` raised by `read.cfb`, passed on unchanged.
- Without an `issues` list, findings are dropped and the result is the same.
- Every issue MUST have `where` set to the locator, and the same input MUST give the issues in stream order.

| code | severity | when |
|---|---|---|
| `altium.sch.malformed-record` | warning | a property list without its one final NUL, a record without an integer `RECORD`, or a pin cut inside a required field |
| `altium.sch.bad-value` | warning | a modelled key whose value does not parse |
| `altium.sch.unknown-record` | info | a record id with no class (one per id and file, with the count) |
| `altium.sch.unknown-stream` | info | a stream or ASCII section the reader does not read |
| `altium.sch.empty-stream` | warning | an `Additional` or `Data` stream of 0 bytes |
| `altium.sch.weight-mismatch` | warning | `WEIGHT` or `COMPCOUNT` differs from what was read |
| `altium.sch.orphan-record` | warning | an `OWNERINDEX` that names no earlier record |
| `altium.sch.no-sheet` | warning | record 0 of a schematic is not the sheet |
| `altium.sch.part-out-of-range` | warning | a child's part or display mode is outside its component's counts |
| `altium.sch.text-undecodable` | warning | a byte the decoding does not define |
| `altium.sch.pin-trailing-bytes` | info | bytes after a binary pin's last known field |
| `altium.sch.storage-opaque` | info | a `Storage` record that is not a known embedded file |
| `altium.schlib.unlisted-component` | info | a component storage the header does not list |
| `altium.schlib.missing-component` | warning | a listed lib ref without a storage |
| `altium.schlib.no-component` | warning | a `Data` stream whose record 0 is not the component |
| `altium.schlib.side-stream-opaque` | info | a pin side stream that is kept and not decoded |
| `altium.schlib.side-stream-orphan` | warning | a side-stream entry that names no pin |

#### Scenario: Closed set
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_sch_issues.py` reads every negative fixture
- **THEN** every issue code is a key of `ISSUE_CODES` with the severity of the table, and every code of the table is produced by at least one fixture

#### Scenario: Missing FileHeader
- **GIVEN** a compound file with only a `Storage` stream
- **WHEN** `read_schematic(data, file="a.SchDoc")` runs
- **THEN** it raises `FormatError` with `file` `a.SchDoc` and `locator` `FileHeader`

#### Scenario: Truncated input never crashes
- **GIVEN** every prefix of the binary sample `tests/data/altium/blink/blink.SchDoc` and of its library sample, cut at 257 evenly spaced lengths
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_sch_fuzz.py` reads each
- **THEN** each call returns a result or raises `FormatError`, and never another exception

### Requirement: Bounded reading of untrusted files
The reader SHALL treat its input as untrusted.
- It MUST NOT recurse over record depth, and MUST read a stream of `n` records in time and memory linear in the stream size.
- It MUST NOT evaluate, import, execute or open anything a file names: a file name in a record (`FILENAME`, `MODELDATAFILE<i>`, a sheet file name, a template file name) is returned as text and never resolved against the file system.
- It MUST NOT decompress embedded data while reading ("Storage stream and embedded files").
- A count key that is larger than the record can hold (`LOCATIONCOUNT`, `FONTIDCOUNT`, `KEYCOUNT`, `COMPCOUNT`, `DATAFILECOUNT`) MUST NOT drive an allocation or a loop: items are read from the keys that exist, and a count larger than the record's length in bytes, or smaller than the number of items present, gives one `altium.sch.bad-value` warning. A count that is larger than the items present but not than the record (zero-valued items left out) gives no warning; only `LOCATIONCOUNT` adds items for it (the points at (0, 0) of "Lengths and fractions").

#### Scenario: Huge count
- **GIVEN** a wire with `|LOCATIONCOUNT=2000000000|X1=1|Y1=2|X2=3|Y2=2`
- **WHEN** it is read with an `issues` list
- **THEN** `points` holds the two points, the call returns at once, and `issues` holds one `altium.sch.bad-value` warning

#### Scenario: Deep chain
- **GIVEN** an authored schematic of 100 000 records in which each record owns the next
- **WHEN** it is read and `walk(records[0])` is consumed
- **THEN** 100 000 records are yielded and no `RecursionError` is raised

#### Scenario: File names are not opened
- **GIVEN** an image record whose `FILENAME` is an absolute path that does not exist and a sheet file name `..\..\x.SchDoc`
- **WHEN** the document is read under a file-system access guard
- **THEN** both texts are returned and no file-system call is made

### Requirement: Own output read back by the product reader
The product reader SHALL read every Altium schematic and schematic library that Fenolite writes, with no issue, and SHALL agree with the test reader `tests/_altium_read.py`, which shares no code with it.
- For each schematic under `tests/data/altium/` and each schematic the Altium build examples produce, in the binary and the ASCII form: the records read by `read_schematic`, as lists of `(key, text)` pairs, MUST equal those of `_altium_read.read_records` (ASCII) and `_cfb_read.deframe` (binary).
- For each library: the storages, the records and every binary pin field MUST equal those of `_altium_read.read_schlib`.
- The binary and the ASCII form of one design MUST give equal typed records.
- The test reader MUST NOT be changed by this change, and MUST NOT import the product reader.

#### Scenario: Samples agree
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_sch_own_output.py` runs
- **THEN** every committed sample and every example build is read without an issue, and the two readers agree record for record and pin field for pin field

#### Scenario: Readers stay independent
- **WHEN** `git grep -n "backends.altium.read" tests/_altium_read.py tests/_cfb_read.py tests/_altium_pcb_read.py` runs
- **THEN** it prints nothing

### Requirement: Corpus reading and census
Tests marked `needs_corpus` SHALL read every corpus row whose `uses` holds `altium-sch` or `altium-schlib` (`corpus-policy`, "Altium schematic corpus rows") and SHALL check, per file:
- the read raises no exception, and `check_identity` returns `()`;
- no issue of severity `warning` other than those listed, per code and row id, in the table `EXPECTED` of `tests/corpus/test_altium_sch_read.py`, each entry with a one-line reason;
- every `owner` is an earlier record of its index space, and every record is reached from `roots` exactly once;
- every child's part and display mode is inside its component's counts, except where `EXPECTED` says otherwise;
- every length's `nm()` is an integer and every text view decodes.

`tools/altium_census.py --uses TAG [--json]` SHALL print the merged `census()` of the cached rows of a tag: record ids, unknown record ids, unknown keys per record id, key-case styles, `WEIGHT` agreement, owner-rule agreement, fraction counts, pin string counts and tails, side-stream names and sizes, and issue codes. Its output and `docs/evidence/altium-read-schematic.md` MUST hold key names, record ids, row ids and counts only.

The rows MUST come from at least three repositories for schematics and three for libraries. Files and anything derived from them MUST stay in the corpus cache or under `tmp_path`.

#### Scenario: Corpus is read
- **GIVEN** the cached rows of `uv run python tools/corpus_fetch.py --uses altium-sch --uses altium-schlib`
- **WHEN** `FENOLITE_REQUIRE=corpus uv run pytest tests/corpus/test_altium_sch_read.py` runs
- **THEN** every row is read, every check above passes, and `git status --porcelain` is unchanged afterwards

#### Scenario: Corpus absent
- **GIVEN** an empty corpus cache
- **WHEN** `uv run pytest tests/corpus/test_altium_sch_read.py` runs
- **THEN** every test is skipped with the message `run: uv run python tools/corpus_fetch.py`

#### Scenario: Census prints no value
- **GIVEN** the cached rows
- **WHEN** `uv run python tools/altium_census.py --uses altium-sch --json` runs
- **THEN** the output is valid JSON whose strings are key names, record ids, class names, stream names, issue codes and row ids only, which `tests/corpus/test_altium_sch_read.py::test_census_vocabulary` checks against the texts of the files

#### Scenario: ASCII form from corpus records
- **GIVEN** a cached binary schematic
- **WHEN** the test writes its records one per line under `tmp_path`, with the ASCII header and CR LF ends, and reads that file
- **THEN** the typed records of both readings are equal, and nothing is written outside `tmp_path`

### Requirement: Library oracle
`tests/kicad/altium/test_schlib_read_oracle.py` SHALL compare Fenolite's reading of each `altium-schlib` corpus row with the KiCad library that `kicad-cli sym upgrade <row> -o <tmp>.kicad_sym` writes, read by `fenolite.backends.kicad`.
- The test MUST carry `needs_kicad` and `needs_corpus`, run `kicad-cli` only as a subprocess through the package runner, and write only under `tmp_path`.
- Per symbol and unit it MUST compare the set of pins as (number, name with overbars mapped, hot end in nanometres, length in nanometres, direction, hidden flag), the number of units (`part_count`), and the number of body styles against `display_mode_count`.
- A difference that a recorded importer behaviour explains MUST be listed in the test's table `KNOWN`, with the fact row that states it; any other difference fails the test.
- A row that `kicad-cli` refuses or crashes on MUST be listed in `KNOWN` with the exit code and MUST NOT count as evidence.
- The hypothesis rows `H-A-RD-SCH-PIN` and `H-A-RD-SCH-PARTS` become `ORACLE-VERIFIED(kicad-cli)` only for the fields this test compares, on the version it ran.

#### Scenario: Pins agree with the importer
- **GIVEN** `kicad-cli` 10.0.x and the cached `altium-schlib` rows
- **WHEN** `FENOLITE_REQUIRE=kicad,corpus uv run pytest tests/kicad/altium/test_schlib_read_oracle.py` runs
- **THEN** for every row outside `KNOWN`, every symbol's pins and unit count agree, and `git status --porcelain` is unchanged

#### Scenario: Negative control
- **GIVEN** Fenolite's reading of one row with the X of one pin's location negated in the test
- **WHEN** the comparison runs
- **THEN** it reports that pin and its symbol

### Requirement: Reader facts are documented
The facts the reader relies on SHALL be rows of the format pages, each with a source and an evidence label, before the code that uses them is merged.
- `docs/formats/altium/schematic-records.md` (new) MUST hold one table per typed record with its keys, types and defaults, the "Storage" layout, and the reader's own choices.
- `docs/formats/altium/schematic-ascii.md`, `schematic-binary.md` and `schematic-library.md` MUST gain the rows on reading: letter case of keys, the `%UTF8%` twin, the owner rules of each index space, the `_FRAC` rule, the optional pin strings, the side streams and the header's name list.
- Every row below a verified level MUST name an `H-A-RD-SCH-*` hypothesis or an existing Altium hypothesis, and `tests/unit/test_format_facts.py` MUST accept the `H-A-RD-` family on the Altium pages.
- AltiumSharp MUST be cited only as S-0150, version 1 at commit `afe796434b6d2110c745c90abe44a6ddf64f5bca`. No row MAY cite S-0142 or a file of AltiumSharp version 2.
- `docs/evidence/altium-read-schematic.md` (new) MUST hold the census tables and the oracle results, by row id, record id, key name and count.
- `src/fenolite/backends/altium/PROVENANCE.md` MUST gain a section for the reader that states that it was written from the format pages, that the GPL sources were read for facts only, and that the corpus files were fetched, read and never committed.
- No public text of this change MAY name a company, a product design or a person outside the URLs of `docs/evidence/sources.md` and the `url` fields of the corpus manifest.

#### Scenario: Fact tables pass
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py` runs after this change
- **THEN** every row of the four pages has a registered source, a valid label and, below a verified level, a registered hypothesis

#### Scenario: Version 2 is not cited
- **WHEN** `git grep -n "S-0142" docs/formats/altium/schematic-records.md` runs
- **THEN** it prints nothing

#### Scenario: No corpus file in the tree
- **WHEN** `uv run pytest tests/corpus/test_manifest.py tests/residue` runs after this change, with the corpus cache present
- **THEN** it passes: every Altium file in the tree is an authored fixture declared in `tests/data/MANIFEST.toml`, and none equals a cached corpus row

### Requirement: Reader interfaces for later changes
The names below SHALL be the stable surface that changes c0043 (import), c0044 (inspect, check, diff, round trip) and c0046 (sheet templates) build on; `read.sch.__all__` and `read.schlib.__all__` MUST export them.
- From `read.sch`: `read_schematic`, `detect`, `encode_stream`, `check_identity`, `SchDocument`, `SchRecord`, `UnknownRecord`, `PropertyRecord`, `RecordRef`, `PropertyList`, `Prop`, `SchLength`, `Color`, `Font`, `Harness`, `EmbeddedFile`, `RECORD_TYPES`, every class of "Typed records", `ISSUE_CODES`, `DEFAULT_CODEPAGE`, `MAX_EMBEDDED`, `UNIT_NM`, `EVIDENCE`.
- From `read.schlib`: `read_schlib`, `encode_stream`, `SchLibrary`, `SchLibComponent`, `SIDE_STREAMS_DECODED`.
- `SchDocument` MUST offer `components()`, `wires()`, `buses()`, `net_labels()`, `power_ports()`, `ports()`, `junctions()`, `no_ercs()`, `sheet_symbols()`, `harnesses()` and `templates()`, each a tuple in stream order, and `template_children()`, the records owned by a `Template`, in stream order.
- The reader MUST NOT compute a net, a connection or a neutral-model entity, and MUST NOT register a backend. `fenolite capabilities` MUST NOT change with this change.

#### Scenario: Surface exists
- **WHEN** `uv run python -c "from fenolite.backends.altium.read import sch, schlib; print(sorted(set(['read_schematic','detect','encode_stream','check_identity','SchDocument','SchLength','RecordRef','RECORD_TYPES','EVIDENCE']) - set(sch.__all__)), sorted(set(['read_schlib','SchLibrary','SchLibComponent','SIDE_STREAMS_DECODED']) - set(schlib.__all__)))"` runs
- **THEN** it prints `[] []`

#### Scenario: Template records for the sheet-template import
- **GIVEN** an authored schematic with a record 39 that owns two lines and a label
- **WHEN** it is read
- **THEN** `templates()` returns the one `Template` and `template_children()` its three children in stream order

#### Scenario: Capabilities unchanged
- **WHEN** `uv run fenolite capabilities --json` runs before and after this change
- **THEN** both outputs are equal

### Requirement: Pin visibility bits
`Pin.name_shown` and `Pin.designator_shown` SHALL read bits 0x08 and 0x10 of `PINCONGLOMERATE` as show flags when bit 0x20 is set and as hide flags when it is clear (`records.SHOW_FLAGS`; `schematic-library.md`, "Binary pin record"; `H-A-SCHLIB-PINBITS`).
- The 0x20-set reading rests on S-0613, S-0614, S-0130 and S-0131; the 0x20-clear reading on S-0612 alone.
- `direction` and `hidden` MUST NOT depend on 0x20.

#### Scenario: A pin as Altium saves it
- **WHEN** a pin with `PINCONGLOMERATE=58` (0x20, 0x10, 0x08 and leftwards) is read
- **THEN** `name_shown` and `designator_shown` are true and `direction` is 2

#### Scenario: A pin that Fenolite wrote before 0.3.0
- **WHEN** a pin with `PINCONGLOMERATE=18` (0x10 and leftwards, no 0x20) is read
- **THEN** `name_shown` is true, `designator_shown` is false and `direction` is 2

#### Scenario: The check project
- **WHEN** the sheet `tests/data/altium/pinbits/pinbits.SchDoc` is read
- **THEN** the pins of `LED_V1` show neither text, those of `LED_V2` only the number, those of `LED_V3` only the name and those of `LED_V4` both
