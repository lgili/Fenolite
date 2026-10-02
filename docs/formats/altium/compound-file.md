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
| A stream may be empty: its directory entry gives the size 0. Such a stream needs no sector and no mini sector; Fenolite writes ENDOFCHAIN as its starting sector, a choice no section of the specification states for a size of 0 (change c0035, which needs empty `Data` streams; KiCad reads them in a local probe) | S-0145, S-0020 | INFERRED | H-A-PCB-DOC-OPEN |

## Fenolite's choices

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
