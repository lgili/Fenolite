## Outcome in one paragraph

**Write pins as Altium saves them, and read both forms as Altium shows them.** Every pin the writers write holds bit 0x20 of `PINCONGLOMERATE`, with 0x08 and 0x10 as show flags. The reader takes the two bits as show flags with 0x20 and as hide flags without it. The model's meaning (what a symbol shows) is untouched; only the encoding changes, in one property of one class.

## Context

- **Where the bits are made.** `altsym.AltiumPin.conglomerate` is the one place: `schdoc` writes it as the text key, `schlib.pin_record` as the byte of the binary pin, for generic bodies (`from_generic`) and for KiCad symbols (`map_pin`) alike. `map_pin` takes visibility from `SymbolDef.pin_names_hidden`, `pin_numbers_hidden` and the name; `from_generic` from `GenericPin.name_shown`. No other module of `src/` writes or reads the two bits, and the KiCad backend never sees them.
- **Where they are read.** `read.sch.records.Pin.name_shown` and `designator_shown` (text and binary pins alike); `direction` and `hidden` use bits 0-2. The adapter maps neither attribute into the model (`adapter/library.py` keeps `hidden` alone), so the import's model does not depend on them.
- **The catalog rule of c0134** estimates the pin texts the model means to show. It reads no Altium bit, so it is unchanged; with this change Altium shows what it measures.
- **The fact rows** (`schematic-library.md`, `schematic-ascii.md`) said, `INFERRED` from S-0130 and S-0131, that 0x08 shows the name and 0x10 the number, without a condition on 0x20.

## The evidence

1. **Author report, files of 0.2.x (S-0612).** The LED of the kit sample `flat`, written with 18 and 16 (0x10 set, 0x08 clear), showed both names and hid both numbers; `Mini:Mini_LED`, written with 2 and 0, showed both. So without 0x20 the two bits hide. One report; four values.
2. **Corpus census (S-0614), measured 2026-10-08 with Fenolite's own reader.** All 4 175 pins of the Altium-saved schematics (2 974 in 36 documents) and libraries (1 201 in 9) hold 0x20. In the documents:

   | owner | neither | 0x10 only | 0x08 only | both |
   |---|---|---|---|---|
   | at most 3 pins | 1 233 | 105 | 17 | 12 |
   | more than 3 pins | 47 | 77 | 69 | 1 414 |

   Small parts (resistors and capacitors with pins named `1` and `2`) hold neither bit, larger ones (pins named `VCC`, `EN`) both. Read as show flags that is the usual convention; read as hide flags it would show the numbered pin names of every resistor and hide every IC's texts. The census therefore contradicts a plain flip of the reader.
3. **Author report, check project (S-0613).** `tests/data/altium/pinbits/` holds the catalog LED four times with every pin at 0x20 plus 0, 0x10, 0x08 and 0x18. Altium Designer Professional 26.5.0 showed neither text, the numbers only, the names only, and both: the bits are show flags with 0x20.

The 0x20-set reading rests on S-0613 (`ALTIUM-VERIFIED(author-report)`), on the corpus (`CORPUS-VERIFIED`, the counts above) and on S-0130/S-0131. The 0x20-clear reading rests on S-0612 alone, one author report on the values 0, 2, 16 and 18. What 0x20 means by itself is not claimed; only how the two bits read with and without it.

## Decisions

1. **Write 0x20 on every pin, with show flags** (option B of the investigation). The alternative, keeping 0x20 clear and writing hide flags, matched the first report but no Altium-saved file, and KiCad's importer (S-0131, measured with `kicad-cli` 10.0.6 on pins without 0x20) reads the bits as show flags, so it would have shown the opposite of Altium. With 0x20 and show flags, Altium (S-0613), the corpus and KiCad's reader agree.
2. **One constant.** `altsym.SHOW_FLAGS = 0x20`, added in `AltiumPin.conglomerate`; the reader has its own `records.SHOW_FLAGS` (the reader package does not import the writer). `schlib.EVIDENCE` names `H-A-SCHLIB-PINBITS`, since every `H-A-SCHLIB-` row is a claim of the build; the module's level stays `INFERRED`.
3. **The reader follows Altium for both forms.** `name_shown = bool(c & 0x08) == bool(c & 0x20)`, the same for `designator_shown` with 0x10. Fenolite's own files of earlier releases are the only known pins without 0x20; without this rule a reader would report their pins as showing what Altium hides.
4. **Samples are written again by their own tools** (the golden tests' write mode, `channels/two/author.py`, the generic copies by the same build the test runs). Each changed file is compared with its former bytes record by record (`tests/_pin_bits.py::pin_bits_only`): equal but for 0x20 on each pin. `test_altium_samples_of_earlier_changes_keep_their_bytes` uses that comparison for the schematic files of the samples of earlier changes and for the copies under `generic/`, which can no longer be the bytes of commit 6cdf0aea.
5. **Pins**: the ten `ALTIUM` entries of `test_build_bytes_pinned.py` move with the reason beside each. Measured against builds with the base code: per design the schematic document and library change (pin bit alone) and `.fenolite/build.json` names their new digests; no other file changes. No KiCad pin moves.
6. **The check project is a committed sample** with its `author.py`: the writer's own `write_project` with a pin class whose conglomerate is set per variant, and free texts given as a `schdoc.Frame`. Its bytes do not depend on `AltiumPin.conglomerate`, so they are the bytes the maintainer opened.
7. **Pages that name the maintainer's folders keep their digests**: those files are what he was given. Tables of committed files carry the new digests. The short set of Part X (built in its test) carries the new digests, with a line saying that the folder holds the former ones.

## Tests

- `tests/unit/backends/altium/test_pinbits.py`: the check project equals what `author.py` writes; its four variants read back as Altium showed them, in the sheet and the library; the writer's four combinations (name hidden and number shown gives 0x08 clear and 0x10 set, and the reverse) through `pin_record` and the library reader; text pins with and without 0x20.
- Updated with the reason beside each: the worked pin (`test_schlib.py`, `_altium_sch_build.py`), the four-pin part and the edge-code pin (`test_schdoc.py`), the text pin of `test_sch_records.py` (now 62, so that it still reads as shown).
- `tests/unit/lens/test_build_bytes_pinned.py` (ten Altium pins), the golden tests and the protocol tables.

## Released output

Three product files change: `backends/altium/altsym.py`, `backends/altium/read/sch/records.py` and `backends/altium/schlib.py` (its evidence tuple only). Every Altium build writes other schematic bytes; no KiCad module, no model, no design-language and no catalog file is edited.

## Size (design-days)

| group | dd |
|---|---|
| investigation, corpus census, check project | 0.25 |
| writer, reader, tests | 0.25 |
| samples, pins, pages | 0.5 |

Total: 1. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-schematic-writer`: MODIFIED "Generic component bodies" and "Binary pin record" (living requirements; no open change modifies them).
- `altium-schematic-reader`: ADDED "Pin visibility bits".
