## MODIFIED Requirements

### Requirement: Designator, comment and links
Each component SHALL carry its designator, its comment, its library link and, when it has one, its footprint link.
- Designator record: `RECORD=34`, `OWNERINDEX`, `OWNERPARTID=-1`, `NAME=Designator`, `TEXT=<ref>`, `LOCATION.X`, `LOCATION.Y` (100 mil above the body's top-left corner), `FONTID=1`, `COLOR=8388608` (S-0130, S-0131).
- Comment record: `RECORD=41` with the same keys, `NAME=Comment` and `TEXT=<value>`, 200 mil below the body's bottom-left corner. An empty value MUST give the symbol name as the comment (S-0130, S-0137).
- Library link: `lib_id` `<library>:<name>` MUST give `LIBREFERENCE=<name>`, `DESIGNITEMID=<name>` and `SOURCELIBRARYNAME=<project.schlib_name(lib_id, design=<design name>)>`: the library itself for an Altium link, and `<design name>.SchLib` for a KiCad lib id, the library file that the build writes (S-0002, S-0130, S-0137; "Library and storage names"). That "Tools » Update From Libraries" follows these keys is `H-A-SCH-UPDATE`.
- Footprint link: the component's footprint link `<library>:<name>` (its `footprint`, or the symbol's `Footprint` property, `altium-build` "Altium symbol sources") MUST give, after the component's other children, `RECORD=44` (`OWNERINDEX` = the component), then `RECORD=45` (`OWNERINDEX` = the record 44, `MODELNAME=<name>`, `MODELTYPE=PCBLIB`, `DATAFILECOUNT=1`, `MODELDATAFILEENTITY0=<name>`, `MODELDATAFILEKIND0=PCBLIB`, `MODELDATAFILE0=<project.pcblib_name(link, design=<design name>)>`, `ISCURRENT=T`), then `RECORD=46` and `RECORD=48`, each with `OWNERINDEX` = the record 45 (S-0130, S-0131, S-0135, S-0142, S-0144). That Altium reads `MODELDATAFILE0` as the "Library name" mode is `H-A-SCH-LINK`.
- `MODELDATAFILE0` MUST follow the link's form, not the build's outcome: the library itself for an Altium link (`.PcbLib` in any letter case), and `<design name>.PcbLib` for a KiCad footprint link, whether or not that footprint is written (`altium-pcb-writer`, "PCB library name"). The schematic bytes therefore never depend on the content of a footprint library.
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

#### Scenario: Links of a KiCad footprint
- **GIVEN** the part `R1` of `examples/blink_2layer/design.py`, with `footprint="Mini:Mini_R_0603"`, in the design `blink`
- **WHEN** it is written
- **THEN** its record 45 holds `MODELNAME=Mini_R_0603`, `MODELDATAFILEENTITY0=Mini_R_0603` and `MODELDATAFILE0=blink.PcbLib`

#### Scenario: Unresolved KiCad footprint keeps its link
- **GIVEN** a part with `footprint="Nowhere:X"` in a design named `board`, whose library does not resolve
- **WHEN** it is written
- **THEN** its record 45 holds `MODELNAME=X` and `MODELDATAFILE0=board.PcbLib`

### Requirement: Project file
`backends.altium.prjpcb.write_prjpcb(*, schematic, pcb=None, libraries=())` SHALL return the bytes of the lines `[Design]`, `Version=1.0`, an empty line, `[Document1]` and `DocumentPath=<schematic>`; then, when `pcb` is given, an empty line, `[Document2]` and `DocumentPath=<pcb>`; then for each library, i from the next free number, an empty line, `[Document<i>]` and `DocumentPath=<library>`, each line ending with CR LF, in 7-bit ASCII and without a byte-order mark (S-0132, S-0134, S-0142, S-0143).
- `<schematic>`, `<pcb>` and each `<library>` are bare file names, because the files sit beside the project (S-0132, S-0142). Libraries, schematic (`.SchLib`) and PCB (`.PcbLib`) alike, MUST be in the MS-CFB order of their names (`cfb.name_key`), and a name holding `/` or `\` MUST raise `ValueError`.
- That Altium takes a listed `.SchLib` as a project library, which "Tools » Update From Libraries" searches, is `H-A-SCHLIB-PRJ`. That it shows a listed `.PcbLib` and `.PcbDoc` as project documents, and that the change order finds footprints in the listed `.PcbLib`, are `H-A-PCB-PRJ` and `H-A-PCB-ECO`.
- That Altium opens this file, takes defaults for every other key, and needs no byte-order mark is `H-A-PRJ-OPEN`.

#### Scenario: Project of the sample
- **WHEN** `write_prjpcb(schematic="altium_sample.SchDoc")` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=altium_sample.SchDoc\r\n"`

#### Scenario: Project with a library
- **WHEN** `write_prjpcb(schematic="altium_sample.SchDoc", libraries=("FenoliteSample.SchLib",))` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=altium_sample.SchDoc\r\n\r\n[Document2]\r\nDocumentPath=FenoliteSample.SchLib\r\n"`

#### Scenario: Project with a PCB document and two libraries
- **WHEN** `write_prjpcb(schematic="blink.SchDoc", pcb="blink.PcbDoc", libraries=("blink.SchLib", "blink.PcbLib"))` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=blink.SchDoc\r\n\r\n[Document2]\r\nDocumentPath=blink.PcbDoc\r\n\r\n[Document3]\r\nDocumentPath=blink.PcbLib\r\n\r\n[Document4]\r\nDocumentPath=blink.SchLib\r\n"`

### Requirement: Compound file container
`backends.altium.cfb.write_compound(streams)` SHALL return the bytes of an MS-CFB version 3 compound file whose root storage holds exactly the given streams, in Fenolite's fixed layout (S-0145, `docs/formats/altium/compound-file.md`). `streams` is a sequence of `(name, data)` pairs. The function writes no file. c0034's "Compound file storages" extends it to storages.
- Integers MUST be little-endian. The 512-byte header MUST hold the signature `D0 CF 11 E0 A1 B1 1A E1`, a zero header CLSID, minor version `0x003E`, major version `0x0003`, byte order `0xFFFE`, sector shift 9, mini sector shift 6, zero reserved bytes, 0 directory sectors, the FAT sector count, the first directory sector, transaction signature 0, mini stream cutoff 4096, the first mini FAT sector (ENDOFCHAIN when there is none), the mini FAT sector count, first DIFAT sector ENDOFCHAIN, 0 DIFAT sectors, and the FAT sector numbers in the header DIFAT, FREESECT after them.
- The sectors after the header MUST be, in this order: the FAT sectors, the directory sectors, the mini FAT sectors, the sectors of the mini stream, then each stream of 4096 bytes or more in the given order. Every chain MUST run through consecutive sectors and end with ENDOFCHAIN. FAT sectors MUST be marked FATSECT, and FAT entries past the last used sector FREESECT. The FAT sector count MUST cover the FAT's own sectors.
- A stream under 4096 bytes MUST be stored in the mini stream as consecutive 64-byte mini sectors, chained in the mini FAT. A stream of 4096 bytes or more MUST be stored in regular sectors. The unused tail of every last sector or mini sector MUST be zero.
- Directory: entry 0 MUST be `Root Entry` (type 5), whose starting sector and size name the mini stream (size = 64 × mini sectors in use; ENDOFCHAIN and 0 when no stream is small). Entries 1 … n MUST be the streams in the given order (type 2, child NOSTREAM). Unused entries MUST fill the last directory sector, all zero except the three links, which are NOSTREAM.
- Every entry MUST be black and carry a zero CLSID, zero state bits and zero timestamps. The root's child MUST be the top of a binary search tree of the streams under the MS-CFB order (shorter name first, then the upper-cased UTF-16 code units), built by taking the element at index `len // 2` of each sorted run as its top.
- A name MUST hold 1 to 31 characters without `/`, `\`, `:` or `!`, and names MUST be unique under that order; otherwise `ValueError`. An empty stream (0 bytes) MUST be written with a directory entry of size 0 and starting sector ENDOFCHAIN, and MUST take no sector and no mini sector; the PCB library and document need empty `Data` streams (S-0145, `compound-file.md`; that Altium accepts it is `H-A-PCB-DOC-OPEN`).
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

#### Scenario: Empty streams
- **WHEN** `write_compound([("Header", b"\x00\x00\x00\x00"), ("Data", b"")])` is read with `tests/_cfb_read.py`
- **THEN** the reader reports no violation, `Data` has size 0 and starting sector ENDOFCHAIN, the mini stream holds one mini sector, and both streams read back byte for byte

#### Scenario: Schematic bytes unchanged
- **WHEN** the sample's binary schematic is built after this change
- **THEN** it equals `tests/data/altium/sample/binary/altium_sample.SchDoc` byte for byte
