# Provenance of `fenolite.backends.altium`

An experimental writer of Altium's ASCII schematic (`.SchDoc`) and project file (`.PrjPcb`), change
c0032. Every fact this package relies on comes from a public source listed in
`docs/evidence/sources.md`, recorded in Fenolite's own words in `docs/formats/altium/schematic-ascii.md`
and `docs/formats/altium/project.md`. The code is written from those pages. No third-party code was
copied, transcribed or followed: the GPL sources (S-0131, S-0132) and the other open-source projects
(S-0130, S-0143, S-0144; AltiumSharp only as version 1, S-0150; S-0142 not used) were read for facts only. No Altium file, sample or vendor binary was
downloaded, opened or decompiled, and no file of any organisation was used. The binary form (change
c0033) adds the compound-file container, written from `docs/formats/altium/compound-file.md` (MS-CFB,
S-0145, under the Open Specification Promise, S-0146), and the record framing of
`docs/formats/altium/schematic-binary.md`. The schematic library (change c0034) adds storages to the
container and the library records, written from `docs/formats/altium/schematic-library.md`; AltiumSharp
is used only as version 1 at commit `afe796434b6d2110c745c90abe44a6ddf64f5bca` (S-0150), never version 2
(LEGAL.md P1), and the format researcher's scratch probe was not followed.

| fact-or-area | public source | licence of source | date | how used |
|---|---|---|---|---|
| header record, record syntax (one line per record, `\|KEY=VALUE` fields, booleans), character set and line ends | S-0002, S-0130, S-0131, S-0133, S-0143, S-0150 | not stated on the page; WTFPL v2; GPL-2.0-or-later (facts only); all rights reserved (read for facts); MIT; Apache-2.0 | 2026-10-02 | facts only |
| record numbering, ownership order, units of 10 mil, Y upwards from the bottom-left corner, absolute child coordinates | S-0002, S-0130, S-0131 | not stated on the page; WTFPL v2; GPL-2.0-or-later (facts only) | 2026-10-02 | facts only |
| sheet record: font table, grids, colours, ISO sheet styles and drawing areas, custom size | S-0002, S-0130, S-0131 | not stated on the page; WTFPL v2; GPL-2.0-or-later (facts only) | 2026-10-02 | facts only |
| component, rectangle and pin records: part count, current part, body corners, pin body end and electrical end, direction and display bits, electrical type | S-0130, S-0131, S-0137, S-0140 | WTFPL v2; GPL-2.0-or-later (facts only); all rights reserved (read for facts) | 2026-10-02 | facts only |
| designator and comment records; a parameter text that starts with `=` | S-0130, S-0131, S-0137, S-0144 | WTFPL v2; GPL-2.0-or-later (facts only); all rights reserved (read for facts); MPL-2.0 (facts only) and MIT | 2026-10-02 | facts only |
| library link (`LIBREFERENCE`, `DESIGNITEMID`, `SOURCELIBRARYNAME`) and footprint link (records 44, 45, 46 and 48); "Update From Libraries"; footprint search | S-0002, S-0130, S-0131, S-0135, S-0136, S-0137, S-0138, S-0144, S-0150 | not stated on the page; WTFPL v2; GPL-2.0-or-later (facts only); all rights reserved (read for facts); MPL-2.0 (facts only) and MIT | 2026-10-02 | facts only |
| wires, net labels and power ports: connection points, label hotspot, port styles and orientation, scope of names | S-0130, S-0131, S-0140 | WTFPL v2; GPL-2.0-or-later (facts only); all rights reserved (read for facts) | 2026-10-02 | facts only |
| component unique ids: form, schematic-to-PCB link, duplicates not repaired | S-0130, S-0139 | WTFPL v2; all rights reserved (read for facts) | 2026-10-02 | facts only |
| project file: sections, `Version`, `DocumentPath`, line ends, byte-order mark; the engineering change order | S-0132, S-0134, S-0141, S-0143 | GPL-3.0-or-later (facts only); all rights reserved (read for facts); MIT | 2026-10-02 | facts only |
| `kicad-cli` cannot read a `.SchDoc`: it picks its schematic reader by extension, and authored files exit 3 | S-0020, S-0132 | GPL-3.0-or-later tool run as a subprocess; GPL-3.0-or-later (facts only) | 2026-10-02 | oracle |
| compound-file container (c0033): header, sectors, FAT, mini FAT and mini stream, directory entries, the sibling tree | S-0145, S-0146 | Microsoft Open Specifications notice (copies allowed to develop implementations); Microsoft patent non-assert | 2026-10-02 | facts only |
| binary schematic (c0033): streams `FileHeader` and `Storage`, the 32-bit length word and NUL framing, the binary header text, text pins, the empty `Storage` record | S-0002, S-0130, S-0131, S-0133, S-0147, S-0148, S-0150 | not stated on the page; WTFPL v2; GPL-2.0-or-later (facts only); all rights reserved (read for facts); Apache-2.0 | 2026-10-02 | facts only |
| the Altium 365 Viewer's inputs, and a third-party report of a binary schematic checked in it (c0033) | S-0143, S-0149 | MIT; all rights reserved (read for facts) | 2026-10-02 | facts only |
| schematic library container (c0034): one storage per component holding `Data`, `FileHeader`, `Storage`, `SectionKeys` and section keys, optional side streams; compound-file storages | S-0002, S-0131, S-0145, S-0148, S-0150, S-0151, S-0152 | not stated on the page; GPL-2.0-or-later (facts only); Microsoft Open Specifications notice; Apache-2.0, version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca only (facts only); GPL-3.0 (facts only); MIT | 2026-10-02 | facts only |
| schematic library records (c0034): header text and keys, `WEIGHT`, the name list, component, rectangle, designator, comment and footprint chain, `OWNERPARTID` and Part Zero, implementation index, designator prefix | S-0130, S-0131, S-0150, S-0151, S-0154, S-0155 | WTFPL v2; GPL-2.0-or-later (facts only); Apache-2.0, version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca only (facts only); GPL-3.0 (facts only); all rights reserved (read for facts) | 2026-10-02 | facts only |
| binary pin records (c0034): framing without NUL, short strings, field order with the default value, `FORMALTYPE`, `PINCONGLOMERATE`, electrical types, edge codes, overbars; the contradicted table of S-0152 | S-0130, S-0131, S-0148, S-0150, S-0152 | WTFPL v2; GPL-2.0-or-later (facts only); Apache-2.0, version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca only (facts only); MIT | 2026-10-02 | facts only |
| mapping of a KiCad symbol to an Altium symbol (c0034): directions, body ends, electrical types, edge codes, visibility, units and Part Zero, the reverse of KiCad's importer | S-0131, S-0154 | GPL-2.0-or-later (facts only); all rights reserved (read for facts) | 2026-10-02 | facts only |
| `kicad-cli sym upgrade` converts a `.SchLib` through KiCad's Altium importer (c0034 oracle) | S-0020, S-0153 | GPL-3.0-or-later tool run as a subprocess; GPL-3.0-or-later (facts only) | 2026-10-02 | oracle |
