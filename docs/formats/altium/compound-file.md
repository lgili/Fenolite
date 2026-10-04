# Compound file (MS-CFB) for the binary schematic and the schematic library

This page states, in Fenolite's own words, the rules of the Compound File Binary format that the binary
schematic writer `fenolite.backends.altium.cfb` (change c0033) relies on, and that the independent test
reader `tests/_cfb_read.py` checks. Change c0034 adds storages, which the schematic library
(`schematic-library.md`) needs: section "Storages".

- The source is Microsoft's normative specification [MS-CFB] (S-0145). Its notice allows copies made to
  develop implementations, and [MS-CFB] is a Covered Specification of the Open Specification Promise
  (S-0146). Sections 1.7 and 2 of [MS-CFB] are normative; the example of section 3 is informative.
- The writer and the test reader are written from this page only; no other implementation's code was
  read or copied. Every row was `INFERRED` until an Altium reader opened a written file (`H-A-SCHBIN-CFB`,
  `docs/evidence/altium-schematic.md`). The Altium 365 Viewer rendered the binary sample on 2026-10-02
  (step V1), so the rows carry that author-report label, except the DIFAT row: the sample's FAT fits
  in the header's 109 entries, so DIFAT sectors were never exercised and that row stays `INFERRED`.
- Python's standard library has no compound-file codec, so Fenolite writes the container with `struct`.
- `tests/unit/test_format_facts.py` checks the tables.

## Header and sectors

| fact | source | label | hypothesis |
|---|---|---|---|
| Every integer is little-endian | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| The file starts with a 512-byte header. Bytes 0-7 are the signature `D0 CF 11 E0 A1 B1 1A E1`; bytes 8-23, the header CLSID, are zero | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| Then: minor version (2 bytes, `0x003E`), major version (2 bytes, 3 for 512-byte sectors), byte order (2 bytes, `0xFFFE`), sector shift (2 bytes, 9 for version 3, so 512-byte sectors), mini sector shift (2 bytes, 6, so 64-byte mini sectors), six reserved zero bytes | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| Then, at offset 0x28, 4-byte fields: number of directory sectors (0 in version 3), number of FAT sectors, first directory sector, transaction signature (0), mini stream cutoff (4096), first mini FAT sector (ENDOFCHAIN when there is none), number of mini FAT sectors, first DIFAT sector (ENDOFCHAIN when there is none), number of DIFAT sectors | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| At offset 0x4C the header holds the first 109 entries of the DIFAT: the sector numbers of the FAT sectors in order, then FREESECT. A file whose FAT needs more than 109 sectors also needs DIFAT sectors | S-0145 | INFERRED | H-A-SCHBIN-CFB |
| Sector `N` starts at byte `(N + 1) × 512`: the header occupies the first sector's place. The file holds whole sectors after the header | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| Special sector numbers: `0xFFFFFFFA` is the largest regular sector number, `0xFFFFFFFC` DIFSECT, `0xFFFFFFFD` FATSECT, `0xFFFFFFFE` ENDOFCHAIN, `0xFFFFFFFF` FREESECT; in directory links, `0xFFFFFFFF` is NOSTREAM | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |

## FAT, chains and the mini stream

| fact | source | label | hypothesis |
|---|---|---|---|
| The FAT is an array of 4-byte entries, 128 per sector, one per sector of the file: entry `N` is the sector after `N` in its chain, or ENDOFCHAIN at the end of a chain. Sectors that hold the FAT are marked FATSECT; entries of sectors past the end of the file are FREESECT | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| The FAT sectors are exactly those that the DIFAT lists | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| Every chain ends with ENDOFCHAIN, has no cycle, and shares no sector with another chain; a stream's chain has exactly `ceil(size / sector size)` sectors | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| The directory, the mini FAT and the mini stream are chains of regular sectors; the directory starts at the header's first directory sector and the mini FAT at the header's first mini FAT sector | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| A stream smaller than the cutoff of 4096 bytes is stored in the mini stream, in 64-byte mini sectors; a stream of 4096 bytes or more is stored in regular sectors. A reader decides by the size alone | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| The mini FAT has the FAT's layout for mini sectors; mini sector `N` lies at byte `N × 64` of the mini stream. The mini stream's first sector and size are those of the root directory entry | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| The unused tail of a stream's last sector or mini sector should be zero | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| In the specification's worked example, a root entry of size 576 (nine mini sectors) holds one stream of 544 bytes: the root's size counts the whole mini sectors in use | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |

## Directory

| fact | source | label | hypothesis |
|---|---|---|---|
| The directory is an array of 128-byte entries, four per sector; an entry's index is its id. Entry 0 is the root storage | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| An entry holds: the name in UTF-16LE with a terminating NUL, in 64 bytes; the name length in bytes, NUL included (2 bytes); the object type (1 byte: 0 unused, 1 storage, 2 stream, 5 root); the colour (1 byte: 0 red, 1 black); the left sibling, right sibling and child ids (4 bytes each); the CLSID (16 bytes); state bits (4 bytes); creation and modification times (8 bytes each); the starting sector (4 bytes); the size (8 bytes, the high 4 zero in version 3) | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| A name holds at most 31 characters and none of `/`, `\`, `:` and `!` | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| The root entry is named `Root Entry` (name length 22) and has type 5; its starting sector and size are those of the mini stream (ENDOFCHAIN and 0 when no stream is small) | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| A stream entry has type 2 and child NOSTREAM; its starting sector and size give its data. Streams and the root may have a zero CLSID, zero state bits and zero times; streams must | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| Unused entries that fill the last directory sector are all zero except their three links, which are NOSTREAM | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| The children of a storage form one tree through the left and right sibling links, and the storage's child id names its top. It is a red-black tree under this order: a shorter name comes first; names of equal length compare their UTF-16 code units after upper-casing. Names must be unique under that order | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| A tree whose nodes are all black is valid, which makes it a plain binary search tree | S-0145 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |

## Storages

Rows added by change c0034. A schematic library holds one storage per component
(`schematic-library.md`); KiCad's library reader walks them (S-0131), so the rows that it exercises
also name `H-A-SCHLIB-KICAD`.

| fact | source | label | hypothesis |
|---|---|---|---|
| A storage is a directory entry of type 1. Like the root, it has a child id naming the top of the tree of its own children; its children may be streams and storages | S-0145 | INFERRED | H-A-SCHLIB-OPEN, H-A-SCHLIB-KICAD |
| A storage entry's starting sector and size are zero; it holds no data of its own | S-0145 | INFERRED | H-A-SCHLIB-OPEN, H-A-SCHLIB-KICAD |
| A storage may have a zero CLSID, zero state bits and zero creation and modification times | S-0145 | INFERRED | H-A-SCHLIB-OPEN |
| Names are unique among the children of one storage only: the same name may appear in two storages (each component storage of a library holds its own `Data`) | S-0145 | INFERRED | H-A-SCHLIB-OPEN, H-A-SCHLIB-KICAD |
| The order of the entries in the directory array is free: links, not positions, give the trees | S-0145 | INFERRED | H-A-SCHLIB-OPEN |
| A stream may be empty: its directory entry gives the size 0. Such a stream needs no sector and no mini sector; Fenolite writes ENDOFCHAIN as its starting sector, a choice no section of the specification states for a size of 0 (change c0035, which needs empty `Data` streams; KiCad reads them in a local probe) | S-0145, S-0020 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |

## Fenolite's writer choices

These are choices of the writer, not format facts (design of change c0033):

- version 3, one fixed layout: the header, then the FAT sectors, the directory, the mini FAT, the mini
  stream, then each large stream in the given order; every chain runs through consecutive sectors;
- the FAT sector count covers the FAT's own sectors; no DIFAT sector is written, and output that needs
  more than 109 FAT sectors is refused;
- every entry is black, with zero CLSIDs, state bits and times; the root's child is the top of a binary
  search tree built from the middle element (`len // 2`) of each sorted run; entries 1 … n are the
  streams in the given order;
- an empty stream is refused;
- storages (change c0034): entries are numbered in pre-order, the root's items in the given order with
  each storage followed at once by its own items; large streams take their sectors, and small streams
  their mini sectors, in that order; each storage's child is the top of the tree of its own items,
  built as for the root; a storage entry has start 0 and size 0; an empty storage is refused. A call
  with streams only gives the bytes of c0033's writer.

## Version 4

The reader accepts version 4 as well as the version 3 used by Fenolite's writer. Version 4 uses
4096-byte sectors (`sector shift` 12), with the same 64-byte mini sectors (`mini sector shift` 6).
The header sector is 4096 bytes: after the 512-byte header structure its remaining 3584 bytes are
reserved and zero. The directory-sector count in the header is used for version 4; a directory
sector contains 32 entries. A FAT sector has 1024 entries and a DIFAT sector has 1023 FAT-sector
numbers followed by its next-sector number. A version 4 directory size uses all 64 bits.

| fact | source | label | hypothesis |
|---|---|---|---|
| Version 4 has sector shift 12 (4096-byte sectors), 3584 zero bytes after the header, a directory-sector count, 1024 FAT entries per sector and 32 directory entries per sector | S-0145 | INFERRED | H-A-RD-CFB-V4 |
| A version 4 DIFAT sector has 1023 FAT-sector numbers and its final entry names the next DIFAT sector; the chain ends with ENDOFCHAIN | S-0145 | INFERRED | H-A-RD-CFB-V4 |
| The version 4 directory-entry size field is 64 bits | S-0145 | INFERRED | H-A-RD-CFB-V4 |

No public version 4 file is known; these facts are implemented and tested on authored containers only. `EVIDENCE_V4` remains `INFERRED`; the version 3 reader evidence is `CORPUS-VERIFIED` for the ten rows in this change.

## DIFAT sectors

The header's 109 DIFAT entries list FAT sector numbers first. If more FAT sectors are needed, the
header names the first DIFAT sector and gives the number of DIFAT sectors. Each DIFAT sector adds
127 FAT-sector numbers in version 3 (1023 in version 4), then the sector number of the next DIFAT
sector. ENDOFCHAIN ends that chain. The reader uses the header's FAT-sector count and preserves this
ordering when assembling the FAT.

| fact | source | label | hypothesis |
|---|---|---|---|
| The first 109 FAT-sector numbers are in the header DIFAT; later numbers follow the DIFAT chain, 127 per version 3 sector and 1023 per version 4 sector, with the next DIFAT sector in the final entry | S-0145 | INFERRED | H-A-RD-CFB-DIFAT |
| Altium's public `BMS.PcbDoc` (S-0188) has 154 FAT sectors and one DIFAT sector; the reader assembles them and its allocated-sector partition holds | S-0188 | CORPUS-VERIFIED | H-A-RD-CFB-DIFAT |

## Reading: tolerances and notes

These are reader rules, not properties of Fenolite's writer. Valid forms permitted by MS-CFB are
accepted without a note. A malformed field is reported as a note only when the bytes of every stream
remain unambiguous; an unsafe or ambiguous structure is an error. The version 3 high size bits are
ignored as MS-CFB recommends for readers that are not verifying files.

| fact | source | label | hypothesis |
|---|---|---|---|
| Accept DIFAT sectors and red or black directory entries; neither is written by Fenolite | S-0145 | CORPUS-VERIFIED | H-A-RD-CFB-CLEAN, H-A-RD-CFB-DIFAT |
| Accept a non-zero CLSID, state bits or modified time on the root, and a non-zero CLSID, state bits or creation/modification times on a storage | S-0145, S-0187 | INFERRED | H-A-RD-CFB-CLEAN |
| Accept FAT sectors marked free and directory entries of type 0 | S-0145 | INFERRED | H-A-RD-CFB-CLEAN |
| `cfb.note.minor-version`: note a minor version other than `0x003E` | S-0145 | INFERRED | H-A-RD-CFB-CLEAN |
| `cfb.note.header-fields`: note a non-zero header CLSID, reserved bytes or version 4 header padding; a version 3 directory-sector count; or a mini-FAT/DIFAT/directory sector count that differs from its chain | S-0145 | INFERRED | H-A-RD-CFB-CLEAN |
| `cfb.note.partial-sector`: note bytes after the header that do not make whole sectors; a chain cannot use the cut sector | S-0145 | INFERRED | H-A-RD-CFB-CLEAN |
| `cfb.note.fat-marks`: note a FAT/DIFAT sector not marked FATSECT/DIFSECT, or a FAT entry past end-of-file not marked FREESECT | S-0145 | INFERRED | H-A-RD-CFB-CLEAN |
| `cfb.note.high-size-bits`: note non-zero high 32 size bits in version 3 and read only the low 32 bits, as MS-CFB recommends | S-0145 | INFERRED | H-A-RD-CFB-CLEAN |
| `cfb.note.long-chain`: note sectors after the number needed for an entry's size; ignore those extra sectors | S-0145 | INFERRED | H-A-RD-CFB-CLEAN |
| `cfb.note.entry-fields`: note a stream CLSID, state bits or time; a storage start/size; root creation time or a root name other than `Root Entry`; or a directory colour other than red or black | S-0145 | INFERRED | H-A-RD-CFB-CLEAN |
| `cfb.note.tree-order`: note sibling links that do not form a search tree under the MS-CFB name order | S-0145 | INFERRED | H-A-RD-CFB-CLEAN |
| `cfb.note.orphan-entries`: note a storage or stream not reached from any storage; do not return it | S-0145 | INFERRED | H-A-RD-CFB-CLEAN |

The nine note codes form a closed table. At most one issue per code is returned; it reports the count
and first location. Strict mode raises the first note. No red-black balance rule is checked.

## Reading: limits

MS-CFB's version 3 size field bounds a single stream below 2 GiB. The Altium 365 Viewer accepts files
up to 200 MB. Neither value defines a safe parser limit, so Fenolite chooses limits that bound both
work and output. The reader checks file size before reading from disk, directory entry count before
building nodes, and nesting depth before walking storages. Each sector and mini sector may have one
owner only; chain walks use visited sets and explicit stacks rather than input-sized recursion.

| fact | source | label | hypothesis |
|---|---|---|---|
| Version 3 stores the high size bits as zero by rule; the specification says readers may ignore non-zero high bits when not verifying a file | S-0145 | INFERRED | H-A-RD-CFB-CLEAN |
| The largest file accepted by the Altium 365 Viewer is 200 MB | S-0149 | INFERRED | H-A-RD-CFB-CLEAN |

## What public files hold

A scratch census of 23 Altium-written files from eight repositories found the following. These are
observations used to set the test corpus and reader behavior; files are fetched for tests and never
committed.

| fact | source | label | hypothesis |
|---|---|---|---|
| All 23 files have major version 3, minor version `0x003E`, 512-byte sectors, a complete header and whole sectors | S-0170, S-0171, S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200 | INFERRED | H-A-RD-CFB-CORPUS |
| All 23 have zero header CLSID, reserved bytes and transaction signature; all have red and black directory entries | S-0170, S-0171, S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200 | INFERRED | H-A-RD-CFB-CLEAN |
| One file, S-0188 `BMS.PcbDoc`, is 10 078 208 bytes and uses 154 FAT sectors plus one DIFAT sector containing 45 FAT-sector numbers | S-0188 | INFERRED | H-A-RD-CFB-DIFAT |
| The largest file without DIFAT is S-0176 `foc.PcbDoc` at 6 730 752 bytes with 103 FAT sectors | S-0176 | INFERRED | H-A-RD-CFB-CORPUS |
| Seventeen files have a root modified time; the six schematics in S-0187 have a root CLSID; no file has a root creation time | S-0170, S-0171, S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200 | INFERRED | H-A-RD-CFB-CLEAN |
| Storages in the eleven files that have storages carry creation or modification times; they have no CLSID, state bits, or non-zero start and size | S-0170, S-0171, S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200 | INFERRED | H-A-RD-CFB-CLEAN |
| Streams have no CLSID, state bits or times; empty streams start at ENDOFCHAIN; no entry size exceeds 32 bits | S-0170, S-0171, S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200 | INFERRED | H-A-RD-CFB-CLEAN |
| All chains fit their sizes, share no sector, and every allocated sector has one owner; all sibling trees are ordered and names are at most 31 characters | S-0170, S-0171, S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200 | INFERRED | H-A-RD-CFB-CORPUS |
| No version 4 file was found in the census | S-0170, S-0171, S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200 | INFERRED | H-A-RD-CFB-V4 |

## Fenolite's choices

These choices are not format facts:

- `Limits(max_file_bytes=2**30, max_entries=2**18, max_depth=64)`; these are deliberately above the
  largest public file in this census while bounding allocation and traversal.
- All structural errors are checked eagerly by `open_compound`; only the requested stream's bytes
  are copied by `read(path)`. Chain runs are retained instead of one integer per sector.
- Paths are slash-joined stored names, looked up case-insensitively under the MS-CFB name order.
- A malformed field with unambiguous stream bytes becomes an issue note; ambiguous ownership,
  malformed chains and unsafe links are errors. Orphan entries are noted and omitted.
- No version 4 public sample is known. Version 4 support remains `INFERRED` until one is found.

The reader passed the public corpus test on all ten pinned rows from five repositories on 2026-10-04. All ten returned no notes; the nine rows without DIFAT matched the independent test reader byte for byte. The DIFAT row reported 154 FAT sectors and one DIFAT sector, and `kicad-cli` 10.0.6 imported it with exit 0. Counts only are recorded in `H-A-RD-CFB-CORPUS` and `H-A-RD-CFB-DIFAT` in `docs/hypotheses.md`.
