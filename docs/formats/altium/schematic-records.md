# Altium schematic records

This page states, in Fenolite's own words, what the schematic reader `fenolite.backends.altium.read.sch` and
`read.schlib` (change c0040) rely on: the records of a schematic document, a template and a schematic library,
their keys, the units of their values, how text is decoded, and the layout of an embedded file. The framing of
the binary form is in `schematic-binary.md`, the ASCII form in `schematic-ascii.md`, the library container and
the binary pin in `schematic-library.md`.

- Sources are listed in `docs/evidence/sources.md`. The record ids, names and keys come from the documentation
  of an open-source converter (S-0130); keys that only KiCad's importer reads come from S-0131, read for facts
  only (GPL; nothing transcribed or followed); harness keys also from the files of S-0187 and S-0188.
  AltiumSharp is cited only as version 1 (S-0150 at commit `afe796434b6d2110c745c90abe44a6ddf64f5bca`).
- The reader is written from this page and the three other schematic pages, never from a source's code.
- Every row is `INFERRED` until the corpus test or the library oracle settles its hypothesis; the labels are
  updated by task 8.2 of change c0040. `tests/unit/test_format_facts.py` checks the fact tables and
  `tests/unit/backends/altium/read/test_sch_records_table.py` checks that the record tables below equal the
  classes' `MODELED` keys.

## Units

| fact | source | label | hypothesis |
|---|---|---|---|
| A length is an integer number of units of 10 mil (254 000 nm); an optional `<key>_FRAC` integer adds 1/100 000 of a unit, so one fraction step is 2.54 nm and is not always a whole nanometre | S-0130, S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| The two integers keep their own signs: the length is `K × 100 000 + K_FRAC` in 1/100 000 unit | S-0131 | CORPUS-VERIFIED (22 rows; 2026-10-05) | H-A-RD-SCH-FRAC |
| A sheet entry's and a harness entry's `DISTANCEFROMTOP` counts steps of 10 units, and `DISTANCEFROMTOP_FRAC1` adds 1/100 000 of a unit, so the distance is `DISTANCEFROMTOP × 1 000 000 + DISTANCEFROMTOP_FRAC1` in 1/100 000 unit | S-0130, S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| The point `n` of a polyline, a polygon, a Bezier curve, a wire, a bus or a signal harness is `X<n>`, `Y<n>` with their `_FRAC` keys, for `n` from 1 to `LOCATIONCOUNT` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| A key whose value is zero is left out in saved files, so a coordinate that is 0 has no key, and a point at (0, 0) has neither `X<n>` nor `Y<n>`: polylines and polygons of saved libraries hold fewer point keys than `LOCATIONCOUNT` | S-0187, S-0188, S-0277, S-0279 | CORPUS-VERIFIED (22 rows; 2026-10-05) | H-A-RD-SCH-FRAC |
| A colour is an integer with red in bits 0 to 7, green in bits 8 to 15 and blue in bits 16 to 23 | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| An angle (`STARTANGLE`, `ENDANGLE`) is a decimal number of degrees with typically three decimals, left out when zero | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| An orientation (`ORIENTATION`) counts quarter turns anticlockwise, 0 to 3 | S-0130, S-0131 | INFERRED | H-A-RD-SCH-CASE |
| Coordinates are in the file's frame: X rightwards, Y upwards, the origin at the sheet's lower-left corner; children of a placed component carry absolute sheet coordinates, and library coordinates are relative to the symbol's origin | S-0130, S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| A count key (`LOCATIONCOUNT`, `FONTIDCOUNT`, `DATAFILECOUNT`, `DESIMPCOUNT`, `KEYCOUNT`, `COMPCOUNT`) states how many numbered items follow; items are numbered from 1 (points, fonts) or from 0 (data files, library components, section keys) | S-0130, S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-SCH-CASE |

## Text

| fact | source | label | hypothesis |
|---|---|---|---|
| Key names are probably compared without letter case; saved files hold upper-case keys (older) and mixed-case keys such as `OwnerIndex` and `Location.X` (newer); readers fold case | S-0130, S-0131, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |
| A key may occur twice in one record (`HOTSPOTGRIDON` of the sheet) | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| Values are 8-bit text in a Windows code page, commonly Windows-1252; a non-ASCII value is often followed by a twin key `%UTF8%<key>` holding the same text in UTF-8 | S-0130, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-RD-SCH-TEXT-2 |
| In saved files every `%UTF8%` twin is valid UTF-8; the plain value differs from the `cp1252` reading of its twin where Altium writes the byte 0x8E for the broken bar U+00A6, and in files saved under another system code page. The twin, not the plain value, holds the text | S-0130, S-0187, S-0188, S-0279 | CORPUS-VERIFIED (22 rows; 2026-10-05) | H-A-RD-SCH-TEXT-2 |
| Windows-1252 (`cp1252`) leaves the bytes 0x81, 0x8D, 0x8F, 0x90 and 0x9D undefined | S-0280 | INFERRED | H-A-RD-SCH-TEXT |
| Altium Designer 17 and later save ASCII schematics in UTF-8, older versions in the system code page | S-0133 | INFERRED | H-A-RD-SCH-ASCII |
| A reader trims spaces around values | S-0131 | INFERRED | H-A-RD-SCH-CASE |

## Storage

| fact | source | label | hypothesis |
|---|---|---|---|
| `Storage` starts with the property list `\|HEADER=Icon storage`; each later record has type 1 and holds one embedded file | S-0130 | CORPUS-VERIFIED (22 rows; 2026-10-05) | H-A-RD-SCH-STORAGE |
| An embedded-file record is the byte 0xD0, a one-byte name length, the name, a 4-byte little-endian size, then that many bytes of zlib data (with its zlib header) | S-0130 | CORPUS-VERIFIED (22 rows; 2026-10-05) | H-A-RD-SCH-STORAGE |
| An image (record 30) with `EMBEDIMAGE=T` names its embedded file by `FILENAME`, which may be a bare name or an absolute Windows path | S-0130 | INFERRED | H-A-RD-SCH-STORAGE |
| `zlib.decompressobj().decompress(data, max_length)` returns at most `max_length` bytes and keeps the rest of the input, so the output can be capped before it is produced | S-0281 | INFERRED | H-A-RD-SCH-STORAGE |

## Record ids

| fact | source | label | hypothesis |
|---|---|---|---|
| Record ids 1 to 18, 22, 25 to 34, 37, 39, 41 and 43 to 48 are the objects of the sections below, with the names S-0130 gives them | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| Records 215 to 218 (harness connector, entry, type, signal harness) are found in the `Additional` stream; 226 is a hyperlink | S-0130, S-0131, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| A text frame is record 28, and the same object is also seen as record 209; its property list may lack the leading `\|` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| Record 44 is owned by its component, 45 by the 44, 46 and 48 by the 45, 47 by the 46 | S-0130, S-0131, S-0144 | INFERRED | H-A-RD-SCH-OWNER |
| A parameter (record 41) without an owner index is a parameter of the sheet | S-0130, S-0187 | INFERRED | H-A-RD-SCH-OWNER |
| A component has `PARTCOUNT − 1` parts; a child's `OWNERPARTID` is its part, 0 for Part Zero (on every part), -1 for no part; its `OWNERPARTDISPLAYMODE` is a 0-based display mode below `DISPLAYMODECOUNT` | S-0130, S-0131, S-0154, S-0282 | INFERRED | H-A-RD-SCH-PARTS |
| A component has a Normal display mode and up to 255 alternates | S-0282 | INFERRED | H-A-RD-SCH-PARTS |

## Reader's choices

These are decisions of the reader, not format facts (design of change c0040, Decisions 4 to 14):

- **Lossless records.** A `Prop` is the key as written and the value's raw bytes. Typed attributes are views of
  the property list, so nothing is stored twice; `PropertyList.to_bytes()` gives back the parsed bytes.
- **Rebuilt streams.** `encode_stream` rebuilds every stream from property lists, pins and frames, never from a
  stored copy, so a parsing step that drops a byte fails the identity test.
- **Keys fold case.** Lookup upper-cases the key; the spelling stays. A repeated key keeps both fields; lookup
  takes the first and `PropertyList.duplicates` names it.
- **Text is decoded late.** The `%UTF8%` twin first, then UTF-8 for an ASCII file whose whole content is valid
  UTF-8, then the code page (`cp1252` by default, or a single-byte code page the caller passes). An undefined
  byte shows as U+FFFD with one `altium.sch.text-undecodable` warning; the bytes stay.
- **Exact lengths.** `SchLength.value` counts 1/100 000 unit; `nm()` rounds half to even and `exact` says
  whether it rounded. No float is used.
- **The file's frame.** No coordinate is flipped, rotated or moved.
- **A closed table of 43 classes.** Any other id is an `UnknownRecord` with its whole property list.
- **`MODELED` and `unknown_keys`.** Each class lists the keys it reads; every other key, and every modelled key
  whose value does not parse, is in `unknown_keys`.
- **Owners per index space.** `FileHeader`: an `OWNERINDEX` names an earlier record, and a record without one is
  at the sheet level. `Additional`: `OWNERINDEXADDITIONALLIST=T` means an index into `Additional`, an omitted
  index being 0. Library `Data`: a record belongs to the component unless it names an earlier record. A bad index
  leaves the record at the root with a warning; no record is dropped.
- **Owners are references.** A `RecordRef(stream, index)`; documents are flat tuples, and `walk` uses an explicit
  stack.
- **Parts and display modes are exposed, not resolved.** `children_of(component, part=, mode=)` filters;
  `shown_children` applies the component's own part and mode.
- **Counts never drive a loop past the record.** Items are read from the keys that exist. `LOCATIONCOUNT` adds
  the points whose keys are all left out (zero coordinates) only when it is at most the record's length in bytes;
  a larger count, or more items than the count, gives one `altium.sch.bad-value` warning.
- **Nothing is opened.** File names (`FILENAME`, `MODELDATAFILE<i>`, a sheet file name, a template file name)
  are text; embedded files are decompressed only by `EmbeddedFile.data(limit)`, with a cap of 64 MiB.
- **The census never holds a value.** It gives the header text as its kind and replaces a library's storage
  names by `<component>`.

## Every record

Every typed record models these keys (`SchRecord`); a record class adds its own.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `RECORD` | integer | 0 | `record_id` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `OWNERINDEX` | integer | 0 | `owner` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-OWNER |
| `OWNERPARTID` | integer | -1 | `owner_part` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-PARTS |
| `OWNERPARTDISPLAYMODE` | integer | 0 | `owner_display_mode` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-PARTS |
| `OWNERINDEXADDITIONALLIST` | boolean (`T`) | false | `owner` | S-0130, S-0131, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `INDEXINSHEET` | integer | 0 | `index_in_sheet` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-OWNER |
| `UNIQUEID` | text | "" | `unique_id` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-CASE |

### 1 `Component`

Record 1: a placed component (schematic) or the symbol's component record (library).

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LIBREFERENCE` | text | "" | `lib_reference` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `COMPONENTDESCRIPTION` | text | "" | `description` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `DESIGNITEMID` | text | "" | `design_item_id` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `SOURCELIBRARYNAME` | text | "" | `source_library` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LIBRARYPATH` | text | "" | `library_path` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `TARGETFILENAME` | text | "" | `target_file_name` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `PARTCOUNT` | integer | 2 (one part) | `part_count` | S-0130 | INFERRED | H-A-RD-SCH-PARTS |
| `CURRENTPARTID` | integer | 1 | `current_part` | S-0130 | INFERRED | H-A-RD-SCH-PARTS |
| `DISPLAYMODECOUNT` | integer | 1 | `display_mode_count` | S-0130 | INFERRED | H-A-RD-SCH-PARTS |
| `DISPLAYMODE` | integer | 0 | `display_mode` | S-0130 | INFERRED | H-A-RD-SCH-PARTS |
| `ORIENTATION` | quarter turns 0 to 3 | 0 | `orientation` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISMIRRORED` | boolean (`T`) | false | `mirrored` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `AREACOLOR` | colour | 0 (black) | `area_color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `COMPONENTKIND` | integer | 0 | `component_kind` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `PARTIDLOCKED` | boolean (`T`) | false | `part_id_locked` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `DESIGNATORLOCKED` | boolean (`T`) | false | `designator_locked` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `PINSMOVEABLE` | boolean (`T`) | false | `pins_moveable` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `SHEETPARTFILENAME` | text | "" | `sheet_part_file_name` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ALIASLIST` | text | "" | `alias_list` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `DATABASETABLENAME` | text | "" | `database_table_name` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `NOTUSEDBTABLENAME` | boolean (`T`) | false | `not_use_db_table_name` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 2 `Pin`

Record 2, a pin: a property list (``RECORD=2``) or a binary pin record (``binary`` is ``True``).

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `PINLENGTH` | length (units) | 0 | `length` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `PINLENGTH_FRAC` | integer (1/100 000 unit) | 0 | `length` | S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `NAME` | text | "" | `name` | S-0130 | INFERRED | H-A-RD-SCH-PIN |
| `DESIGNATOR` | text | "" | `designator` | S-0130 | INFERRED | H-A-RD-SCH-PIN |
| `DESCRIPTION` | text | "" | `description` | S-0130 | INFERRED | H-A-RD-SCH-PIN |
| `ELECTRICAL` | integer | 0 | `electrical` | S-0130 | INFERRED | H-A-RD-SCH-PIN |
| `PINCONGLOMERATE` | integer | 0 | `direction` | S-0130 | INFERRED | H-A-RD-SCH-PIN |
| `FORMALTYPE` | integer | 0 | `formal_type` | S-0130 | INFERRED | H-A-RD-SCH-PIN |
| `SYMBOL_INNEREDGE` | integer | 0 | `inner_edge` | S-0130 | INFERRED | H-A-RD-SCH-PIN |
| `SYMBOL_OUTEREDGE` | integer | 0 | `outer_edge` | S-0130 | INFERRED | H-A-RD-SCH-PIN |
| `SYMBOL_INNER` | integer | 0 | `inside` | S-0131 | INFERRED | H-A-RD-SCH-PIN |
| `SYMBOL_OUTER` | integer | 0 | `outside` | S-0131 | INFERRED | H-A-RD-SCH-PIN |
| `SWAPIDPIN` | text | "" | `swap_group` | S-0130 | INFERRED | H-A-RD-SCH-PIN |
| `SWAPIDPART` | text | "" | `part_and_sequence` | S-0130 | INFERRED | H-A-RD-SCH-PIN |
| `COLOR` | colour | 0 (black) | `color` | S-0131 | INFERRED | H-A-RD-SCH-PIN |

### 3 `IeeeSymbol`

Record 3: an IEEE symbol near a pin.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `SYMBOL` | integer | 0 | `symbol` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `SCALEFACTOR` | integer | 0 | `scale_factor` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ORIENTATION` | quarter turns 0 to 3 | 0 | `orientation` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISMIRRORED` | boolean (`T`) | false | `mirrored` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 4 `Label`

Record 4: a text note.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `TEXT` | text | "" | `text` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `FONTID` | integer | 0 | `font_id` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ORIENTATION` | quarter turns 0 to 3 | 0 | `orientation` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `JUSTIFICATION` | integer | 0 | `justification` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISMIRRORED` | boolean (`T`) | false | `mirrored` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `GRAPHICALLYLOCKED` | boolean (`T`) | false | `locked` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 5 `Bezier`

Record 5: a Bezier curve; its points are the control points.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LOCATIONCOUNT` | count | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `X<n>` | length (units) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `X<n>_FRAC` | integer (1/100 000 unit) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `Y<n>` | length (units) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `Y<n>_FRAC` | integer (1/100 000 unit) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 6 `Polyline`

Record 6: a polyline.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LOCATIONCOUNT` | count | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `X<n>` | length (units) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `X<n>_FRAC` | integer (1/100 000 unit) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `Y<n>` | length (units) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `Y<n>_FRAC` | integer (1/100 000 unit) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LINESTYLE` | integer | 0 | `line_style` | S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `STARTLINESHAPE` | integer | 0 | `start_line_shape` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ENDLINESHAPE` | integer | 0 | `end_line_shape` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LINESHAPESIZE` | integer | 0 | `line_shape_size` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 7 `Polygon`

Record 7: a polygon.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LOCATIONCOUNT` | count | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `X<n>` | length (units) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `X<n>_FRAC` | integer (1/100 000 unit) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `Y<n>` | length (units) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `Y<n>_FRAC` | integer (1/100 000 unit) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `AREACOLOR` | colour | 0 (black) | `area_color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISSOLID` | boolean (`T`) | false | `solid` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `IGNOREONLOAD` | boolean (`T`) | false | `ignore_on_load` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 8 `Ellipse`

Record 8: an ellipse.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `AREACOLOR` | colour | 0 (black) | `area_color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISSOLID` | boolean (`T`) | false | `solid` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `RADIUS` | length (units) | 0 | `radius` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `RADIUS_FRAC` | integer (1/100 000 unit) | 0 | `radius` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `SECONDARYRADIUS` | length (units) | 0 | `secondary_radius` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `SECONDARYRADIUS_FRAC` | integer (1/100 000 unit) | 0 | `secondary_radius` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |

### 9 `PieChart`

Record 9: a pie chart.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `AREACOLOR` | colour | 0 (black) | `area_color` | S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `ISSOLID` | boolean (`T`) | false | `solid` | S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `RADIUS` | length (units) | 0 | `radius` | S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `RADIUS_FRAC` | integer (1/100 000 unit) | 0 | `radius` | S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `STARTANGLE` | decimal (degrees) | 0 | `start_angle` | S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `ENDANGLE` | decimal (degrees) | 0 | `end_angle` | S-0131 | INFERRED | H-A-RD-SCH-CASE |

### 10 `RoundRectangle`

Record 10: a rectangle with round corners.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `AREACOLOR` | colour | 0 (black) | `area_color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISSOLID` | boolean (`T`) | false | `solid` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `CORNER.X` | length (units) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.X_FRAC` | integer (1/100 000 unit) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.Y` | length (units) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.Y_FRAC` | integer (1/100 000 unit) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNERXRADIUS` | length (units) | 0 | `corner_x_radius` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNERXRADIUS_FRAC` | integer (1/100 000 unit) | 0 | `corner_x_radius` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNERYRADIUS` | length (units) | 0 | `corner_y_radius` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNERYRADIUS_FRAC` | integer (1/100 000 unit) | 0 | `corner_y_radius` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |

### 11 `EllipticalArc`

Record 11: an elliptical arc.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `RADIUS` | length (units) | 0 | `radius` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `RADIUS_FRAC` | integer (1/100 000 unit) | 0 | `radius` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `SECONDARYRADIUS` | length (units) | 0 | `secondary_radius` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `SECONDARYRADIUS_FRAC` | integer (1/100 000 unit) | 0 | `secondary_radius` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `STARTANGLE` | decimal (degrees) | 0 | `start_angle` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ENDANGLE` | decimal (degrees) | 0 | `end_angle` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 12 `Arc`

Record 12: a circle or an arc; angles in microdegrees.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `RADIUS` | length (units) | 0 | `radius` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `RADIUS_FRAC` | integer (1/100 000 unit) | 0 | `radius` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `STARTANGLE` | decimal (degrees) | 0 | `start_angle` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ENDANGLE` | decimal (degrees) | 0 | `end_angle` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 13 `Line`

Record 13: a line from ``LOCATION`` to ``CORNER``.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `CORNER.X` | length (units) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.X_FRAC` | integer (1/100 000 unit) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.Y` | length (units) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.Y_FRAC` | integer (1/100 000 unit) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LINESTYLE` | integer | 0 | `line_style` | S-0131 | INFERRED | H-A-RD-SCH-CASE |

### 14 `Rectangle`

Record 14: a rectangle from ``LOCATION`` (bottom left) to ``CORNER`` (top right).

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `AREACOLOR` | colour | 0 (black) | `area_color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISSOLID` | boolean (`T`) | false | `solid` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `CORNER.X` | length (units) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.X_FRAC` | integer (1/100 000 unit) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.Y` | length (units) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.Y_FRAC` | integer (1/100 000 unit) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `TRANSPARENT` | boolean (`T`) | false | `transparent` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 15 `SheetSymbol`

Record 15: a sheet symbol; its location is its top-left corner.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `XSIZE` | length (units) | 0 | `x_size` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `XSIZE_FRAC` | integer (1/100 000 unit) | 0 | `x_size` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `YSIZE` | length (units) | 0 | `y_size` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `YSIZE_FRAC` | integer (1/100 000 unit) | 0 | `y_size` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |
| `AREACOLOR` | colour | 0 (black) | `area_color` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |
| `ISSOLID` | boolean (`T`) | false | `solid` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |
| `SYMBOLTYPE` | text | "" | `symbol_type` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |

### 16 `SheetEntry`

Record 16: a sheet entry of a sheet symbol.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `NAME` | text | "" | `name` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |
| `SIDE` | integer | 0 | `side` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |
| `DISTANCEFROMTOP` | length (units) | 0 | `distance` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `DISTANCEFROMTOP_FRAC1` | integer (1/100 000 unit) | 0 | `distance` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |
| `AREACOLOR` | colour | 0 (black) | `area_color` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |
| `TEXTCOLOR` | colour | 0 (black) | `text_color` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |
| `TEXTFONTID` | integer | 0 | `text_font_id` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |
| `TEXTSTYLE` | text | "" | `text_style` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |
| `IOTYPE` | integer | 0 | `io_type` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |
| `STYLE` | integer | 0 | `style` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |
| `ARROWKIND` | text | "" | `arrow_kind` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |
| `HARNESSTYPE` | text | "" | `harness_type` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-CASE |

### 17 `PowerPort`

Record 17: a power port; its location is the connection point.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `TEXT` | text | "" | `text` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `FONTID` | integer | 0 | `font_id` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ORIENTATION` | quarter turns 0 to 3 | 0 | `orientation` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `STYLE` | integer | 0 | `style` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `SHOWNETNAME` | boolean (`T`) | false | `show_net_name` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISCROSSSHEETCONNECTOR` | boolean (`T`) | false | `cross_sheet` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 18 `Port`

Record 18: a port.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `NAME` | text | "" | `name` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `WIDTH` | length (units) | 0 | `width` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `WIDTH_FRAC` | integer (1/100 000 unit) | 0 | `width` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `HEIGHT` | length (units) | 0 | `height` | S-0130, S-0187 | INFERRED | H-A-RD-SCH-FRAC |
| `HEIGHT_FRAC` | integer (1/100 000 unit) | 0 | `height` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `IOTYPE` | integer | 0 | `io_type` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `STYLE` | integer | 0 | `style` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ALIGNMENT` | integer | 0 | `alignment` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `HARNESSTYPE` | text | "" | `harness_type` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `AREACOLOR` | colour | 0 (black) | `area_color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `TEXTCOLOR` | colour | 0 (black) | `text_color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `FONTID` | integer | 0 | `font_id` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 22 `NoErc`

Record 22: a No ERC directive.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `ISACTIVE` | boolean (`T`) | false | `active` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `SUPPRESSALL` | boolean (`T`) | false | `suppress_all` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `SYMBOL` | text | "" | `symbol` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `ORIENTATION` | quarter turns 0 to 3 | 0 | `orientation` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-CASE |

### 25 `NetLabel`

Record 25: a net label; its location is the connection point.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `TEXT` | text | "" | `text` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `FONTID` | integer | 0 | `font_id` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ORIENTATION` | quarter turns 0 to 3 | 0 | `orientation` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 26 `Bus`

Record 26: a bus polyline.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LOCATIONCOUNT` | count | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `X<n>` | length (units) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `X<n>_FRAC` | integer (1/100 000 unit) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `Y<n>` | length (units) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `Y<n>_FRAC` | integer (1/100 000 unit) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |

### 27 `Wire`

Record 27: a wire, a polyline at sheet level.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LOCATIONCOUNT` | count | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `X<n>` | length (units) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `X<n>_FRAC` | integer (1/100 000 unit) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `Y<n>` | length (units) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `Y<n>_FRAC` | integer (1/100 000 unit) | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |

### 28 `TextFrame`

Record 28: a text box.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `TEXT` | text | "" | `text` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `FONTID` | integer | 0 | `font_id` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ORIENTATION` | quarter turns 0 to 3 | 0 | `orientation` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `CORNER.X` | length (units) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.X_FRAC` | integer (1/100 000 unit) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.Y` | length (units) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.Y_FRAC` | integer (1/100 000 unit) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `AREACOLOR` | colour | 0 (black) | `area_color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ALIGNMENT` | integer | 0 | `alignment` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `WORDWRAP` | boolean (`T`) | false | `word_wrap` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `SHOWBORDER` | boolean (`T`) | false | `show_border` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISSOLID` | boolean (`T`) | false | `solid` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `CLIPTORECT` | boolean (`T`) | false | `clip_to_rect` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `TEXTMARGIN` | length (units) | 0 | `text_margin` | S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `TEXTMARGIN_FRAC` | integer (1/100 000 unit) | 0 | `text_margin` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |

### 29 `Junction`

Record 29: a junction.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LOCKED` | boolean (`T`) | false | `locked` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 30 `Image`

Record 30: an image, linked by file name or embedded in ``Storage``.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `CORNER.X` | length (units) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.X_FRAC` | integer (1/100 000 unit) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.Y` | length (units) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.Y_FRAC` | integer (1/100 000 unit) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `EMBEDIMAGE` | boolean (`T`) | false | `embedded` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `FILENAME` | text | "" | `file_name` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `KEEPASPECT` | boolean (`T`) | false | `keep_aspect` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 31 `Sheet`

Record 31: the sheet, record 0 of a schematic document.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `FONTIDCOUNT` | count | 0 | `fonts` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `SIZE<i>` | integer | 0 | `fonts` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `FONTNAME<i>` | text | "" | `fonts` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ITALIC<i>` | boolean (`T`) | false | `fonts` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `BOLD<i>` | boolean (`T`) | false | `fonts` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `UNDERLINE<i>` | boolean (`T`) | false | `fonts` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ROTATION<i>` | integer | 0 | `fonts` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `SYSTEMFONT` | integer | 0 | `system_font` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `SHEETSTYLE` | integer | 0 | `sheet_style` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `USECUSTOMSHEET` | boolean (`T`) | false | `custom_size` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `CUSTOMX` | length (units) | 0 | `custom_size` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CUSTOMX_FRAC` | integer (1/100 000 unit) | 0 | `custom_size` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CUSTOMY` | length (units) | 0 | `custom_size` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CUSTOMY_FRAC` | integer (1/100 000 unit) | 0 | `custom_size` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `WORKSPACEORIENTATION` | integer | 0 | `portrait` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `TITLEBLOCKON` | boolean (`T`) | false | `title_block` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `BORDERON` | boolean (`T`) | false | `border` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `AREACOLOR` | colour | 0 (black) | `area_color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `SNAPGRIDON` | boolean (`T`) | false | `snap_grid_on` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `SNAPGRIDSIZE` | integer | 0 | `snap_grid_size` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `VISIBLEGRIDON` | boolean (`T`) | false | `visible_grid_on` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `VISIBLEGRIDSIZE` | integer | 0 | `visible_grid_size` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `HOTSPOTGRIDON` | boolean (`T`) | false | `hotspot_grid_on` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `HOTSPOTGRIDSIZE` | integer | 0 | `hotspot_grid_size` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `DISPLAY_UNIT` | integer | 0 | `display_unit` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `USEMBCS` | boolean (`T`) | false | `use_mbcs` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISBOC` | boolean (`T`) | false | `is_boc` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `SHEETNUMBERSPACESIZE` | integer | 0 | `sheet_number_space_size` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `CUSTOMXZONES` | integer | 0 | `custom_x_zones` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `CUSTOMYZONES` | integer | 0 | `custom_y_zones` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `CUSTOMMARGINWIDTH` | integer | 0 | `custom_margin_width` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `REFERENCEZONESON` | boolean (`T`) | false | `reference_zones_on` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `SHOWTEMPLATEGRAPHICS` | boolean (`T`) | false | `show_template_graphics` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `TEMPLATEFILENAME` | text | "" | `template_file_name` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 32 `SheetName`

Record 32: the sheet name of a sheet symbol.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `TEXT` | text | "" | `text` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `FONTID` | integer | 0 | `font_id` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ORIENTATION` | quarter turns 0 to 3 | 0 | `orientation` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISHIDDEN` | boolean (`T`) | false | `hidden` | S-0131 | INFERRED | H-A-RD-SCH-CASE |

### 33 `SheetFileName`

Record 33: the file name of a sheet symbol, as text; never opened.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `TEXT` | text | "" | `text` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `FONTID` | integer | 0 | `font_id` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ORIENTATION` | quarter turns 0 to 3 | 0 | `orientation` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISHIDDEN` | boolean (`T`) | false | `hidden` | S-0131 | INFERRED | H-A-RD-SCH-CASE |

### 34 `Designator`

Record 34: the designator of a component.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `TEXT` | text | "" | `text` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `FONTID` | integer | 0 | `font_id` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ORIENTATION` | quarter turns 0 to 3 | 0 | `orientation` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `NAME` | text | "" | `name` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISHIDDEN` | boolean (`T`) | false | `hidden` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISMIRRORED` | boolean (`T`) | false | `mirrored` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `READONLYSTATE` | integer | 0 | `read_only_state` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `OVERRIDENOTAUTOPOSITION` | boolean (`T`) | false | `override_not_auto_position` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 37 `BusEntry`

Record 37: a bus entry line from ``LOCATION`` to ``CORNER``.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `CORNER.X` | length (units) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.X_FRAC` | integer (1/100 000 unit) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.Y` | length (units) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `CORNER.Y_FRAC` | integer (1/100 000 unit) | 0 | `corner` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |

### 39 `Template`

Record 39: a sheet template, owning the template's lines and labels.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `FILENAME` | text | "" | `file_name` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISNOTACCESIBLE` | boolean (`T`) | false | `not_accessible` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 41 `Parameter`

Record 41: a parameter of its owner (a component, a directive, or the sheet when it has no owner).

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `TEXT` | text | "" | `text` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `FONTID` | integer | 0 | `font_id` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ORIENTATION` | quarter turns 0 to 3 | 0 | `orientation` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `NAME` | text | "" | `name` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISHIDDEN` | boolean (`T`) | false | `hidden` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISMIRRORED` | boolean (`T`) | false | `mirrored` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `READONLYSTATE` | integer | 0 | `read_only_state` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `SHOWNAME` | boolean (`T`) | false | `show_name` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `NOTAUTOPOSITION` | boolean (`T`) | false | `not_auto_position` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 43 `WarningSign`

Record 43: a directive (a warning sign, or a Parameter Set owning parameters).

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130, S-0187 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130, S-0187 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130, S-0187 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130, S-0187 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130, S-0187 | INFERRED | H-A-RD-SCH-CASE |
| `NAME` | text | "" | `name` | S-0130, S-0187 | INFERRED | H-A-RD-SCH-CASE |
| `ORIENTATION` | quarter turns 0 to 3 | 0 | `orientation` | S-0130, S-0187 | INFERRED | H-A-RD-SCH-CASE |

### 44 `ImplementationList`

Record 44: the list of a component's models.

No key beyond those of every record.

### 45 `Implementation`

Record 45: one model (a footprint, a simulation model …) of a component.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `MODELNAME` | text | "" | `model_name` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `MODELTYPE` | text | "" | `model_type` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `DESCRIPTION` | text | "" | `description` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `ISCURRENT` | boolean (`T`) | false | `is_current` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `USECOMPONENTLIBRARY` | boolean (`T`) | false | `use_component_library` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `DATAFILECOUNT` | count | 0 | `data_files` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `MODELDATAFILEENTITY<i>` | text | "" | `data_files` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `MODELDATAFILEKIND<i>` | text | "" | `data_files` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `MODELDATAFILE<i>` | text | "" | `data_files` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `INTEGRATEDMODEL` | boolean (`T`) | false | `integrated_model` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `DATABASEMODEL` | boolean (`T`) | false | `database_model` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `DATALINKSLOCKED` | boolean (`T`) | false | `data_links_locked` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `DATABASEDATALINKSLOCKED` | boolean (`T`) | false | `database_data_links_locked` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 46 `MapDefinerList`

Record 46: the pin-to-pad map list of an implementation.

No key beyond those of every record.

### 47 `MapDefiner`

Record 47: one map from a pin designator to model designators.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `DESINTF` | text | "" | `interface` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `DESIMPCOUNT` | count | 0 | `implementations` | S-0130 | INFERRED | H-A-RD-SCH-CASE |
| `DESIMP<i>` | text | "" | `implementations` | S-0130 | INFERRED | H-A-RD-SCH-CASE |

### 48 `ImplementationParameters`

Record 48: the parameter list of an implementation.

No key beyond those of every record.

### 215 `HarnessConnector`

Record 215: a harness connector; its location is its top-left corner.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `XSIZE` | length (units) | 0 | `x_size` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `XSIZE_FRAC` | integer (1/100 000 unit) | 0 | `x_size` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `YSIZE` | length (units) | 0 | `y_size` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `YSIZE_FRAC` | integer (1/100 000 unit) | 0 | `y_size` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `AREACOLOR` | colour | 0 (black) | `area_color` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `HARNESSCONNECTORSIDE` | integer | 0 | `side` | S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `SIDE` | integer | 0 | `side` | S-0131 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `PRIMARYCONNECTIONPOSITION` | integer | 0 | `primary_position` | S-0131, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |

### 216 `HarnessEntry`

Record 216: an entry of a harness connector.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `NAME` | text | "" | `name` | S-0131, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `SIDE` | integer | 0 | `side` | S-0131, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `DISTANCEFROMTOP` | length (units) | 0 | `distance` | S-0131, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `DISTANCEFROMTOP_FRAC1` | integer (1/100 000 unit) | 0 | `distance` | S-0131, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0131, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `AREACOLOR` | colour | 0 (black) | `area_color` | S-0131, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `TEXTCOLOR` | colour | 0 (black) | `text_color` | S-0131, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `TEXTFONTID` | integer | 0 | `text_font_id` | S-0131, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `TEXTSTYLE` | text | "" | `text_style` | S-0131, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |

### 217 `HarnessType`

Record 217: the type label of a harness connector.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `TEXT` | text | "" | `text` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `FONTID` | integer | 0 | `font_id` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `ORIENTATION` | quarter turns 0 to 3 | 0 | `orientation` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `ISHIDDEN` | boolean (`T`) | false | `hidden` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-ADDOWNER |

### 218 `SignalHarness`

Record 218: a signal harness line.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `COLOR` | colour | 0 (black) | `color` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `LINEWIDTH` | integer | 0 | `line_width` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `LOCATIONCOUNT` | count | 0 | `points` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-ADDOWNER |
| `X<n>` | length (units) | 0 | `points` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `X<n>_FRAC` | integer (1/100 000 unit) | 0 | `points` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `Y<n>` | length (units) | 0 | `points` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |
| `Y<n>_FRAC` | integer (1/100 000 unit) | 0 | `points` | S-0130, S-0187, S-0188 | INFERRED | H-A-RD-SCH-FRAC |

### 226 `Hyperlink`

Record 226: a hyperlink text; its address is text and never followed.

| key | type | default | attribute | source | label | hypothesis |
|---|---|---|---|---|---|---|
| `LOCATION.X` | length (units) | 0 | `location` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.X_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y` | length (units) | 0 | `location` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `LOCATION.Y_FRAC` | integer (1/100 000 unit) | 0 | `location` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-FRAC |
| `COLOR` | colour | 0 (black) | `color` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `TEXT` | text | "" | `text` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `FONTID` | integer | 0 | `font_id` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `ORIENTATION` | quarter turns 0 to 3 | 0 | `orientation` | S-0130, S-0131 | INFERRED | H-A-RD-SCH-CASE |
| `URL` | text | "" | `url` | S-0131 | INFERRED | H-A-RD-SCH-CASE |

## What the writer sets (change c0086)

The schematic writer (`fenolite.backends.altium.schdoc`, `schlib`, `ascii`) writes the records below since
change c0086. Each row is a fact the writer relies on; the keys themselves are those of the record tables
above. The observations of 2026-10-06 were made by reading the 16 cached corpus rows of use `altium-sch` with
`read.sch.read_schematic` and counting key names only; they are not a committed test, so their rows stay
`INFERRED`. The writer's own rows are `H-A-SCHX-*` (`docs/hypotheses.md`).

### Graphics the writer draws

| fact | source | label | hypothesis |
|---|---|---|---|
| A component's own graphics are children of its record 1 like its pins: a line is record 13 with `LOCATION` and `CORNER`, a rectangle record 14 with its bottom-left `LOCATION` and top-right `CORNER`, a closed polygon record 7 with `LOCATIONCOUNT` and `X<n>`, `Y<n>`, an ellipse record 8 with `LOCATION`, `RADIUS` and `SECONDARYRADIUS`; a circle is an ellipse of two equal radii | S-0130, S-0131 | INFERRED | H-A-SCHX-GRAPHICS |
| A shape is filled when it holds `ISSOLID=T`, with the colour of `AREACOLOR`; saved shapes hold `AREACOLOR` with and without `ISSOLID` (observed 2026-10-06: rectangles, polygons and ellipses of saved components) | S-0130, S-0187, S-0188 | INFERRED | H-A-SCHX-GRAPHICS |
| In saved components the keys stand in this order: record 13 `LOCATION.X`, `LOCATION.Y`, `CORNER.X`, `CORNER.Y`, `LINEWIDTH`, `COLOR`; record 7 `LINEWIDTH`, `COLOR`, `AREACOLOR`, `ISSOLID`, `LOCATIONCOUNT`, then `X1`, `X1_FRAC`, `Y1`, `Y1_FRAC` and so on; record 8 `LOCATION.X`, `LOCATION.Y`, `RADIUS`, `SECONDARYRADIUS`, `COLOR`, `AREACOLOR`, `ISSOLID`; `OWNERPARTID` follows the owner keys (observed 2026-10-06: 289 records 13, 23 records 7, 17 records 8) | S-0187, S-0188 | INFERRED | H-A-SCHX-GRAPHICS |
| A graphic coordinate that is no whole unit of 10 mil is written with its `_FRAC` key, in 1/100 000 unit (2.54 nm); saved polygons of components hold `X<n>_FRAC` and `Y<n>_FRAC` (observed 2026-10-06). The writer rounds half up to that step and leaves a `_FRAC` of zero out; the integer and its fraction have the same sign | S-0130, S-0131, S-0187 | INFERRED | H-A-SCHX-GRAPHICS |

Fenolite's choices: every graphic holds `LINEWIDTH=1`, `COLOR=128` and, when it can be filled,
`AREACOLOR=11599871`, the values of the synthesised rectangle; the line width and the colours of the source
symbol are not written. A rectangle of the source symbol holds `ISSOLID=T` only when the symbol fills it.
No `ISNOTACCESIBLE` and no `INDEXINSHEET` is written, as on every Fenolite record. An open circle is an
ellipse without `ISSOLID`.

### Directions, buses, parameters and text

| fact | source | label | hypothesis |
|---|---|---|---|
| `IOTYPE` of a port (record 18) and of a sheet entry (record 16) is 0 or absent for unspecified, 1 for output, 2 for input and 3 for bidirectional; saved ports and sheet entries hold 1, 2 and 3 (observed 2026-10-06: 14 ports and 30 sheet entries with the key, 43 and 161 without) | S-0130, S-0187, S-0188 | INFERRED | H-A-SCHX-DIR |
| A bus is record 26, a polyline with `LINEWIDTH`, `COLOR`, `LOCATIONCOUNT` and `X<n>`, `Y<n>`; a bus entry is record 37, a line from `LOCATION` to `CORNER`. No corpus sheet holds either, so their key order is the writer's own | S-0130, S-0131 | INFERRED | H-A-SCHX-BUS |
| A bus carries its members when a net label `<stem>[<a>..<b>]` lies on its line, and a port or a sheet entry of that text carries the bus off the sheet; the members are the nets that net labels `<stem><i>` name (`connectivity.md`, "Buses and harnesses") | S-0301, S-0185 | INFERRED | H-A-SCHX-BUS |
| A parameter of a component is record 41 owned by the component (`OWNERINDEX`), with `OWNERPARTID=-1`, `LOCATION`, `COLOR`, `FONTID`, `ISHIDDEN=T` when it is not shown, `TEXT` (the value), `NAME` and `UNIQUEID`, in that order in saved files (observed 2026-10-06: the most frequent key order of 2 619 owned parameters) | S-0130, S-0187, S-0188 | INFERRED | H-A-SCHX-READBACK |
| In saved files the `%UTF8%<key>` twin of a value stands right before the plain key (observed 2026-10-06: 734 twins, each before its plain key) | S-0130, S-0187, S-0188 | INFERRED | H-A-SCHX-TEXT |
| Windows-1252 encodes every character it holds as one byte; the characters U+0080 to U+009F are control codes in Unicode and are not printable text | S-0280 | INFERRED | H-A-SCHX-TEXT |

Fenolite's choices: a binary schematic is written in Windows-1252; a comment or a parameter value with a
character outside printable 7-bit ASCII is written as `%UTF8%TEXT` in UTF-8 and then `TEXT` in the code
page; every other text stays printable 7-bit ASCII. A bus line holds `LINEWIDTH=2` and the colour of a wire.
