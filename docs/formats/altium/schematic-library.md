# Altium schematic library (`.SchLib`)

This page states, in Fenolite's own words, what `fenolite.backends.altium.schlib` and
`fenolite.backends.altium.altsym` (change c0034) rely on to write an Altium schematic library, and what
the test reader `tests/_altium_read.py` (`read_schlib`) checks. The container is described in
`compound-file.md`; the record framing and the text records are those of `schematic-binary.md` and
`schematic-ascii.md`.

- Sources are listed in `docs/evidence/sources.md`. The GPL sources (S-0131, S-0148, S-0151, S-0153)
  were read for facts only; nothing was transcribed or followed.
- S-0150 is AltiumSharp **version 1 only**, at commit `afe796434b6d2110c745c90abe44a6ddf64f5bca`
  (2023-07-21, Apache-2.0 `LICENSE` at that commit). Every row resting on it says so. AltiumSharp
  version 2 is not used: its comments cite a non-public decompilation folder (LEGAL.md P1). Facts that
  only version 2 gave are listed in the section of facts awaiting a permitted source and are not used.
- The code is written from this page only, never from the sources' code or the format researcher's
  scratch probe.
- `kicad-cli sym upgrade` converts a `.SchLib` into a KiCad library through KiCad's Altium importer
  (S-0153). Rows that the importer reads name `H-A-SCHLIB-KICAD` and become `ORACLE-VERIFIED(kicad-cli)`
  once `tests/kicad/altium/test_schlib_oracle.py` passes. Rows that only Altium reads stay `INFERRED`
  until the maintainer's Part L report (`docs/evidence/altium-schematic.md`).
- The round trip passed on kicad-cli 10.0.6 and on 9.0.9 (pinned image, local run) on 2026-10-02. Rows
  whose only hypothesis is `H-A-SCHLIB-KICAD` and that the test exercises now carry
  `ORACLE-VERIFIED(kicad-cli)`; rows that also name an Altium-only hypothesis, and observations the test
  does not repeat, stay `INFERRED`. No Part L report exists, so every Altium-only row is pending. The free Altium 365
  Viewer refuses library files (maintainer report of 2026-10-02), so it checks nothing here.
- Units: lengths in a library are in units of 10 mil (S-0131, `schematic-ascii.md`).

## Container

| fact | source | label | hypothesis |
|---|---|---|---|
| A schematic library is a compound file. Its root holds the streams `FileHeader` and `Storage`, optionally `SectionKeys`, and one storage per component | S-0002, S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0152 | INFERRED | H-A-SCHLIB-OPEN, H-A-SCHLIB-KICAD |
| A component's storage holds a stream `Data` (its records) and, only when a pin needs one, a side stream; with every pin on the 10-mil grid and every pin text under 256 bytes no side stream is needed | S-0002, S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0152 | INFERRED | H-A-SCHLIB-OPEN, H-A-SCHLIB-KICAD |
| The side streams are spelled `PinFrac`, `PinWideText`, `PinTextData` and `PinSymbolLineWidth` in code; KiCad's developer page spells them with `Pins`. `PinFrac` holds sub-unit fractions of pin coordinates, `PinWideText` pin texts longer than a short string | S-0002, S-0131, S-0148, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0152 | INFERRED | H-A-SCHLIB-OPEN |
| KiCad tells an Altium symbol library by the `.SchLib` extension and the compound-file signature; it reads libraries only as compound files | S-0131, S-0153 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| KiCad reads every storage of the root as one symbol and names the symbol after the storage, not after `LIBREFERENCE`; it reads neither the header's component list nor `SectionKeys` | S-0131, S-0148 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| A component storage needs its `Data` stream: KiCad reads no symbol from a storage without it, and refuses an empty `Data` | S-0131 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| A storage name is a compound-file name: 1 to 31 characters, none of `/`, `\`, `:` and `!`; sibling names compare after upper-casing, so two names that differ only in letter case cannot both be storages of one library | S-0145, S-0152 | INFERRED | H-A-SCHLIB-OPEN |
| A lib ref that is not a valid storage name is stored under a section key: `/` replaced by `_` and the name cut to 31 characters; the long name and its key are listed in `SectionKeys` | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0151, S-0152 | INFERRED | H-A-SCHLIB-SECTIONKEY |
| `SectionKeys` holds one property record: `KEYCOUNT=<k>`, then `LIBREF<i>=<long name>` and `SECTIONKEY<i>=<storage name>` for i from 0; a reader looks a lib ref up there first and falls back to the storage name | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0151 | INFERRED | H-A-SCHLIB-SECTIONKEY |
| Altium's own rule for two long names that share a 31-character prefix is not documented in any permitted source | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0152 | UNKNOWN | H-A-SCHLIB-SECTIONKEY |
| `Storage` is the stream of the schematic document: without images it holds the one record `\|HEADER=Icon storage`; KiCad's library path never opens it | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-OPEN |

## File header

| fact | source | label | hypothesis |
|---|---|---|---|
| `FileHeader` is a sequence of framed records, as in the binary schematic (`schematic-binary.md`): a 4-byte little-endian word whose low 24 bits give the payload length and whose top byte gives the type, then the payload; a property list has type 0 and ends with one NUL that the length counts | S-0131, S-0148, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-OPEN, H-A-SCHLIB-KICAD |
| The first record is the library header, `HEADER=Protel for Windows - Schematic Library Editor Binary File Version 5.0`; KiCad compares this text without regard to letter case and refuses a library with another text | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-OPEN, H-A-SCHLIB-KICAD |
| The header record lists the components: `COMPCOUNT=<n>`, then for i from 0 `LIBREF<i>=<lib ref>`, `COMPDESCR<i>=<description>` and `PARTCOUNT<i>=<parts + 1>` | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0151 | INFERRED | H-A-SCHLIB-OPEN |
| `PARTCOUNT` counts one more than the parts, in the header and in the component record alike; one reader subtracts 1 from both | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0151 | INFERRED | H-A-SCHLIB-PARTS, H-A-SCHLIB-KICAD |
| `WEIGHT` of the header record is the number of records in all `Data` streams plus 1 in the version-1 writer; KiCad does not read it | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-OPEN |
| The header record carries a font table (`FONTIDCOUNT`, `SIZE<i>`, `FONTNAME<i>`); KiCad reads only the header text and the font sizes from it | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-OPEN |
| Key names are read without regard to letter case by KiCad and by the version-1 reader | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-OPEN |
| Name list: the version-1 writer appends, after the header record, a 4-byte count and one record per component holding its name as a short string; the version-1 reader accepts the header with or without that list, and KiCad reads only the header record. Sources disagree on whether Altium writes the list | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0151 | INFERRED | H-A-SCHLIB-OPEN |

## Records of a component

| fact | source | label | hypothesis |
|---|---|---|---|
| `Data` is a sequence of framed records: property lists (type 0) and binary pin records (type 1), with no header record | S-0131, S-0148, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-OPEN, H-A-SCHLIB-KICAD |
| The first record of `Data` must be the component, `RECORD=1`; KiCad refuses a symbol that starts otherwise | S-0131 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| KiCad reads `Data` to its last byte and refuses a stream with bytes left over after the last record | S-0131 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| Every record after the component belongs to it. KiCad's library path ignores `OWNERINDEX`; the version-1 writer sets an owner index | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-OPEN |
| Coordinates in a library are relative to the symbol's origin, in units of 10 mil, with X rightwards and Y upwards; a `_FRAC` key holds 1/100 000 of a unit. KiCad's library path takes them as written, without the `LOCATION` subtraction of the schematic path | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| `OWNERPARTID` is the part, from 1; part 0 ("Part Zero") holds pins common to every part, which Altium shows on each part. The designator and parameters carry `-1` | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0154 | INFERRED | H-A-SCHLIB-PARTS, H-A-SCHLIB-KICAD |
| KiCad maps `OWNERPARTID` to its unit number, 0 being common to all units, and `PARTCOUNT - 1` (at least 1) to the unit count | S-0131 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| `OWNERPARTDISPLAYMODE` is the 0-based display mode of a child; with `DISPLAYMODECOUNT` above 1 KiCad makes one body style per mode | S-0131 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| Component record keys include `LIBREFERENCE`, `COMPONENTDESCRIPTION`, `PARTCOUNT`, `DISPLAYMODECOUNT`, `OWNERPARTID=-1`, `CURRENTPARTID`, `UNIQUEID`, `DESIGNITEMID`, `COLOR` and `AREACOLOR`; a library component has no `LOCATION`. KiCad reads `LIBREFERENCE`, `COMPONENTDESCRIPTION`, `PARTCOUNT` and `DISPLAYMODECOUNT` | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-OPEN, H-A-SCHLIB-KICAD |
| The version-1 writer also writes `LIBRARYPATH`, `SOURCELIBRARYNAME` and `TARGETFILENAME` with placeholder values; no permitted source gives Altium's values, and KiCad does not read them | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-OPEN |
| A rectangle is `RECORD=14` with `LOCATION` (bottom-left), `CORNER` (top-right), `LINEWIDTH`, `COLOR`, `AREACOLOR` and `ISSOLID`; KiCad reads it as a filled rectangle of its unit | S-0130, S-0131 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| The designator is `RECORD=34` with `NAME=Designator`; KiCad takes its text, less a final `?`, as the reference prefix. Altium's default designators end in `?` (`U?`, `R?`), and placed parts get suffix letters | S-0131, S-0155 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| The comment is a parameter, `RECORD=41` with `NAME=Comment` | S-0130, S-0131 | INFERRED | H-A-SCHLIB-OPEN |
| A footprint model is the chain `RECORD=44`, `RECORD=45` (the model), `RECORD=46` and `RECORD=48`, as in a schematic; in a library KiCad reads the footprint name from `MODELNAME` of the 45 and ignores 44, 46 and 48 | S-0130, S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-KICAD, H-A-SCHLIB-IMPLIDX |
| Implementation index: the version-1 writer and reader use `MODELDATAFILEKIND1` and `MODELDATAFILEENTITY1` (1-based); S-0130 documents the 0-based keys; KiCad reads `MODELDATAFILE0`. No permitted source settles Altium's own base | S-0130, S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-IMPLIDX |
| KiCad accepts the records after the component in any order | S-0131 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |

## Binary pin record

| fact | source | label | hypothesis |
|---|---|---|---|
| In a library, pins are binary records: the 4-byte word `(1 << 24) \| <payload length>`, then the payload, with no NUL. KiCad takes any record whose top byte is not zero as binary | S-0131, S-0148, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-PIN, H-A-SCHLIB-KICAD |
| A short string is one length byte and that many bytes of text, without a terminator, so at most 255 bytes | S-0148, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-PIN, H-A-SCHLIB-KICAD |
| The payload fields, little-endian, are those of the table "Pin fields" below. KiCad's reader and the version-1 writer agree on them field for field up to the part-and-sequence string | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-PIN, H-A-SCHLIB-KICAD |
| The version-1 writer adds a fifth short string, the default value; KiCad stops reading after the part-and-sequence string and does not check for bytes left in the pin | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-PIN |
| `FORMALTYPE`: S-0130 gives 1 for every pin; the version-1 writer writes 0 in binary pins | S-0130, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-PIN |
| `PINCONGLOMERATE`: bits 0-1 the direction from the body end to the hot end (0 right, 1 up, 2 left, 3 down), 0x04 hidden, 0x08 name shown, 0x10 number shown | S-0130, S-0131 | INFERRED | H-A-SCHLIB-PIN, H-A-SCHLIB-KICAD |
| `LOCATION` is the body end of the pin; the electrical (hot) end lies `PINLENGTH` further in the pin's direction. KiCad maps the directions right, up, left and down to its pin orientations pointing left, down, right and up | S-0130, S-0131 | INFERRED | H-A-SCHLIB-PIN, H-A-SCHLIB-KICAD |
| Electrical type: 0 input, 1 input/output, 2 output, 3 open collector, 4 passive, 5 high impedance, 6 open emitter, 7 power | S-0130, S-0131 | INFERRED | H-A-SCHLIB-PIN, H-A-SCHLIB-KICAD |
| Edge codes (one byte each for inner edge, outer edge, inside and outside): 0 none, 1 dot, 3 clock, 4 active-low input, 17 active-low output. KiCad reads outer edge 1 as inverted (with inner edge 3 as inverted clock), inner edge 3 alone as clock, outer edge 4 as input low (with inner edge 3 as clock low) and outer edge 17 as output low | S-0131 | INFERRED | H-A-SCHLIB-PIN, H-A-SCHLIB-KICAD |
| KiCad shows no pin number without bit 0x10, no pin name without bit 0x08, and hides a pin with bit 0x04 | S-0131 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| An Altium overbar is a `\` after each overlined character of a pin name; KiCad converts it to its own `~{…}` form | S-0131 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| `PINLENGTH`, `LOCATION.X` and `LOCATION.Y` are signed 16-bit integers in units of 10 mil; finer positions go to `PinFrac`, keyed by the pin's index in `Data` | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-SCHLIB-PIN |
| S-0152's binary-pin table gives `OWNERPARTID` one byte and has no `FORMALTYPE` byte; it disagrees with both code sources and would shift every later field, so it is rejected | S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0152 | INFERRED | H-A-SCHLIB-PIN |
| Whether Altium also accepts a text pin (`RECORD=2`) in a library is not documented; KiCad's library reader accepts one | S-0131 | UNKNOWN | H-A-SCHLIB-PIN |

### Pin fields

Offsets in bytes from the start of the payload; `d` is the length of the description, `n` of the
name, `m` of the number.

| offset | size | field | Fenolite writes |
|---|---|---|---|
| 0 | 4 | record id (signed) | 2 |
| 4 | 1 | unknown | 0 |
| 5 | 2 | `OWNERPARTID` (signed) | the part, 0 for Part Zero |
| 7 | 1 | `OWNERPARTDISPLAYMODE` | 0 |
| 8 | 1 | inner-edge code | edge code |
| 9 | 1 | outer-edge code | edge code |
| 10 | 1 | inside code | 0 |
| 11 | 1 | outside code | 0 |
| 12 | 1 + d | description (short string) | empty |
| 13 + d | 1 | `FORMALTYPE` | 1 |
| 14 + d | 1 | electrical type | 0 … 7 |
| 15 + d | 1 | `PINCONGLOMERATE` | direction and bits |
| 16 + d | 2 | `PINLENGTH` (signed) | length in 10 mil |
| 18 + d | 2 | `LOCATION.X` (signed) | body end, 10 mil |
| 20 + d | 2 | `LOCATION.Y` (signed) | body end, 10 mil |
| 22 + d | 4 | colour | 0 |
| 26 + d | 1 + n | name (short string) | pin name |
| 27 + d + n | 1 + m | designator (short string) | pin number |
| 28 + d + n + m | 1 | swap group (short string) | empty |
| 29 + d + n + m | 1 | part and sequence (short string) | empty |
| 30 + d + n + m | 1 | default value (short string) | empty |

With empty description, swap group, part-and-sequence and default value, the payload holds
`31 + n + m` bytes.

Worked pin (arithmetic on the table): pin `1` named `IN`, passive, leftwards, name and number shown,
length 20 units, body end (-30, 10) units, part 1. `PINCONGLOMERATE` is 2 | 0x08 | 0x10 = 0x1A. The
payload has 34 bytes, so the record is:

```
22 00 00 01 | 02 00 00 00 | 00 | 01 00 | 00 | 00 00 00 00 | 00 | 01 | 04 | 1A | 14 00 | E2 FF | 0A 00 |
00 00 00 00 | 02 49 4E | 01 31 | 00 | 00 | 00
```

## Oracle observations

| fact | source | label | hypothesis |
|---|---|---|---|
| `kicad-cli sym upgrade <in> -o <out>.kicad_sym` converts any symbol library that one of KiCad's plugins reads, chosen from the input path, on 10.0 and on 9.0; `-o` is required for a library that is not KiCad's own | S-0153 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| `kicad-cli sym export svg` reads KiCad libraries only: given a `.SchLib`, kicad-cli 10.0.6 exits 0 and writes nothing, so a rendering takes the upgrade first | S-0020, S-0153 | INFERRED | H-A-SCHLIB-KICAD |
| On kicad-cli 10.0.6, a library with another header text, without `FileHeader`, that is not a compound file, whose `Data` does not start with the component, that has a stray byte after the last record, whose binary record has another record id, whose pin is cut short, or whose pin lacks its last two short strings, exits 2 with the generic message "Unable to convert library" | S-0020, S-0153 | INFERRED | H-A-SCHLIB-KICAD |
| On kicad-cli 10.0.6, a component storage without `Data` crashes the tool (exit 139); the oracle never runs that case | S-0020, S-0153 | INFERRED | H-A-SCHLIB-KICAD |
| On kicad-cli 10.0.6, a library whose header has no component list and that has no `Storage` stream converts; a symbol stored under a section key is named after the key | S-0020, S-0153 | INFERRED | H-A-SCHLIB-KICAD |
| Converting the same library twice gives byte-identical KiCad libraries | S-0020, S-0153 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| Fenolite's oracle (`tests/kicad/altium/test_schlib_oracle.py`, kicad-cli 10.0.6, 2026-10-02): the sample's `FenoliteSample.SchLib` converts (exit 0) into six symbols named after their storages, with the generic pins (number, name, passive, hot end, angle, length, unit 1), the reference prefix and the footprint name; two conversions are byte-identical | S-0020, S-0153 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| Fenolite's negative controls on kicad-cli 10.0.6 (2026-10-02), built from the writer's records: another header text, a `Data` whose first record is not the component, a stray byte after the last record, and a pin without its last two short strings each exit 2 with "Unable to convert library"; the same library without the change converts | S-0020, S-0153 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| Fenolite's oracle on kicad-cli 10.0.6 (2026-10-02): `altium_kicad.SchLib` of `examples/altium_kicad/` converts into its four symbols with the source's unit count and, per pin, the number, the name (overbars back in KiCad's form), the electrical type after the lossy mapping, the hot end, the angle, the length, the unit (Part Zero as unit 0) and the hidden flag; the reference prefix, the footprint name, the inverted and clock shapes all read back | S-0020, S-0153 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-02) | H-A-SCHLIB-KICAD |
| The same test with kicad-cli 9.0.9 (pinned image, local run, 2026-10-02) passes as well: 9.0 converts every library; a pin name `~` reads back as an empty name, because a 9.0 library file writes `~` for an empty name | S-0020, S-0031, S-0153 | ORACLE-VERIFIED(kicad-cli) (9.0.9, pinned image, local run; 2026-10-02) | H-A-SCHLIB-KICAD9 |

## Facts awaiting a permitted source

Facts that the format research first found in AltiumSharp version 2. Version 1 (S-0150) does not give
them, so Fenolite does not use them, and no row above rests on them:

- that Altium's own headers carry no name list after the header record;
- that `WEIGHT` is a record count of the whole library as Altium writes it;
- that a writer reproduces a corpus of real libraries byte for byte;
- that Altium writes the records 44 … 48 at the end of `Data`;
- that a library writer writes no `OWNERINDEX` (version 1 sets an owner index).

Facts that c0032's and c0033's pages cite from S-0142 (unpinned AltiumSharp) and that version 1 does
not give. Each of those rows also cites another source, except the two marked "S-0142 only"; c0034
changes no behaviour of c0032 or c0033 (design Decision 12, Open Question 8), and the coordinator
decides whether a follow-up change replaces them:

- `project.md`: every fact cited from S-0142 (INI layout, `[DocumentN]` sections, relative
  `DocumentPath`, `[Design]` `Version` and optional keys, CR LF "Altium uses CRLF", the byte-order mark
  kept, Altium rewriting the file). Version 1 has no project-file code at all. The `Version` and
  optional-key row and the byte-order-mark row are S-0142 only;
- `schematic-ascii.md`: the project writer's statement that Altium writes CR LF (line-end row), and the
  ownership chain 44 → 45 → 46, 48 of the footprint link (version 1 declares the record numbers 44,
  45, 46 and 48 but shows no owner chain);
- `schematic-binary.md`: that the writer writes compound files of version 3 (version 1 hands the
  container to a third-party library and states no version; S-0142 only), and that a binary pin record
  belongs to libraries only (version 1 writes a pin as binary whenever its caller asks, and the
  schematic-document writer does not show which);
- `schematic-binary.md`, `Storage` without images: version 1 always writes the `Storage` stream, which
  confirms that part of the row, but it writes a `WEIGHT` key holding the image count (0 without
  images), where the row says "no weight key"; the other sources of that row (S-0130, S-0131) remain.

## Check of S-0142 against S-0150

Task 1.3 of change c0034 read only the version-1 files at the pinned commit (`SchWriter.cs`,
`SchDocWriter.cs`, `CompoundFileWriter.cs`, `SchLibWriter.cs`, `Records/Sch/SchLibHeader.cs`,
`SchImplementation.cs`, `SchImplementationList.cs`, `SchMapDefinerList.cs`,
`SchImplementationParameters.cs` and the file list of the tree), on 2026-10-02:

| page and fact (cited from S-0142) | version 1 |
|---|---|
| `schematic-binary.md`: the record word `(type << 24) \| length`, a NUL that the length counts | confirmed |
| `schematic-binary.md`: a `Storage` stream is always written | confirmed (written even without images) |
| `schematic-binary.md`: payload text in a Windows code page | confirmed (Windows-1252 by default) |
| `schematic-ascii.md`: records 44, 45, 46 and 48 of a footprint link | record numbers confirmed; the ownership chain not shown |
| `schematic-binary.md`: compound files of version 3 | not given |
| `schematic-binary.md`: binary pins belong to libraries | not given |
| `schematic-binary.md`: `Storage` without images has no weight key | contradicted (version 1 writes `WEIGHT`) |
| `project.md`: every project-file fact | not given (no project code in version 1) |
| `schematic-ascii.md`: Altium writes project files with CR LF | not given |

Confirmed rows carry "confirmed in S-0150" in their source cell.

## Fenolite's choices

These are choices of the writer, not format facts (design of change c0034):

- the root holds `FileHeader`, `Storage`, `SectionKeys` only when a symbol has a section key, then one
  storage per symbol in the MS-CFB order of the storage names, each holding only `Data`;
- the header record holds `HEADER`, `WEIGHT` (records in all `Data` streams plus 1), one font
  (`FONTIDCOUNT=1`, `SIZE1=10`, `FONTNAME1=Times New Roman`), `COMPCOUNT`, then `LIBREF<i>`,
  `COMPDESCR<i>` (only when not empty) and `PARTCOUNT<i>`; nothing follows the record;
- `Data` holds the component, the binary pins ordered by part and then by number in natural order, one
  rectangle per part, the designator `<prefix>?`, the `Comment` parameter and, with a footprint, the
  records 44, 45, 46 and 48; no record carries `OWNERINDEX`, and no coordinate carries `_FRAC`;
- the component carries `UNIQUEID=<project.unique_id("schlib:<library>:<lib ref>")>`, and neither
  `LIBRARYPATH`, `SOURCELIBRARYNAME` nor `TARGETFILENAME`;
- binary pins carry all five short strings, `FORMALTYPE` 1, an empty description, swap group,
  part-and-sequence and default value, display mode 0 and colour 0;
- the data file keys of the footprint model stay 0-based (`MODELDATAFILEENTITY0`, `MODELDATAFILEKIND0`,
  `MODELDATAFILE0`), as in the schematic;
- a lib ref longer than 31 characters is stored under its section key; another invalid name, and two
  storage names equal under the MS-CFB order, are refused;
- no side stream is written: off-grid pins and pin texts over 255 bytes are refused.

### Mapping from a KiCad symbol

The reverse of the importer's mapping (rows above):

| KiCad (`SymbolDef`) | Altium |
|---|---|
| pin rotation 0, 90, 180, 270 | direction 2 (left), 3 (down), 0 (right), 1 (up) |
| pin position (hot end) | body end = hot end moved by the length against the direction |
| input, bidirectional, output, open_collector, passive, tri_state, open_emitter, power_in | 0, 1, 2, 3, 4, 5, 6, 7 |
| power_out; free, unspecified, no_connect | 7; 4 (lossy, `altium.pin-lossy`) |
| line, inverted, clock, inverted_clock | none; outer 1; inner 3; outer 1 and inner 3 |
| input_low, output_low, clock_low | outer 4; outer 17; inner 3 and outer 4 |
| edge_clock_high, non_logic | none (lossy, `altium.pin-lossy`) |
| unit k, unit 0 | part k, Part Zero |
| body style 1 and 0 | kept; other styles and alternates dropped (`altium.symbol-simplified`) |
| `~{AB}` overbar | `A\B\` |
| `pin_names_hidden`, empty name, name `~` | name not shown (0x08 clear) |
| `pin_numbers_hidden` | number not shown (0x10 clear) |
| hidden pin | 0x04 |

Each part gets one rectangle: the bounding box of the body ends of its pins and of the Part Zero pins,
grown to at least 200 mil per side around its centre and rounded outwards to 10 mil; a part without
pins gets the square from (-100, -100) to (100, 100) mil.
