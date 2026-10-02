## ADDED Requirements

### Requirement: Compound file storages
`backends.altium.cfb.write_compound(entries)` SHALL also accept storages: each item of `entries` is a stream `(name, data)` or a `cfb.Storage(name, entries)`, whose `entries` follow the same rule at any depth. This requirement extends c0033's "Compound file container", whose rules hold for every storage as they hold for the root.
- `cfb.Storage` MUST be a frozen dataclass with the fields `name: str` and `entries: tuple[cfb.Entry, ...]`, where `cfb.Entry` is `tuple[str, bytes] | Storage`. Both are public and are the API that c0035 uses for PCB documents and libraries.
- Directory entries MUST be numbered in pre-order: the root's items in the given order, each storage followed at once by its own items. Large streams MUST take their sectors in that order, and small streams their mini sectors in that order.
- A storage entry MUST have type 1, black, a zero CLSID, zero state bits, zero timestamps, starting sector 0 and size 0. Its child MUST be the top of the binary search tree of its own items, built as for the root.
- Names MUST follow the rules of c0033 among siblings: the same name may appear in two different storages. A storage without items MUST raise `ValueError`.
- A call whose items are all streams MUST return the bytes that c0033's writer returns for them.
- `cfb.storage_from_paths(mapping)` MUST turn `{"A/B/Data": b"…", …}` into entries, storages and streams in first-seen order, and MUST raise `ValueError` when one path is both a stream and a storage.

#### Scenario: A library-shaped container
- **WHEN** `write_compound([("FileHeader", h), ("Storage", s), Storage("RES", (("Data", d),)), Storage("CAP", (("Data", e),))])` is read with `tests/_cfb_read.py`
- **THEN** the reader reports no violation and returns the paths `FileHeader`, `Storage`, `RES/Data` and `CAP/Data` with their bytes, and the entries are numbered root, `FileHeader`, `Storage`, `RES`, `RES/Data`, `CAP`, `CAP/Data`

#### Scenario: Streams-only calls keep their bytes
- **WHEN** the sample's binary schematic is built after this change
- **THEN** it equals `tests/data/altium/sample/binary/altium_sample.SchDoc` byte for byte

#### Scenario: Two levels and a large stream
- **WHEN** a storage `A` holds a storage `B` that holds a stream `Data` of 10 000 bytes, beside a root stream `X` of 10 bytes
- **THEN** `A/B/Data` lies in regular sectors, `X` in the mini stream, and both read back byte for byte

#### Scenario: Invalid storages
- **WHEN** `write_compound` gets an empty storage, or a storage holding the names `Data` and `DATA`
- **THEN** each call raises `ValueError`

### Requirement: Schematic library file
`backends.altium.schlib.write_schlib(symbols, *, library)` SHALL return the bytes of the schematic library file `library` holding the given `altsym.AltiumSymbol` values, as a compound file (S-0002, S-0131, S-0148, S-0150, S-0151, S-0152).
- The root MUST hold, in this order: the stream `FileHeader`, the stream `Storage`, the stream `SectionKeys` only when some symbol has a section key ("Library and storage names"), then one storage per symbol, named by its storage name and holding exactly one stream `Data`. Symbols MUST be in the MS-CFB order of their storage names.
- `FileHeader` MUST be one property record, framed as in c0033's "Binary schematic form", with the fields `HEADER=Protel for Windows - Schematic Library Editor Binary File Version 5.0`, `WEIGHT=<w>`, `FONTIDCOUNT=1`, `SIZE1=10`, `FONTNAME1=Times New Roman`, `COMPCOUNT=<n>`, then for each symbol i from 0 `LIBREF<i>=<lib ref>`, `COMPDESCR<i>=<description>` (only when not empty) and `PARTCOUNT<i>=<parts + 1>`. `<w>` is the number of records in all `Data` streams plus 1 (S-0150). Nothing follows the record (`H-A-SCHLIB-OPEN`).
- `Storage` MUST be c0033's `binary.storage_stream()`.
- `SectionKeys` MUST be one property record `KEYCOUNT=<k>`, then for each keyed symbol `LIBREF<i>=<lib ref>` and `SECTIONKEY<i>=<storage name>`, i from 0 in symbol order (S-0150, S-0151).
- No other stream is written: no `PinFrac`, `PinWideText`, `PinTextData` or `PinSymbolLineWidth` (S-0150, S-0152).
- The bytes MUST depend only on `symbols` and `library`.

#### Scenario: Library of the sample
- **WHEN** the sample's `FenoliteSample.SchLib` is read with `tests/_cfb_read.py`
- **THEN** its paths are `FileHeader`, `Storage` and `<name>/Data` for `CAP`, `DRV4`, `HDR2`, `LDO3`, `LED` and `RES`, its header record holds `COMPCOUNT=6`, and no `SectionKeys` stream exists

#### Scenario: Header keys
- **WHEN** the `FileHeader` of the sample's library is de-framed
- **THEN** it holds one record, which starts with `|HEADER=Protel for Windows - Schematic Library Editor Binary File Version 5.0|WEIGHT=`, and whose `LIBREF<i>` values equal the storage names in order

### Requirement: Library component records
The `Data` stream of a symbol SHALL be a sequence of framed records owned by its first record, the component, in this order: the component, the pins, one rectangle per part, the designator, the comment and, when the symbol has a footprint, the footprint chain (S-0131, S-0150).
- Text records MUST be framed as in c0033's "Binary schematic form", and MUST carry no `OWNERINDEX`: every record after the first belongs to it (`H-A-SCHLIB-OPEN`). Coordinates MUST be symbol-relative, in units of 10 mil, with Y upwards, and MUST carry no `_FRAC` key.
- Component: `RECORD=1`, `LIBREFERENCE`, `COMPONENTDESCRIPTION` (only when not empty), `PARTCOUNT=<parts + 1>`, `DISPLAYMODECOUNT=1`, `OWNERPARTID=-1`, `CURRENTPARTID=1`, `UNIQUEID=<project.unique_id("schlib:<library>:<lib ref>")>`, `DESIGNITEMID=<lib ref>`, `COLOR=128`, `AREACOLOR=11599871`.
- Rectangle of part k: `RECORD=14`, `OWNERPARTID=<k>`, `LOCATION.X`, `LOCATION.Y` (bottom-left), `CORNER.X`, `CORNER.Y` (top-right), `LINEWIDTH=1`, `COLOR=128`, `AREACOLOR=11599871`, `ISSOLID=T`.
- Designator: `RECORD=34`, `OWNERPARTID=-1`, `NAME=Designator`, `TEXT=<prefix>?`, the location 100 mil above part 1's top-left corner, `FONTID=1`, `COLOR=8388608`. Comment: `RECORD=41` with the same keys, `NAME=Comment`, `TEXT=<comment>`, 200 mil below part 1's bottom-left corner.
- Footprint chain: `RECORD=44`; `RECORD=45` with the keys and values of c0032's chain ("Designator, comment and links"); `RECORD=46`; `RECORD=48`; none with `OWNERINDEX`. The data file index stays 0-based as in c0032 (`H-A-SCHLIB-IMPLIDX`).
- Pins MUST be binary records ("Binary pin record"), ordered by part, then by designator in natural order.

#### Scenario: Records of RES
- **WHEN** the `RES/Data` stream of the sample's library is de-framed
- **THEN** it holds, in order, a `RECORD=1` with `LIBREFERENCE=RES` and `PARTCOUNT=2`, two binary pins `1` and `2`, one `RECORD=14` with `OWNERPARTID=1`, a `RECORD=34` with `TEXT=R?`, a `RECORD=41` with `NAME=Comment`, and the records 44, 45 (`MODELNAME=R0603`), 46 and 48, and no field `OWNERINDEX`

### Requirement: Binary pin record
`backends.altium.schlib.pin_record(pin)` SHALL return one framed binary record for an `altsym.AltiumPin`: a 32-bit little-endian word `(1 << 24) | <payload length>`, then the payload, without a NUL (S-0131, S-0148, S-0150).
- The payload MUST be, little-endian: record id 2 (4 bytes); byte 0; `OWNERPARTID` (2 bytes, signed); display mode 0 (1 byte); the inner-edge, outer-edge, inside and outside symbol codes (1 byte each); the description as a short string; `FORMALTYPE` 1 (1 byte); the electrical type (1 byte); `PINCONGLOMERATE` (1 byte); the pin length, `LOCATION.X` and `LOCATION.Y` of the body end (2 bytes each, signed, 10-mil units); the colour 0 (4 bytes); then the short strings name, designator, swap group, part-and-sequence and default value.
- A short string MUST be one length byte and that many ASCII bytes. Description, swap group, part-and-sequence and default value MUST be empty.
- `PINCONGLOMERATE` MUST be the direction (0 right, 1 up, 2 left, 3 down, from the body end to the hot end), plus 0x04 when hidden, 0x08 when the name is shown, 0x10 when the number is shown.
- A name or designator over 255 bytes, a value outside the signed 16-bit range, or a code outside 0 … 255 MUST raise `ValueError`.
- That two public implementations agree on this layout is recorded in the fact page; that Altium shows such pins as written is `H-A-SCHLIB-PIN`. The `FORMALTYPE` byte is 1 here and 0 in S-0150; the page records the difference.

#### Scenario: Worked pin
- **WHEN** `pin_record` is called on pin `1` named `IN`, passive, leftwards, name and number shown, length 20 units, body end (-30, 10) units, part 1
- **THEN** it returns the hex bytes `22000001` `02000000` `00` `0100` `00` `00000000` `00` `01` `04` `1a` `1400` `e2ff` `0a00` `00000000` `02494e` `0131` `00` `00` `00`

#### Scenario: Too long a name
- **WHEN** `pin_record` is called on a pin whose name has 256 characters
- **THEN** it raises `ValueError`

### Requirement: Library symbols from KiCad symbols
`backends.altium.altsym.from_symbol_def(symbol, *, lib_ref, footprint, issues)` SHALL map a resolved `SymbolDef` to an `AltiumSymbol` (S-0131 for the importer's reverse mapping, `docs/formats/altium/schematic-library.md`).
- Body style 1 and common pins (body style 0) MUST be kept. Pins of other body styles and pin alternates MUST be dropped with one `altium.symbol-simplified` info per symbol. The symbol's own graphics are not in the model; each part gets a synthesised rectangle.
- Parts MUST be the units 1 … `unit_count`. A pin of unit 0 MUST get `OWNERPARTID=0` (Part Zero); others keep their unit.
- A pin's hot end is `SymbolPin.position` and its rotation gives the direction: 0 → 2 (left), 90 → 3 (down), 180 → 0 (right), 270 → 1 (up). The body end MUST be the hot end moved by the length against the direction. Positions and lengths MUST be multiples of 254 000 nm (10 mil); otherwise `ValueError`, which the build reports as `altium.symbol-off-grid` first.
- Electrical type MUST map: input 0, bidirectional 1, output 2, open_collector 3, passive 4, tri_state 5, open_emitter 6, power_in 7. `power_out` gives 7, and `free`, `unspecified` and `no_connect` give 4, each with an `altium.pin-lossy` warning.
- Shape MUST map to edge codes: line none; inverted outer edge 1; clock inner edge 3; inverted_clock outer edge 1 and inner edge 3; input_low outer edge 4; output_low outer edge 17; clock_low inner edge 3 and outer edge 4. `edge_clock_high` and `non_logic` give none with an `altium.pin-lossy` warning.
- The name MUST be shown unless `pin_names_hidden` or the name is empty or `~`, the number unless `pin_numbers_hidden`. A hidden pin MUST set 0x04. A KiCad overbar `~{…}` MUST be written as each character followed by `\`.
- Part k's rectangle MUST be the bounding box of the body ends of its pins and the Part Zero pins; a side shorter than 200 mil MUST grow to 200 mil around its centre, rounded outwards to 10 mil. A part without pins gets the square from (-100, -100) to (100, 100) mil.
- The designator prefix MUST be the symbol's `Reference` property, or `U` when it is empty. The comment MUST be the `Value` property, or the symbol name. The description MUST be the `Description` property.

#### Scenario: Resistor turned upright
- **GIVEN** a symbol with pins `1` at (0, 150) mil rotation 270 and `2` at (0, -150) mil rotation 90, both 50 mil long
- **WHEN** it is mapped
- **THEN** pin `1` has direction 1 and body end (0, 100) mil, pin `2` direction 3 and body end (0, -100) mil, and the rectangle is (-100, -100) to (100, 100) mil

#### Scenario: Dual unit with common power pins
- **GIVEN** a symbol with units 1 and 2 of three pins each and two power_in pins of unit 0
- **WHEN** it is mapped
- **THEN** the symbol has 2 parts, `PARTCOUNT` is 3, the power pins have part 0 and electrical type 7, and each part's rectangle encloses its own pins and the power pins

#### Scenario: Off-grid pin refused
- **GIVEN** a pin at x = 1.27 mm + 1 µm
- **WHEN** it is mapped
- **THEN** `ValueError` is raised, naming the pin

### Requirement: Generic library symbols
`backends.altium.altsym.from_generic(body, *, lib_ref, prefix, comment, footprint)` SHALL give c0032's generic body (`symbols.GenericSymbol`) as an `AltiumSymbol` of one part whose origin is the body's top-left corner.
- The rectangle MUST be (0, -height) to (width, 0); a left pin of row r MUST have its body end at (0, -100 · (r + 1)) mil and direction 2, a right pin at (width, -100 · (r + 1)) mil and direction 0; every pin is passive, 200 mil long, part 1, and shows its name only when the name differs from the designator.
- The prefix MUST be the leading letters of the first ref in component-path order among the parts that share the lib id, or `U` when there are none. The footprint MUST be the parts' common footprint, or none when they differ.
- Placed at a component's location, this symbol MUST give exactly the pins and rectangle that c0032 writes for the generic body.

#### Scenario: Generic resistor of the sample
- **WHEN** the generic symbol of `FenoliteSample.SchLib:RES` is built
- **THEN** it has pins `1` (left, body end (0, -100) mil) and `2` (right, body end (600, -100) mil), the rectangle (0, -200) to (600, 0) mil, the prefix `R` and the footprint `FenoliteSample.PcbLib:R0603`

### Requirement: Library and storage names
`backends.altium.project.schlib_name(lib_id, *, design)` and `project.storage_name(lib_ref)` SHALL give the library file of a lib id and the storage name of a symbol.
- `schlib_name` MUST return the lib id's library part when it ends with `.SchLib` in any letter case (an Altium link), and `<design>.SchLib` otherwise (a KiCad lib id), where `<design>` is the design name. All KiCad symbols of a design therefore share one library, as c0035 puts all KiCad footprints in `<design>.PcbLib`.
- `storage_name` MUST return the lib ref when it holds 1 to 31 characters and none of `/ \ : !`. Otherwise it MUST return a section key: `/` replaced by `_`, cut to 31 characters (S-0150, S-0152); a key that still holds `\`, `:` or `!` MUST raise `ValueError`. That Altium finds a symbol by its section key is `H-A-SCHLIB-SECTIONKEY`.
- Within one library, two symbols whose storage names are equal under the MS-CFB order MUST raise `ValueError` in `write_schlib`; the build reports `altium.symbol-name-collision` first.

#### Scenario: Names
- **WHEN** `schlib_name("Device:R", design="board")`, `schlib_name("My.schlib:R", design="board")` and `storage_name("A" * 40)` are called
- **THEN** they return `board.SchLib`, `My.schlib` and 31 `A` characters

### Requirement: Schematic libraries read back
`tests/_altium_read.py` SHALL read a schematic library, as test code that the product never imports, written from `docs/formats/altium/schematic-library.md`: `read_schlib(data)` returns, per storage, the de-framed records, with every binary pin decoded field by field.
- It MUST check: the header text; `COMPCOUNT` and the `LIBREF<i>` keys against the storages; `WEIGHT`; that each storage holds `Data` and nothing else; that the first record is `RECORD=1`; that the stream is consumed exactly; and that every binary record has record id 2 and all five short strings.
- `tests/_cfb_read.py` MUST check that a storage entry has starting sector 0 and size 0.
- `tests/unit/backends/altium/test_schlib.py` MUST hold one negative control per check.

#### Scenario: Round trip of a mapped symbol
- **WHEN** the dual-unit symbol of "Library symbols from KiCad symbols" is written and read back
- **THEN** every pin field equals the mapped `AltiumPin`, and the records follow the order of "Library component records"

#### Scenario: Stray byte caught
- **GIVEN** the sample's library with one byte appended to `RES/Data`, rebuilt with `write_compound`
- **WHEN** `read_schlib` reads it
- **THEN** it fails and names `RES/Data`

### Requirement: Schematic library oracle
`tests/kicad/altium/test_schlib_oracle.py` SHALL convert written libraries with `kicad-cli sym upgrade <X>.SchLib -o <Y>.kicad_sym`, read the result with `backends.kicad.sym.read_symbol_library`, and compare it with the source (S-0131, S-0153).
- For the library of `examples/altium_kicad/`, each symbol MUST have the source `SymbolDef`'s unit count and, per pin of body style 1 or 0: number; name after the overbar mapping; electrical type after the lossy mapping; hot-end position; rotation; length; unit; hidden. The `Reference` and `Footprint` properties MUST be the prefix and the footprint name.
- For the sample's library, each symbol MUST have the generic pins.
- Negative controls, written by the test from the writer's records: another header text, a `Data` that does not start with the component, a stray byte at the end of `Data`, and a pin without its last two strings. Each MUST make `kicad-cli` exit non-zero. A storage without `Data` crashes kicad-cli 10.0.6 and MUST NOT be run.
- The test MUST skip without kicad-cli, and fail when `FENOLITE_REQUIRE` lists `kicad`. It runs in the `kicad-10` and `kicad-9` jobs. When kicad-cli 9 cannot read a library that 10.0.6 reads, the test MUST be marked expected-to-fail on major 9, with the observed message recorded on the fact page (`H-A-SCHLIB-KICAD9`).
- A pass on 10.0.6 gives `ORACLE-VERIFIED(kicad-cli)` to the facts that KiCad's importer reads (`H-A-SCHLIB-KICAD`), and to no Altium-only fact.

#### Scenario: Example library converts
- **WHEN** `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/altium/test_schlib_oracle.py` runs with kicad-cli 10.0.6
- **THEN** it passes: every symbol of the example converts with the source's pins and units, and every negative control exits non-zero

### Requirement: Schematic bodies from the library symbol
The schematic SHALL draw each component from the `AltiumSymbol` of its lib id, placed with the symbol's origin at the component's `LOCATION`, so that the schematic and the library hold the same pins at the same places (`H-A-SCHLIB-UPDATE`, `H-A-SCHLIB-SCHDOC`).
- A symbol of one part MUST give one component record with `CURRENTPARTID=1`, its rectangle and its pins as text records `RECORD=2`, with the keys of "Generic component bodies", plus `SYMBOL_INNEREDGE` and `SYMBOL_OUTEREDGE` when not 0, and the electrical type and direction of the symbol.
- A symbol of n > 1 parts MUST give n component records, parts 1 … n, each with `CURRENTPARTID=<k>`, `PARTCOUNT=<n + 1>`, the ref as designator, the comment, the footprint chain and every rectangle and pin of the symbol with its `OWNERPARTID`. Part 1's `UNIQUEID` is `unique_id(<component id>)`; part k > 1 gets `unique_id("<component id>#<k>")` (`H-A-SCHLIB-MULTIPART`).
- Stubs MUST be drawn for the pins of part k on part k, and for Part Zero pins on part 1 only ("Connectivity on the sheet").
- A design whose lib ids are all Altium links MUST give the same schematic bytes as c0033, in both forms.

#### Scenario: Sample schematic unchanged
- **WHEN** the sample is built in both forms after this change
- **THEN** both schematics equal the committed `altium_sample.SchDoc` files byte for byte

#### Scenario: Dual unit placed twice
- **WHEN** the example's `U1` (two units and common power pins) is written
- **THEN** it gives two component records with designator `U1`, `CURRENTPARTID` 1 and 2 and different unique ids, and the power pins get stubs on part 1 only

#### Scenario: Pins at the library positions
- **WHEN** the example's schematic is read back with `tests/_altium_read.py`
- **THEN** each pin's location minus its component's location equals the pin's body end in the example's library, and the nets read back equal the model's nets

## MODIFIED Requirements

### Requirement: Altium writer package
`fenolite.backends.altium` SHALL provide `project.write_project(design, *, name, project=True, issues=None, form=DEFAULT_FORM, symbols=None) -> dict[str, bytes]`, which returns `<name>.SchDoc`, one `<library>.SchLib` per library that the components' lib ids name ("Schematic library file") and, when `project` is true, `<name>.PrjPcb`, for a model `Design` whose components hold their pins, and writes no file. `symbols` maps each lib id of the design to its `altsym.AltiumSymbol`; a lib id missing from it, or `symbols=None`, gets its generic symbol ("Generic library symbols").
- The package MUST import only `fenolite.core` and `fenolite.model`, and MUST NOT open a file, start a process or read the environment. It MUST NOT resolve a library: `lens.altium` passes the resolved symbols in.
- It MUST NOT be registered in `fenolite.backends.registry`.
- `src/fenolite/backends/altium/PROVENANCE.md` MUST hold the provenance table of `docs/provenance.md`, one row per fact area, each citing `docs/evidence/sources.md` ids.
- Every format fact the package relies on MUST be a row of a page under `docs/formats/altium/` (`schematic-ascii.md`, `project.md`, `compound-file.md`, `schematic-binary.md` or `schematic-library.md`), with its source, its label and an `H-A-SCH-*`, `H-A-SCHBIN-*`, `H-A-SCHLIB-*` or `H-A-PRJ-*` hypothesis.
- `write_project` MUST raise `ValueError` for a net member whose pin the component does not hold, and for a text that `ascii.text_problem` refuses; the build checks both first (`altium-build`, "Altium build issue codes").

#### Scenario: Files of the sample
- **GIVEN** the model of `examples/altium_sample/design.py` with generic pins
- **WHEN** `write_project(model, name="altium_sample")` and `write_project(model, name="altium_sample", project=False)` are called
- **THEN** the first returns the keys `altium_sample.PrjPcb`, `altium_sample.SchDoc` and `FenoliteSample.SchLib`, and the second only `altium_sample.SchDoc` and `FenoliteSample.SchLib`

#### Scenario: Not a registered backend
- **WHEN** `registry.all_backends()` is called after `fenolite.backends.altium.project` is imported
- **THEN** no backend is named `altium`

#### Scenario: Layering and provenance
- **WHEN** `uv run pytest tests/unit/test_import_graph.py tests/unit/test_provenance.py` runs
- **THEN** it passes, with `backends.altium` checked against the `backends.<x>` row and its `PROVENANCE.md` table found

### Requirement: ASCII schematic form
`backends.altium.ascii.encode_records(records)` SHALL write the ASCII form of a schematic (S-0002, S-0130, S-0131, S-0133):
- The first line MUST be the header record `|HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0|WEIGHT=<n>`, where `<n>` is the number of records after it.
- Every other record MUST be one line of fields `|KEY=VALUE`, starting with `|` and without a trailing `|`, with its keys in the order this capability lists them. A boolean MUST be written `T` and only when true.
- Every line, the last one included, MUST end with CR LF (S-0142, S-0143; `H-A-SCH-LINEEND`).
- The bytes MUST be printable 7-bit ASCII apart from the line ends.
- Records after the header are numbered from 0 in file order. Record 0 MUST be the sheet record `RECORD=31`. Every `OWNERINDEX` MUST name an earlier record, so every owner precedes its children.
- A line MUST NOT end with `|>`, and the file MUST hold no second header and no embedded file.
- Lengths are integers in units of 10 mil, and X grows rightwards and Y upwards from the sheet's bottom-left corner (S-0130, S-0131). The writer works on a 10-mil grid (library pins may sit on a 50-mil grid; component origins stay on the 100-mil grid of "Deterministic sheet layout"), so it MUST write no `_FRAC` key.

#### Scenario: Header and first record of the sample
- **WHEN** the sample's `altium_sample.SchDoc` is split into lines
- **THEN** it has 123 lines, the first is `|HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0|WEIGHT=122`, and the second starts with `|RECORD=31|`

#### Scenario: Line ends and bytes
- **WHEN** the bytes of the sample's schematic are read
- **THEN** every line ends with CR LF, every other byte lies between 0x20 and 0x7E, and no line ends with `|>`

#### Scenario: Units
- **WHEN** `coord_fields("LOCATION", 1000, 500)` is called with a point 1000 mil right of and 500 mil above the sheet origin
- **THEN** it returns the fields `LOCATION.X=100` and `LOCATION.Y=50`, `coord_fields("LOCATION", 1050, 500)` returns `LOCATION.X=105`, and a length that is not a multiple of 10 mil raises `ValueError`

### Requirement: Generic component bodies
Each component whose lib id is an Altium link (`altium-build`, "Altium symbol sources") SHALL be written as a component record with one rectangle and one pin per pin of `Component.pins`; `lens.altium.generic_pins` gives every component of one lib id one pin per designator that the nets name on any component of that lib id, so that components sharing a lib id share one body, which is also their library component ("Generic library symbols") (`altium-build`, "Altium build outputs").
- Pins MUST be in natural order: designators split into runs of digits and other characters, digit runs compared as integers and before letters, so `1`, `2`, `10`, `A1`, `B` is the order. The first ⌈n/2⌉ pins go on the left edge from top to bottom, the rest on the right edge from top to bottom.
- Geometry (mils, Fenolite choices): pins 200 long and 100 apart, the first 100 below the top edge; body width `max(600, 100 · ⌈(100 + 2 · 70 · L) / 100⌉)` for the longest shown pin name of `L` characters; body height `100 · (rows + 1)`, at least 200.
- Component record: `RECORD=1`, `LIBREFERENCE`, `DESIGNITEMID`, `SOURCELIBRARYNAME`, `PARTCOUNT=2`, `DISPLAYMODECOUNT=1`, `CURRENTPARTID=1`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the body's top-left corner), `UNIQUEID`, `COLOR=128`, `AREACOLOR=11599871`; no orientation and no mirror (S-0130, S-0131, S-0137).
- Rectangle record: `RECORD=14`, `OWNERINDEX`, `OWNERPARTID=1`, `LOCATION.X`, `LOCATION.Y` (bottom-left), `CORNER.X`, `CORNER.Y` (top-right), `LINEWIDTH=1`, `COLOR=128`, `AREACOLOR=11599871`, `ISSOLID=T` (S-0130, S-0131).
- Pin record: `RECORD=2`, `OWNERINDEX`, `OWNERPARTID=1`, `FORMALTYPE=1`, `ELECTRICAL=4` (passive), `PINCONGLOMERATE`, `PINLENGTH=20`, `LOCATION.X`, `LOCATION.Y`, `NAME`, `DESIGNATOR` (S-0130, S-0131).
  - `LOCATION` MUST be the pin's body end on the body edge. `PINCONGLOMERATE` MUST be the direction (2 leftwards for left pins, 0 rightwards for right pins) plus 0x10 (number shown), plus 0x08 (name shown) only when the name differs from the designator.
  - The electrical hot end is `LOCATION` plus `PINLENGTH` in the pin's direction, away from the body (S-0130, S-0131, S-0140).
- Children carry absolute sheet coordinates (S-0131).

#### Scenario: Natural order
- **WHEN** `generic_symbol([("10", "10"), ("B", "B"), ("2", "2"), ("A1", "A1"), ("1", "1")])` is called
- **THEN** its pins are in the order `1`, `2`, `10`, `A1`, `B`, with `1`, `2` and `10` on the left and `A1` and `B` on the right

#### Scenario: Four-pin part of the sample
- **WHEN** the records of the sample's `U2` are read
- **THEN** its rectangle is 600 × 300 mil, pins `1` and `2` are on its left edge with `PINCONGLOMERATE=18`, pins `3` and `4` are on its right edge with `PINCONGLOMERATE=16`, every pin has `PINLENGTH=20`, `ELECTRICAL=4` and `OWNERINDEX` equal to the record number of `U2`

#### Scenario: A part without connected pins
- **GIVEN** a component that no net names, and whose lib id no other component uses
- **WHEN** it is written
- **THEN** it has a component record, a 600 × 200 mil rectangle, a designator and a comment, and no pin record

#### Scenario: Components sharing a lib id share a body
- **GIVEN** a variant where `R1` uses pins `1` and `2` and `R2`, with the same lib id, uses only pin `1`
- **WHEN** it is written
- **THEN** both components have pins `1` and `2` and the same rectangle, and only pin `1` of `R2` has a stub

### Requirement: Designator, comment and links
Each component SHALL carry its designator, its comment, its library link and, when it has one, its footprint link.
- Designator record: `RECORD=34`, `OWNERINDEX`, `OWNERPARTID=-1`, `NAME=Designator`, `TEXT=<ref>`, `LOCATION.X`, `LOCATION.Y` (100 mil above the body's top-left corner), `FONTID=1`, `COLOR=8388608` (S-0130, S-0131).
- Comment record: `RECORD=41` with the same keys, `NAME=Comment` and `TEXT=<value>`, 200 mil below the body's bottom-left corner. An empty value MUST give the symbol name as the comment (S-0130, S-0137).
- Library link: `lib_id` `<library>:<name>` MUST give `LIBREFERENCE=<name>`, `DESIGNITEMID=<name>` and `SOURCELIBRARYNAME=<project.schlib_name(lib_id, design=<design name>)>`: the library itself for an Altium link, and `<design name>.SchLib` for a KiCad lib id, the library file that the build writes (S-0002, S-0130, S-0137; "Library and storage names"). That "Tools » Update From Libraries" follows these keys is `H-A-SCH-UPDATE`.
- Footprint link: `footprint` `<library>:<name>` MUST give, after the component's other children, `RECORD=44` (`OWNERINDEX` = the component), then `RECORD=45` (`OWNERINDEX` = the record 44, `MODELNAME=<name>`, `MODELTYPE=PCBLIB`, `DATAFILECOUNT=1`, `MODELDATAFILEENTITY0=<name>`, `MODELDATAFILEKIND0=PCBLIB`, `MODELDATAFILE0=<library>`, `ISCURRENT=T`), then `RECORD=46` and `RECORD=48`, each with `OWNERINDEX` = the record 45 (S-0130, S-0131, S-0135, S-0142, S-0144). That Altium reads `MODELDATAFILE0` as the "Library name" mode is `H-A-SCH-LINK`.
- A component without footprint MUST have no record 44, 45, 46 or 48.

#### Scenario: Links of the sample's J1
- **WHEN** the records of the sample's `J1` are read
- **THEN** its component record holds `LIBREFERENCE=HDR2`, `DESIGNITEMID=HDR2` and `SOURCELIBRARYNAME=FenoliteSample.SchLib`, and its record 45 holds `MODELNAME=HDR1X2`, `MODELTYPE=PCBLIB`, `DATAFILECOUNT=1`, `MODELDATAFILEENTITY0=HDR1X2`, `MODELDATAFILEKIND0=PCBLIB`, `MODELDATAFILE0=FenoliteSample.PcbLib` and `ISCURRENT=T`

#### Scenario: Ownership chain
- **WHEN** the owners of the sample's records 44, 45, 46 and 48 are followed
- **THEN** every record 44 is owned by a component, every record 45 by the record 44 just before it, and every record 46 and 48 by that record 45

#### Scenario: Empty value and no footprint
- **GIVEN** a part `X1` with `lib_id="L.SchLib:SYM"`, no value and no footprint
- **WHEN** it is written
- **THEN** its comment record holds `TEXT=SYM`, and no record 44 is owned by it

#### Scenario: Links of a KiCad lib id
- **GIVEN** a part with `lib_id="Device:R"` in a design named `board`
- **WHEN** it is written
- **THEN** its component record holds `LIBREFERENCE=R`, `DESIGNITEMID=R` and `SOURCELIBRARYNAME=board.SchLib`

### Requirement: Connectivity on the sheet
Every pin drawn on a placed part, which is each pin of that part and, on part 1 only, each Part Zero pin ("Schematic bodies from the library symbol"), SHALL get one wire stub from its hot end outward in the pin's direction, ended by a power port when its net is a member of a `power` interface, and carrying a net label otherwise (S-0130, S-0131, S-0140).
- Wire record: `RECORD=27`, `OWNERPARTID=-1`, `LINEWIDTH=1`, `COLOR=8388608`, `LOCATIONCOUNT=2`, `X1`, `Y1` (the pin's hot end), `X2`, `Y2` (the stub's outer end). Stubs of left and right pins are horizontal, stubs of up and down pins vertical: 200 mil long for a port, `max(300, 100 · ⌈(70 · L + 150) / 100⌉)` mil for a label of `L` characters.
- Net label record: `RECORD=25`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y`, `TEXT=<net name>`, `FONTID=1`, `COLOR=8388608`. Its location, the label's lower-left hotspot, MUST lie on its stub: at the outer end for a left pin, 100 mil from the hot end for a right pin (S-0140). On a vertical stub the record MUST add `ORIENTATION=1` after `LOCATION.Y`, and its location MUST be the outer end for a down pin and 100 mil from the hot end for an up pin, so the text runs upwards along the stub (S-0130, S-0131).
- Power port record: `RECORD=17`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the stub's outer end), `STYLE`, `ORIENTATION` (2 for a left pin, 0 for a right pin, 1 for an up pin, 3 for a down pin, pointing away from the body), `SHOWNETNAME=T`, `TEXT=<net name>`, `FONTID=1`, `COLOR=8388608`. `STYLE` MUST be 4 (power ground) for a net that is only ever the `lv` member of power interfaces, and 2 (bar) otherwise (S-0131, S-0140).
- A net MUST NOT get both labels and ports. No junction record is written: no two stubs touch.
- Sheet-level records follow every component block: for each component in path order, each of its parts in order and each pin drawn on that part, by part and then in natural order, the stub, then its label or port.

#### Scenario: Ports and labels of the sample
- **WHEN** the sample's schematic is written
- **THEN** it has 19 wire records, 13 power ports (6 with `STYLE=4` and `TEXT=GND`, 3 with `STYLE=2` and `TEXT=VIN`, 4 with `STYLE=2` and `TEXT=+5V`), 6 net labels (two each for `EN`, `LED_DRV` and `LED_A`), and no `RECORD=29`

#### Scenario: A net that is high in one supply and low in another
- **GIVEN** a variant with `Power(VMID, GND)` and `Power(VCC, VMID)`
- **WHEN** it is written
- **THEN** the ports of `VMID` have `STYLE=2` and the ports of `GND` have `STYLE=4`

#### Scenario: Label on its stub
- **WHEN** the label of the sample's `U2` pin 3 and the stub of that pin are read
- **THEN** the label's location lies on the stub, 100 mil from the pin's hot end, and not on any other wire or pin end

#### Scenario: Vertical stubs of the example
- **WHEN** the schematic of `examples/altium_kicad/design.py` is written
- **THEN** every up or down pin has a vertical stub, each of its labels carries `ORIENTATION=1` and lies on that stub, and the nets read back equal the model's nets

### Requirement: Deterministic sheet layout
`backends.altium.layout.layout_sheet(parts)` SHALL place components in component-path order, in rows of cells, on the first sheet that holds them.
- A component of n parts takes n consecutive cells, one per part in part order. A cell holds the part's body, its pins, stubs, labels, ports and texts, plus 200 mil on each side; a port takes 100 mil plus 70 mil per character of its net name beyond its stub (Fenolite estimates for the 10-point font).
- Cells MUST be packed left to right and top to bottom inside the drawing area less 500 mil on each side; a row is as high as its tallest cell. Every cell corner and component origin MUST be a multiple of 100 mil, and every written point a multiple of 10 mil.
- The sheet MUST be the first of A4, A3, A2, A1 and A0 whose drawing area holds the packing. Otherwise the sheet MUST be custom, with the A0 width (or the widest cell plus the margins, when larger) and the needed height rounded up to 1000 mil, and `write_project` MUST append the warning `altium.sheet-custom`.
- `SheetPlan.size.name` MUST be the sheet name (`A4` … `A0`, or `custom`); `lens.altium` reports it as `result.sheet`.

#### Scenario: Sample on A4
- **WHEN** the sample is laid out
- **THEN** the sheet is `A4`, no two cells overlap, every written point lies inside the drawing area less 500 mil, and the components appear left to right and top to bottom in the order `J1`, `R2`, `U2`, `led/D1`, `led/R1`, `power/C1`, `power/C2`, `power/U1`

#### Scenario: Larger sheet when needed
- **GIVEN** a variant with 120 two-pin parts on two nets
- **WHEN** it is laid out
- **THEN** the sheet is the first ISO size whose drawing area holds the packing, and the packing does not fit the size before it

#### Scenario: Custom sheet
- **GIVEN** a variant whose packing exceeds the A0 drawing area
- **WHEN** `write_project` runs with an `issues` list
- **THEN** the sheet record uses `USECUSTOMSHEET=T`, and `issues` holds one `altium.sheet-custom` warning

### Requirement: Project file
`backends.altium.prjpcb.write_prjpcb(*, schematic, libraries=())` SHALL return the bytes of the lines `[Design]`, `Version=1.0`, an empty line, `[Document1]` and `DocumentPath=<schematic>`, then for each library, i from 2, an empty line, `[Document<i>]` and `DocumentPath=<library>`, each line ending with CR LF, in 7-bit ASCII and without a byte-order mark (S-0132, S-0134, S-0142, S-0143).
- `<schematic>` and each `<library>` are bare file names, because the files sit beside the project (S-0132, S-0142). Libraries MUST be in the MS-CFB order of their names (`cfb.name_key`), and a name holding `/` or `\` MUST raise `ValueError`.
- That Altium takes a listed `.SchLib` as a project library, which "Tools » Update From Libraries" searches, is `H-A-SCHLIB-PRJ`.
- That Altium opens this file, takes defaults for every other key, and needs no byte-order mark is `H-A-PRJ-OPEN`.

#### Scenario: Project of the sample
- **WHEN** `write_prjpcb(schematic="altium_sample.SchDoc")` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=altium_sample.SchDoc\r\n"`

#### Scenario: Project with a library
- **WHEN** `write_prjpcb(schematic="altium_sample.SchDoc", libraries=("FenoliteSample.SchLib",))` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=altium_sample.SchDoc\r\n\r\n[Document2]\r\nDocumentPath=FenoliteSample.SchLib\r\n"`
