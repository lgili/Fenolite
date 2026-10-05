# Altium schematic reader: corpus census and library oracle

This page records what the schematic reader (change c0040, `fenolite.backends.altium.read.sch` and
`read.schlib`) found on the public files of the corpus, and what `kicad-cli` made of the libraries. It holds
row ids, record ids, key names, stream names, issue codes and counts only; no value of a file is quoted.

- Rows: the `altium-sch` and `altium-schlib` rows of `tests/corpus/manifest.toml`, fetched by
  `uv run python tools/corpus_fetch.py --uses altium-sch --uses altium-schlib` (22 files, SHA-256 verified,
  never committed). Schematics come from three repositories (S-0187, S-0188, S-0279), libraries from three
  (S-0277, S-0278, S-0279).
- Census: `uv run python tools/altium_census.py --uses altium-sch --json` and `--uses altium-schlib`, run on
  2026-10-05. The tables below are its output.
- Checks: `FENOLITE_REQUIRE=corpus uv run pytest tests/corpus/test_altium_sch_read.py` (26 passed on
  2026-10-05) and `FENOLITE_REQUIRE=kicad,corpus uv run pytest tests/kicad/altium/test_schlib_read_oracle.py`
  (15 passed on 2026-10-05, kicad-cli 10.0.6, macOS). kicad-cli 9 was not run for this change.

## Results by hypothesis

| hypothesis | result |
|---|---|
| `H-A-RD-SCH-FRAME` | 0 cut frames and 0 `altium.sch.malformed-record` in the 13 schematics (`FileHeader`, `Additional`, `Storage`) and the 9 libraries (`FileHeader`, `SectionKeys`, `Storage`, 169 `Data` streams); every property list ends with one NUL |
| `H-A-RD-SCH-IDENT` | `check_identity` is `()` for all 22 rows |
| `H-A-RD-SCH-HEADER` | 13 schematic headers and 9 library headers of the known texts; `WEIGHT` agrees in 13 of 13 `FileHeader` streams and in 11 of 13 `Additional` streams (the 2 others hold the header alone, without `WEIGHT`); in the 9 libraries `WEIGHT` is the number of `Data` records plus one and `COMPCOUNT` the number of components; 0 `altium.sch.weight-mismatch` |
| `H-A-RD-SCH-CASE` | 0 keys repeated after folding; schematics hold 98 226 mixed-case and 37 433 upper-case keys, libraries 8 467 and 14 389; every folded key of a typed record is modelled or counted below as unknown |
| `H-A-RD-SCH-TEXT` | refuted: of the values with a `%UTF8%` twin, 514 of 734 (schematics) and 188 of 193 (libraries) differ from a `cp1252` reading of the plain value. In the rows of S-0187 and S-0188 every difference is one character: the plain value holds the byte 0x8E where the twin holds U+00A6 (S-0130 describes this byte); in the rows of S-0279 the plain values are in another system code page. Every twin is valid UTF-8, and 0 `altium.sch.text-undecodable` was reported. Successor `H-A-RD-SCH-TEXT-2` |
| `H-A-RD-SCH-OWNER` | 0 `altium.sch.orphan-record`; every record of every schematic is reached exactly once from `roots` |
| `H-A-RD-SCH-ADDOWNER` | every one of the 98 harness entries and 23 harness types of `Additional` has a harness connector as owner; 32 entries and 9 types carry no `OWNERINDEX` (index 0) |
| `H-A-RD-SCH-LIBOWNER` | in library `Data`, `OWNERINDEX` is present on 183 records 45, 183 records 46, 183 records 48 and 6 records 41, and always names an earlier record of the same stream (45 → 44, 46 and 48 → 45, 41 → 48); 0 indexes out of range; every other record belongs to the component |
| `H-A-RD-SCH-FRAC` | 0 fractions out of range; the sign pairs of (units, fraction) are `+/+` 289 in schematics, `+/+` 72 and `-/-` 21 in libraries; 86 and 67 lengths are not whole nanometres |
| `H-A-RD-SCH-PARTS` | 0 `altium.sch.part-out-of-range`; the oracle's unit and body-style counts equal Fenolite's for all 169 library components, but no corpus library holds a component of more than one part or display mode, and the schematics hold 2 placed multi-part components only |
| `H-A-RD-SCH-PIN` | 1 201 binary pins, all with five short strings and no tail; the oracle's pins equal Fenolite's for the compared fields on all 9 rows |
| `H-A-RD-SCH-PINSIDE` | the 2 `PinFrac` streams match the recorded layout to their last byte and move 8 pins; 21 `PinTextData` and 99 `PinSymbolLineWidth` streams stay opaque (no permitted layout); 99 `PinPackageLength` streams are kept as unknown streams; no `PinWideText` stream is in the corpus |
| `H-A-RD-SCH-STORAGE` | 7 `Storage` records after the header, all with the recorded embedded-file layout, 0 opaque |
| `H-A-RD-SCH-ASCII` | not settled: no public Altium-saved ASCII schematic; the rewritten corpus records read back equal (`test_ascii_form_from_corpus_records`) |
| `H-A-RD-SCH-KICAD` | kicad-cli 10.0.6 converts all 9 rows (exit 0); pins, unit counts and body-style counts agree, after the two recorded importer behaviours below |

## Library oracle per row

kicad-cli 10.0.6 (`sym upgrade <row> -o <tmp>.kicad_sym`, through `fenolite.backends.kicad.cli.KicadCli`,
inside `tmp_path`), 2026-10-05. "Known" counts the pins a recorded importer behaviour changes:
`space-in-pin-name` (a space of a pin name written as `_`) and `position-grid-100nm` (positions held in steps
of 100 nm), both rows of `docs/formats/altium/schematic-library.md`, "Oracle observations".

| row | exit | components | pins | known: space in name | known: 100 nm grid | result |
|---|---|---|---|---|---|---|
| `altium-third-party-schlib-01` | 0 | 1 | 2 | 0 | 0 | agree |
| `altium-third-party-schlib-02` | 0 | 1 | 5 | 0 | 0 | agree |
| `altium-third-party-schlib-03` | 0 | 3 | 55 | 0 | 0 | agree |
| `altium-third-party-schlib-04` | 0 | 18 | 96 | 0 | 0 | agree |
| `altium-third-party-schlib-05` | 0 | 10 | 118 | 0 | 0 | agree |
| `altium-third-party-schlib-06` | 0 | 50 | 390 | 0 | 0 | agree |
| `altium-third-party-schlib-07` | 0 | 3 | 0 | 0 | 0 | agree |
| `altium-third-party-schlib-08` | 0 | 16 | 109 | 0 | 0 | agree |
| `altium-third-party-schlib-09` | 0 | 67 | 426 | 1 | 5 | agree |

The negative control (`test_negative_control`) moves one pin of `altium-third-party-schlib-03` in
Fenolite's reading and the comparison reports that pin and its symbol.

## Tag `altium-sch`

Rows (13): `altium-third-party-schdoc-01`, `altium-third-party-schdoc-02`, `altium-third-party-schdoc-03`, `altium-third-party-schdoc-04`, `altium-third-party-schdoc-05`, `altium-third-party-schdoc-06`, `altium-third-party-schdoc-07`, `altium-third-party-schdoc-08`, `altium-third-party-schdoc-09`, `altium-third-party-schdoc-10`, `altium-third-party-schdoc-11`, `altium-third-party-schdoc-12`, `altium-third-party-schdoc-13`.

Per row: issue codes and the number of streams whose rebuilt bytes differ from the bytes read.

| row | issues | identity mismatches |
|---|---|---|
| `altium-third-party-schdoc-01` | none | 0 |
| `altium-third-party-schdoc-02` | none | 0 |
| `altium-third-party-schdoc-03` | none | 0 |
| `altium-third-party-schdoc-04` | `altium.sch.unknown-record` 1 | 0 |
| `altium-third-party-schdoc-05` | none | 0 |
| `altium-third-party-schdoc-06` | none | 0 |
| `altium-third-party-schdoc-07` | none | 0 |
| `altium-third-party-schdoc-08` | none | 0 |
| `altium-third-party-schdoc-09` | none | 0 |
| `altium-third-party-schdoc-10` | `altium.sch.unknown-record` 1 | 0 |
| `altium-third-party-schdoc-11` | `altium.sch.unknown-record` 2 | 0 |
| `altium-third-party-schdoc-12` | none | 0 |
| `altium-third-party-schdoc-13` | `altium.sch.unknown-record` 1 | 0 |

### Totals

| item | count |
|---|---|
| files | 13 |

**form**: `binary` 13

**header**: `schematic-binary` 13

**weight**: `Additional: WEIGHT absent` 2, `Additional: WEIGHT agrees` 11, `WEIGHT agrees` 13

**storage**: `embedded file` 7

**key case**: `mixed-case` 98226, `upper-case` 37433

**lengths**: `lengths` 25809, `lengths not exact in nm` 86, `lengths with a fraction` 289

**fraction signs**: `+/+` 289

**text**: `non-ASCII value` 734, `twin different` 514, `twin equal` 220

**binary pin strings**: none

**binary pin tails**: none

**issues**: `altium.sch.unknown-record` 5

**unknown record ids**: `209` 6, `225` 9

### Streams

| stream | count | bytes |
|---|---|---|
| `Additional` | 13 | 44706 |
| `FileHeader` | 13 | 2106214 |
| `Storage` | 13 | 93752 |

### Records by id

| record id | count |
|---|---|
| 1 | 211 |
| 2 | 886 |
| 4 | 239 |
| 6 | 410 |
| 7 | 23 |
| 8 | 17 |
| 11 | 4 |
| 12 | 66 |
| 13 | 289 |
| 14 | 49 |
| 15 | 28 |
| 16 | 191 |
| 17 | 269 |
| 18 | 57 |
| 22 | 39 |
| 25 | 261 |
| 27 | 684 |
| 28 | 3 |
| 29 | 207 |
| 30 | 10 |
| 31 | 13 |
| 32 | 28 |
| 33 | 28 |
| 34 | 211 |
| 39 | 7 |
| 41 | 5995 |
| 43 | 62 |
| 44 | 211 |
| 45 | 410 |
| 46 | 410 |
| 47 | 39 |
| 48 | 410 |
| 209 | 6 |
| 215 | 23 |
| 216 | 98 |
| 217 | 23 |
| 218 | 77 |
| 225 | 9 |

### Unknown keys by record id

| record id | keys and counts |
|---|---|
| 1 | `ALLPINCOUNT` 161, `COMPONENTKINDVERSION2` 11, `ITEMGUID` 32, `REVISIONGUID` 32, `SYMBOLITEMGUID` 32, `SYMBOLREVISIONGUID` 32, `SYMBOLVAULTGUID` 32, `VAULTGUID` 32 |
| 2 | `DESIGNATOR_CUSTOMFONTID` 59, `NAME_CUSTOMFONTID` 62, `PINDESIGNATOR_POSITIONCONGLOMERATE` 59, `PINNAME_POSITIONCONGLOMERATE` 62, `PINPROPAGATIONDELAY` 655, `SYMBOL_LINEWIDTH` 6 |
| 6 | `LINESTYLEEXT` 6 |
| 30 | `ORIENTATION` 2 |
| 31 | `FILEVERSIONINFO` 7, `REFERENCEZONESTYLE` 1 |
| 34 | `JUSTIFICATION` 6 |
| 41 | `JUSTIFICATION` 54 |
| 43 | `STYLE` 6 |
| 45 | `MODELITEMGUID` 75, `MODELREVISIONGUID` 75, `MODELVAULTGUID` 75 |
| 209 | `ALIGNMENT` 6, `AREACOLOR` 6, `AUTHOR` 6, `CLIPTORECT` 6, `CORNER.X` 6, `CORNER.Y` 6, `FONTID` 6, `ISSOLID` 6, `LOCATION.X` 6, `LOCATION.Y` 6, `SHOWBORDER` 6, `TEXT` 6, `TEXTMARGIN` 6, `WORDWRAP` 6 |
| 217 | `ISMIRRORED` 1, `JUSTIFICATION` 1, `NOTAUTOPOSITION` 3 |
| 225 | `AREACOLOR` 9, `COLOR` 9, `CORNER.X` 9, `CORNER.Y` 9, `LINESTYLE` 9, `LINESTYLEEXT` 9, `LOCATION.X` 9, `LOCATION.Y` 9, `LOCATIONCOUNT` 9, `X1` 9, `X2` 9, `X3` 9, `X4` 9, `Y1` 9, `Y2` 9, `Y3` 9, `Y4` 9 |

### Owners by record id

| record id | counts |
|---|---|
| 1 | `at root` 211, `without OWNERINDEX` 211 |
| 2 | `with OWNERINDEX` 886, `with owner` 886 |
| 4 | `at root` 26, `with OWNERINDEX` 213, `with owner` 213, `without OWNERINDEX` 26 |
| 6 | `at root` 14, `with OWNERINDEX` 396, `with owner` 396, `without OWNERINDEX` 14 |
| 7 | `with OWNERINDEX` 23, `with owner` 23 |
| 8 | `with OWNERINDEX` 17, `with owner` 17 |
| 11 | `with OWNERINDEX` 4, `with owner` 4 |
| 12 | `with OWNERINDEX` 66, `with owner` 66 |
| 13 | `with OWNERINDEX` 289, `with owner` 289 |
| 14 | `at root` 3, `with OWNERINDEX` 46, `with owner` 46, `without OWNERINDEX` 3 |
| 15 | `at root` 28, `without OWNERINDEX` 28 |
| 16 | `with OWNERINDEX` 191, `with owner` 191 |
| 17 | `at root` 269, `without OWNERINDEX` 269 |
| 18 | `at root` 57, `without OWNERINDEX` 57 |
| 22 | `at root` 39, `without OWNERINDEX` 39 |
| 25 | `at root` 261, `without OWNERINDEX` 261 |
| 27 | `at root` 684, `without OWNERINDEX` 684 |
| 28 | `at root` 2, `with OWNERINDEX` 1, `with owner` 1, `without OWNERINDEX` 2 |
| 29 | `at root` 207, `without OWNERINDEX` 207 |
| 30 | `at root` 1, `with OWNERINDEX` 9, `with owner` 9, `without OWNERINDEX` 1 |
| 31 | `at root` 13, `without OWNERINDEX` 13 |
| 32 | `with OWNERINDEX` 28, `with owner` 28 |
| 33 | `with OWNERINDEX` 28, `with owner` 28 |
| 34 | `with OWNERINDEX` 211, `with owner` 211 |
| 39 | `at root` 7, `without OWNERINDEX` 7 |
| 41 | `at root` 410, `with OWNERINDEX` 5585, `with owner` 5585, `without OWNERINDEX` 410 |
| 43 | `at root` 62, `without OWNERINDEX` 62 |
| 44 | `with OWNERINDEX` 211, `with owner` 211 |
| 45 | `with OWNERINDEX` 410, `with owner` 410 |
| 46 | `with OWNERINDEX` 410, `with owner` 410 |
| 47 | `with OWNERINDEX` 39, `with owner` 39 |
| 48 | `with OWNERINDEX` 410, `with owner` 410 |
| 209 | `at root` 6, `without OWNERINDEX` 6 |
| 215 | `at root` 23, `without OWNERINDEX` 23 |
| 216 | `with OWNERINDEX` 66, `with owner` 98, `without OWNERINDEX` 32 |
| 217 | `with OWNERINDEX` 14, `with owner` 23, `without OWNERINDEX` 9 |
| 218 | `at root` 77, `without OWNERINDEX` 77 |
| 225 | `at root` 9, `without OWNERINDEX` 9 |

## Tag `altium-schlib`

Rows (9): `altium-third-party-schlib-01`, `altium-third-party-schlib-02`, `altium-third-party-schlib-03`, `altium-third-party-schlib-04`, `altium-third-party-schlib-05`, `altium-third-party-schlib-06`, `altium-third-party-schlib-07`, `altium-third-party-schlib-08`, `altium-third-party-schlib-09`.

Per row: issue codes and the number of streams whose rebuilt bytes differ from the bytes read.

| row | issues | identity mismatches |
|---|---|---|
| `altium-third-party-schlib-01` | `altium.sch.unknown-stream` 1, `altium.schlib.side-stream-opaque` 2 | 0 |
| `altium-third-party-schlib-02` | `altium.sch.unknown-stream` 1, `altium.schlib.side-stream-opaque` 1 | 0 |
| `altium-third-party-schlib-03` | `altium.sch.unknown-stream` 3, `altium.schlib.side-stream-opaque` 3 | 0 |
| `altium-third-party-schlib-04` | `altium.sch.unknown-stream` 18, `altium.schlib.side-stream-opaque` 18 | 0 |
| `altium-third-party-schlib-05` | `altium.sch.unknown-stream` 10, `altium.schlib.side-stream-opaque` 20 | 0 |
| `altium-third-party-schlib-06` | `altium.sch.unknown-stream` 50, `altium.schlib.side-stream-opaque` 53 | 0 |
| `altium-third-party-schlib-07` | `cfb.note.entry-fields` 1 | 0 |
| `altium-third-party-schlib-08` | `altium.sch.unknown-stream` 16, `altium.schlib.side-stream-opaque` 17, `cfb.note.entry-fields` 1 | 0 |
| `altium-third-party-schlib-09` | `altium.schlib.side-stream-opaque` 6, `cfb.note.entry-fields` 1 | 0 |

### Totals

| item | count |
|---|---|
| components | 169 |
| files | 9 |
| section keys | 6 |

**form**: `library` 9

**header**: `library` 9

**weight**: `COMPCOUNT agrees` 9, `WEIGHT agrees` 9

**storage**: none

**name list**: `absent` 9

**side streams**: `PinFrac` 2, `PinSymbolLineWidth` 99, `PinTextData` 21

**key case**: `mixed-case` 8467, `upper-case` 14389

**lengths**: `lengths` 4599, `lengths not exact in nm` 67, `lengths with a fraction` 93, `pins with PinFrac` 8

**fraction signs**: `+/+` 72, `-/-` 21

**text**: `non-ASCII value` 193, `twin different` 188, `twin equal` 5

**binary pin strings**: `5` 1201

**binary pin tails**: `without tail` 1201

**issues**: `altium.sch.unknown-stream` 99, `altium.schlib.side-stream-opaque` 120, `cfb.note.entry-fields` 3

**unknown record ids**: none

### Streams

| stream | count | bytes |
|---|---|---|
| `<component>/Data` | 169 | 397665 |
| `<component>/PinFrac` | 2 | 307 |
| `<component>/PinPackageLength` | 99 | 46567 |
| `<component>/PinSymbolLineWidth` | 99 | 49090 |
| `<component>/PinTextData` | 21 | 4905 |
| `FileHeader` | 9 | 18836 |
| `SectionKeys` | 3 | 582 |
| `Storage` | 9 | 225 |

### Records by id

| record id | count |
|---|---|
| 1 | 169 |
| 2 | 1201 |
| 4 | 79 |
| 6 | 339 |
| 7 | 10 |
| 8 | 51 |
| 11 | 10 |
| 12 | 77 |
| 13 | 84 |
| 14 | 195 |
| 34 | 169 |
| 41 | 514 |
| 44 | 169 |
| 45 | 183 |
| 46 | 183 |
| 48 | 183 |

### Unknown keys by record id

| record id | keys and counts |
|---|---|
| 1 | `ALLPINCOUNT` 162, `COMPONENTKINDVERSION2` 2 |
| 41 | `JUSTIFICATION` 40 |

### Owners by record id

| record id | counts |
|---|---|
| 1 | `at root` 169, `without OWNERINDEX` 169 |
| 2 | `with owner` 1201, `without OWNERINDEX` 1201 |
| 4 | `with owner` 79, `without OWNERINDEX` 79 |
| 6 | `with owner` 339, `without OWNERINDEX` 339 |
| 7 | `with owner` 10, `without OWNERINDEX` 10 |
| 8 | `with owner` 51, `without OWNERINDEX` 51 |
| 11 | `with owner` 10, `without OWNERINDEX` 10 |
| 12 | `with owner` 77, `without OWNERINDEX` 77 |
| 13 | `with owner` 84, `without OWNERINDEX` 84 |
| 14 | `with owner` 195, `without OWNERINDEX` 195 |
| 34 | `with owner` 169, `without OWNERINDEX` 169 |
| 41 | `with OWNERINDEX` 6, `with owner` 514, `without OWNERINDEX` 508 |
| 44 | `with owner` 169, `without OWNERINDEX` 169 |
| 45 | `with OWNERINDEX` 183, `with owner` 183 |
| 46 | `with OWNERINDEX` 183, `with owner` 183 |
| 48 | `with OWNERINDEX` 183, `with owner` 183 |
