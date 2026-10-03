## ADDED Requirements

### Requirement: Compound file container
`backends.altium.cfb.write_compound(streams)` SHALL return the bytes of an MS-CFB version 3 compound file whose root storage holds exactly the given streams, in Fenolite's fixed layout (S-0145, `docs/formats/altium/compound-file.md`). `streams` is a sequence of `(name, data)` pairs. The function writes no file.
- Integers MUST be little-endian. The 512-byte header MUST hold the signature `D0 CF 11 E0 A1 B1 1A E1`, a zero header CLSID, minor version `0x003E`, major version `0x0003`, byte order `0xFFFE`, sector shift 9, mini sector shift 6, zero reserved bytes, 0 directory sectors, the FAT sector count, the first directory sector, transaction signature 0, mini stream cutoff 4096, the first mini FAT sector (ENDOFCHAIN when there is none), the mini FAT sector count, first DIFAT sector ENDOFCHAIN, 0 DIFAT sectors, and the FAT sector numbers in the header DIFAT, FREESECT after them.
- The sectors after the header MUST be, in this order: the FAT sectors, the directory sectors, the mini FAT sectors, the sectors of the mini stream, then each stream of 4096 bytes or more in the given order. Every chain MUST run through consecutive sectors and end with ENDOFCHAIN. FAT sectors MUST be marked FATSECT, and FAT entries past the last used sector FREESECT. The FAT sector count MUST cover the FAT's own sectors.
- A stream under 4096 bytes MUST be stored in the mini stream as consecutive 64-byte mini sectors, chained in the mini FAT. A stream of 4096 bytes or more MUST be stored in regular sectors. The unused tail of every last sector or mini sector MUST be zero.
- Directory: entry 0 MUST be `Root Entry` (type 5), whose starting sector and size name the mini stream (size = 64 × mini sectors in use; ENDOFCHAIN and 0 when no stream is small). Entries 1 … n MUST be the streams in the given order (type 2, child NOSTREAM). Unused entries MUST fill the last directory sector, all zero except the three links, which are NOSTREAM.
- Every entry MUST be black and carry a zero CLSID, zero state bits and zero timestamps. The root's child MUST be the top of a binary search tree of the streams under the MS-CFB order (shorter name first, then the upper-cased UTF-16 code units), built by taking the element at index `len // 2` of each sorted run as its top.
- A name MUST hold 1 to 31 characters without `/`, `\`, `:` or `!`, and names MUST be unique under that order; otherwise `ValueError`. An empty stream MUST also raise `ValueError`: a schematic never has one, and the fact page records no rule for its starting sector.
- When the FAT needs more than `cfb.MAX_FAT_SECTORS` sectors (109, the number the header can list), `write_compound` MUST raise `cfb.CompoundTooLarge` (a `ValueError`), because the writer writes no DIFAT sector.
- The bytes MUST depend only on `streams`.

#### Scenario: The two streams of a schematic
- **WHEN** `write_compound([("FileHeader", b"x" * 5000), ("Storage", b"y" * 25)])` is read with `tests/_cfb_read.py`
- **THEN** the reader reports no violation, `FileHeader` lies in 10 regular sectors, `Storage` in one mini sector, the root entry's size is 64, the root's child is `FileHeader` with `Storage` as its left sibling, and both streams read back byte for byte

#### Scenario: Cutoff boundary
- **WHEN** streams of 1, 64, 65, 4095, 4096 and 4097 bytes are written, one container each
- **THEN** each reads back byte for byte, the streams of 4095 bytes or less lie in the mini stream, and those of 4096 and 4097 bytes in regular sectors

#### Scenario: Several FAT sectors
- **WHEN** a stream of 200 000 bytes is written
- **THEN** the header lists 4 FAT sectors, each marked FATSECT, and the stream reads back byte for byte

#### Scenario: Too large
- **WHEN** a stream of 8 000 000 bytes is written
- **THEN** `CompoundTooLarge` is raised

#### Scenario: Invalid names
- **WHEN** `write_compound` gets a name of 32 characters, a name holding `/`, or the names `Storage` and `STORAGE`
- **THEN** each call raises `ValueError`

### Requirement: Binary schematic form
`backends.altium.binary.write_schdoc_binary(plan)` SHALL return the binary form of the schematic of `plan`: a compound file (`write_compound`) with the streams `FileHeader` and then `Storage`, and no other stream (S-0002, S-0130, S-0131, S-0142, S-0147). This requirement extends c0032's "ASCII schematic form": the records, their keys, their order and every value are those of `schdoc.schdoc_records(plan)`, and only the header text and the framing differ.
- `FileHeader` MUST be the header record `|HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0|WEIGHT=<n>`, with `<n>` the number of records after it, followed by every record of `schdoc_records(plan)`.
- Every record MUST be framed as a 32-bit little-endian word whose low 24 bits are the payload length and whose top byte is 0 (a property list), followed by the payload: the record's `ascii.format_record` text, then one NUL byte, counted in the length (S-0130, S-0147, S-0148). A payload of 65 536 bytes or more MUST raise `ValueError`.
- Payload text MUST follow the byte rules of "ASCII schematic form" and "Text the ASCII form cannot carry": printable 7-bit ASCII and no `|` inside a value. No CR or LF is written in a binary schematic.
- Pins MUST stay text records (`RECORD=2`), as in the ASCII form. No record of type 1 is written (S-0131, S-0142).
- `Storage` MUST be exactly one framed record with the payload `|HEADER=Icon storage` and its NUL, 25 bytes in all, with no weight key (S-0130, S-0131, S-0142).
- `project.write_project(design, *, name, project=True, issues=None, form=DEFAULT_FORM)` MUST return this form for `form="binary"` and c0032's ASCII bytes for `form="ascii"`. `project.SchematicForm` is `Literal["binary", "ascii"]` and `project.DEFAULT_FORM` is `"binary"`. `<name>.PrjPcb` is the same in both forms.

#### Scenario: Header record of the binary sample
- **WHEN** the `FileHeader` stream of the sample's binary schematic is de-framed
- **THEN** it holds 123 records, the first payload is `|HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0|WEIGHT=122` followed by a NUL, and the second starts with `|RECORD=31|`

#### Scenario: Same records in both forms
- **GIVEN** the sample's model with generic pins
- **WHEN** both forms are written and each binary payload after the header, without its NUL, is followed by CR LF
- **THEN** the joined payloads equal the ASCII file without its first line

#### Scenario: Storage stream
- **WHEN** the `Storage` stream of the sample's binary schematic is read
- **THEN** it is 25 bytes: the little-endian word 21, then `|HEADER=Icon storage` and one NUL

#### Scenario: Forms of write_project
- **WHEN** `write_project(model, name="altium_sample")` and `write_project(model, name="altium_sample", form="ascii")` are called on the sample's model with generic pins
- **THEN** the first `altium_sample.SchDoc` starts with the CFB signature, the second starts with `|HEADER=`, and both `altium_sample.PrjPcb` values are equal

### Requirement: Compound files read back
`tests/_cfb_read.py` SHALL read a compound file as test code that the product never imports, written from `docs/formats/altium/compound-file.md` and not from `cfb.py`. `read_compound(data)` returns every stream by its path (storage names and the stream name joined by `/`) and raises `CfbError` naming the first violated rule.
- It MUST check: the signature, header CLSID, versions, byte order, both shifts, the reserved bytes and the cutoff; that the header DIFAT lists exactly the sectors marked FATSECT; that every chain ends with ENDOFCHAIN, has no cycle, shares no sector and has `ceil(size / sector size)` sectors; that every stream under 4096 bytes is in the mini stream and every other in regular sectors; the root entry's name, type and size; the name-length field; zero CLSIDs and timestamps of streams; unused entries zero with NOSTREAM links; that the sibling tree is a binary search tree under the MS-CFB order and holds every stream once; and that the file holds exactly its sectors.
- `tests/unit/backends/altium/test_cfb_reader.py` MUST rebuild the worked example of MS-CFB section 3 from the field values of its tables (not from its hex dump) and read it, and MUST hold one negative control per rule.
- The de-framing helper MUST return the records of a `FileHeader` stream as lists of fields, and MUST reject a record without its final NUL or with a non-zero type byte.

#### Scenario: Spec example
- **WHEN** the reader reads the rebuilt MS-CFB example
- **THEN** it returns one stream, named `Stream 1` inside a storage, of 544 bytes, and the root entry's size is 576

#### Scenario: Broken chain caught
- **GIVEN** the sample's binary schematic with the FAT entry of one `FileHeader` sector set to point at the first FAT sector
- **WHEN** `read_compound` reads it
- **THEN** it raises `CfbError` naming the chain of `FileHeader`

#### Scenario: Round trip of the sample
- **WHEN** the sample's binary schematic is read by `read_compound` and its `FileHeader` is de-framed
- **THEN** the root holds exactly `FileHeader` and `Storage`, and the records after the header equal `schdoc_records(plan_sheet(model))` field for field
