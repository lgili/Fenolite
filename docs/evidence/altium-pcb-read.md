# Altium PCB reader: census and oracles

Results of the product reader `fenolite.backends.altium.read` (change c0041) on the eleven public corpus
rows of `tests/corpus/manifest.toml` (uses `altium-pcbdoc` and `altium-pcblib`). The files are fetched
into the corpus cache by `tools/corpus_fetch.py` and never committed; this page holds counts and lengths
only, by row id. The facts are on `docs/formats/altium/pcb-read.md`.

## Census (2026-10-05)

`FENOLITE_REQUIRE=corpus uv run pytest tests/corpus/test_altium_pcb_census.py` on macOS, local corpus
cache: 14 tests passed. On every row: no issue of any severity, no `short-record` warning, every typed
storage rebuilds byte for byte with empty `trailing` (each footprint of a library too), every region has
an empty tail, `Regions6` and `ShapeBasedRegions6` hold the same number of records, every non-empty
polygon name decodes to printable text, and every subrecord length is one of the list of
`pcb-read.md` ("Record lengths").

### Documents

| row id | nets | components | classes | rules | polygons | pads | vias | tracks | arcs | texts | fills | regions | shape regions | wide strings | copper layers | stack entries | untyped storages |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `altium-third-party-pcbdoc-01` | 158 | 248 | 39 | 40 | 13 | 745 | 646 | 4353 | 96 | 531 | 2 | 90 | 90 | 531 | 4 | 13 | 44 |
| `altium-third-party-pcbdoc-02` | 34 | 41 | 15 | 39 | 18 | 143 | 242 | 698 | 56 | 115 | 1 | 91 | 91 | 115 | 4 | 13 | 47 |
| `altium-third-party-pcbdoc-03` | 68 | 55 | 20 | 39 | 1 | 385 | 47 | 1244 | 34 | 159 | 0 | 23 | 23 | 159 | 2 | 9 | 49 |
| `altium-third-party-pcbdoc-04` | 10 | 15 | 16 | 45 | 9 | 53 | 67 | 394 | 24 | 33 | 12 | 27 | 27 | 33 | 4 | 11 | 47 |
| `altium-third-party-pcbdoc-05` | 30 | 23 | 15 | 41 | 2 | 100 | 59 | 421 | 3 | 65 | 0 | 24 | 24 | 65 | 2 | 9 | 47 |
| `altium-third-party-pcbdoc-06` | 18 | 27 | 18 | 40 | 10 | 106 | 42 | 1076 | 69 | 83 | 6 | 42 | 42 | 83 | 2 | 9 | 48 |
| `altium-third-party-pcbdoc-07` | 21 | 12 | 18 | 50 | 9 | 116 | 60 | 743 | 26 | 36 | 1 | 31 | 31 | 36 | 4 | 11 | 48 |

| row id | subrecord lengths (kind length: count) | designator texts | with a channel suffix | changed on the board | named polygons | non-ASCII bytes | `%UTF8%` keys |
|---|---|---|---|---|---|---|---|
| `altium-third-party-pcbdoc-01` | arc 56: 96, fill 46: 2, pad 170: 745, pad-layers 0: 741, pad-layers 651: 4, text 232: 531, track 45: 4353, via 299: 646 | 248 | 84 | 2 | 5 | 239 | 0 |
| `altium-third-party-pcbdoc-02` | arc 60: 56, fill 50: 1, pad 194: 143, pad-layers 0: 107, pad-layers 651: 36, text 252: 115, track 49: 698, via 321: 160, via 351: 82 | 41 | 0 | 0 | 12 | 472 | 0 |
| `altium-third-party-pcbdoc-03` | arc 60: 34, pad 194: 385, pad-layers 0: 312, pad-layers 651: 73, text 252: 159, track 49: 1244, via 321: 47 | 55 | 0 | 0 | 1 | 94 | 0 |
| `altium-third-party-pcbdoc-04` | arc 60: 24, fill 50: 12, pad 186: 53, pad-layers 0: 53, text 252: 33, track 49: 394, via 321: 67 | 15 | 0 | 0 | 9 | 48 | 0 |
| `altium-third-party-pcbdoc-05` | arc 60: 3, pad 185: 100, pad-layers 0: 100, text 252: 65, track 49: 421, via 321: 59 | 23 | 0 | 0 | 2 | 69 | 0 |
| `altium-third-party-pcbdoc-06` | arc 60: 69, fill 50: 6, pad 194: 106, pad-layers 0: 15, pad-layers 651: 91, text 252: 83, track 49: 1076, via 321: 42 | 27 | 0 | 0 | 10 | 169 | 0 |
| `altium-third-party-pcbdoc-07` | arc 60: 26, fill 50: 1, pad 186: 116, pad-layers 0: 99, pad-layers 651: 17, text 252: 36, track 49: 743, via 321: 60 | 12 | 0 | 0 | 9 | 51 | 0 |

- Designator texts (`H-A-RD-PCB-TEXT`, refuted; `H-A-RD-PCB-TEXT-2`): on six rows every designator text
  equals its component's `SOURCEDESIGNATOR`. On `altium-third-party-pcbdoc-01` (saved 2017, a project
  with a repeated sheet) 84 of the 248 designator texts show the logical designator followed by a
  channel suffix of 2 or 3 characters: each belongs to a component whose `SOURCEDESIGNATOR` is shared by
  12 or 13 components and whose `SOURCEUNIQUEID` holds three ids. Two more show another designator than
  `SOURCEDESIGNATOR` (components whose `SOURCEUNIQUEID` holds two ids). Every text with a wide-string index found in
  the table shows that entry.
- Wide strings: the row of 2017 stores its four empty entries with the length 2 and no text bytes;
  the reader follows S-0148 (a length of 2 or less is an empty entry) and its 531 entries equal the
  `Header` count.
- Rules (`H-A-RD-PCB-RULE`): every `Rules6` stream ends at a record end; 39 kind numbers occur, each
  with one `RULEKIND` text over the seven rows (the table of `pcb-read.md`, "Rules").
- Text encoding (`H-A-RD-PCB-CODEC`): no `%UTF8%` key occurs; the non-ASCII bytes of the property
  records (column above) decode as ISO-8859-1 without failure.

### Libraries

| row id | footprints | primitives | pads | tracks | arcs | texts | regions | raw (component bodies) | subrecord lengths | non-ASCII bytes | `%UTF8%` keys |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `altium-third-party-pcblib-01` | 1 | 9 | 5 | 4 | 0 | 0 | 0 | 0 | pad 170: 5, pad-layers 0: 5, track 45: 4 | 4 | 0 |
| `altium-third-party-pcblib-02` | 9 | 9 | 9 | 0 | 0 | 0 | 0 | 0 | pad 171: 9, pad-layers 651: 9 | 1 | 0 |
| `altium-third-party-pcblib-03` | 1 | 24 | 2 | 21 | 0 | 0 | 0 | 1 | pad 185: 2, pad-layers 0: 2, track 49: 21 | 0 | 0 |
| `altium-third-party-pcblib-04` | 1 | 6 | 1 | 5 | 0 | 0 | 0 | 0 | pad 185: 1, pad-layers 0: 1, track 49: 5 | 1 | 0 |

## Document oracle

`FENOLITE_REQUIRE=corpus uv run pytest tests/kicad/altium/test_pcbdoc_read_oracle.py` with `kicad-cli`
10.0.6 (macOS, local, 2026-10-05): 7 passed. In the pinned Linux image of the `kicad-10` job, 6 pass and
`altium-third-party-pcbdoc-02` is skipped: there `kicad-cli pcb import` exits 255 with an unhandled C++
exception of its own importer, whose class differs between runs (`std::bad_alloc` in CI, `std::length_error`
in the same image run locally), so that row is compared on macOS only. On macOS,
`kicad-cli pcb import --format altium` exits 0 on all seven
rows (no row is excluded). On every row the net names, the copper layer count and the length of
`copper_chain`, the footprint references, every pad (position, footprint, name, net, round hole size,
top-layer size, and shape and corner ratio of the simple pads), every via (position, diameter, hole, net)
and every free copper track with a net (ends, width, chain position, net) agree, and the zone count
equals the polygon count. Positions are compared after KiCad's 10 nm conversion (`pcb-read.md`, "What
KiCad does not import"); the largest difference left is 0 nm on every row (`H-A-UNIT`). Every item of
KiCad's board has a reader record.

| row id | nets | copper layers | footprints | footprints of free pads | pads | pads on a paste layer not imported | component copper regions and fills as unnamed pads | pads slotted hole size not compared | pads shape compared | pads shape not compared | vias | copper tracks | zones | largest difference nm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `altium-third-party-pcbdoc-01` | 158 | 4 | 248 | 4 | 735 | 10 | 2 | 0 | 731 | 0 | 646 | 1346 | 13 | 0 |
| `altium-third-party-pcbdoc-02` | 34 | 4 | 41 | 0 | 143 | 0 | 0 | 0 | 141 | 2 | 242 | 191 | 18 | 0 |
| `altium-third-party-pcbdoc-03` | 68 | 2 | 55 | 0 | 385 | 0 | 8 | 4 | 383 | 2 | 47 | 598 | 1 | 0 |
| `altium-third-party-pcbdoc-04` | 10 | 4 | 15 | 2 | 53 | 0 | 6 | 0 | 51 | 0 | 67 | 149 | 9 | 0 |
| `altium-third-party-pcbdoc-05` | 30 | 2 | 23 | 4 | 100 | 0 | 0 | 0 | 64 | 32 | 59 | 194 | 2 | 0 |
| `altium-third-party-pcbdoc-06` | 18 | 2 | 27 | 0 | 106 | 0 | 0 | 20 | 106 | 0 | 42 | 111 | 10 | 0 |
| `altium-third-party-pcbdoc-07` | 21 | 4 | 12 | 2 | 116 | 0 | 0 | 12 | 114 | 0 | 60 | 475 | 9 | 0 |

## Library oracle

`FENOLITE_REQUIRE=corpus uv run pytest tests/kicad/altium/test_pcblib_read_oracle.py` with `kicad-cli`
10.0.6 (macOS, local, 2026-10-05): 4 passed. `kicad-cli fp upgrade` exits 0 on the four rows and writes
one `.kicad_mod` per footprint. The footprint names agree, and so does every pad (position with Y
negated, number, top-layer size, round hole size, plating) after KiCad's 10 nm conversion, with a
largest difference of 0 nm; the lines and arcs on the two overlay layers agree in number. No corpus
library holds an arc on an overlay layer, so that count is checked only at 0.

| row id | footprints | pads | pads slotted hole size not compared | pads on a paste layer not imported | overlay lines | overlay arcs | largest difference nm |
|---|---|---|---|---|---|---|---|
| `altium-third-party-pcblib-01` | 1 | 5 | 0 | 0 | 4 | 0 | 0 |
| `altium-third-party-pcblib-02` | 9 | 9 | 9 | 0 | 0 | 0 | 0 |
| `altium-third-party-pcblib-03` | 1 | 2 | 0 | 0 | 13 | 0 | 0 |
| `altium-third-party-pcblib-04` | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
