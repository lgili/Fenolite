# Provenance of `fenolite.backends.altium`

An experimental writer of Altium's ASCII schematic (`.SchDoc`) and project file (`.PrjPcb`), change
c0032. Every fact this package relies on comes from a public source listed in
`docs/evidence/sources.md`, recorded in Fenolite's own words in `docs/formats/altium/schematic-ascii.md`
and `docs/formats/altium/project.md`. The code is written from those pages. No third-party code was
copied, transcribed or followed: the GPL sources (S-0131, S-0132) and the other open-source projects
(S-0130, S-0142, S-0143, S-0144) were read for facts only. No Altium file, sample or vendor binary was
downloaded, opened or decompiled, and no file of any organisation was used.

| fact-or-area | public source | licence of source | date | how used |
|---|---|---|---|---|
| header record, record syntax (one line per record, `\|KEY=VALUE` fields, booleans), character set and line ends | S-0002, S-0130, S-0131, S-0133, S-0142, S-0143 | not stated on the page; WTFPL v2; GPL-2.0-or-later (facts only); all rights reserved (read for facts); Apache-2.0 or MIT; MIT | 2026-10-02 | facts only |
| record numbering, ownership order, units of 10 mil, Y upwards from the bottom-left corner, absolute child coordinates | S-0002, S-0130, S-0131 | not stated on the page; WTFPL v2; GPL-2.0-or-later (facts only) | 2026-10-02 | facts only |
| sheet record: font table, grids, colours, ISO sheet styles and drawing areas, custom size | S-0002, S-0130, S-0131 | not stated on the page; WTFPL v2; GPL-2.0-or-later (facts only) | 2026-10-02 | facts only |
| component, rectangle and pin records: part count, current part, body corners, pin body end and electrical end, direction and display bits, electrical type | S-0130, S-0131, S-0137, S-0140 | WTFPL v2; GPL-2.0-or-later (facts only); all rights reserved (read for facts) | 2026-10-02 | facts only |
| designator and comment records; a parameter text that starts with `=` | S-0130, S-0131, S-0137, S-0144 | WTFPL v2; GPL-2.0-or-later (facts only); all rights reserved (read for facts); MPL-2.0 (facts only) and MIT | 2026-10-02 | facts only |
| library link (`LIBREFERENCE`, `DESIGNITEMID`, `SOURCELIBRARYNAME`) and footprint link (records 44, 45, 46 and 48); "Update From Libraries"; footprint search | S-0002, S-0130, S-0131, S-0135, S-0136, S-0137, S-0138, S-0142, S-0144 | not stated on the page; WTFPL v2; GPL-2.0-or-later (facts only); all rights reserved (read for facts); Apache-2.0 or MIT; MPL-2.0 (facts only) and MIT | 2026-10-02 | facts only |
| wires, net labels and power ports: connection points, label hotspot, port styles and orientation, scope of names | S-0130, S-0131, S-0140 | WTFPL v2; GPL-2.0-or-later (facts only); all rights reserved (read for facts) | 2026-10-02 | facts only |
| component unique ids: form, schematic-to-PCB link, duplicates not repaired | S-0130, S-0139 | WTFPL v2; all rights reserved (read for facts) | 2026-10-02 | facts only |
| project file: sections, `Version`, `DocumentPath`, line ends, byte-order mark; the engineering change order | S-0132, S-0134, S-0141, S-0142, S-0143 | GPL-3.0-or-later (facts only); all rights reserved (read for facts); Apache-2.0 or MIT; MIT | 2026-10-02 | facts only |
| `kicad-cli` cannot read a `.SchDoc`: it picks its schematic reader by extension, and authored files exit 3 | S-0020, S-0132 | GPL-3.0-or-later tool run as a subprocess; GPL-3.0-or-later (facts only) | 2026-10-02 | oracle |
