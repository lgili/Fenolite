# Tasks: c0460

## 1. TrueType texts

- [x] 1.1 The import gives a text of font type 1 its font name as `face`, with bold and italic (free texts,
  footprint texts, fields); `uv run pytest tests/unit/backends/altium/test_truetype_texts.py`.
- [x] 1.2 The writer writes a text or field with a face as font type 1 with its name, bold and italic;
  `text_problem_of` no longer refuses it; same proof.
- [x] 1.3 The conversion back to Altium keeps a text's font. The KiCad reader left `face`, `bold` and
  `italic` in the text's slots (change c0277), so a round trip through KiCad wrote stroke texts. Chosen
  (coordinator, 2026-11-06): the KiCad reader projects them for a text whose font names a face (board
  texts, footprint texts, fields); a stroke text keeps them in its slots and its canonical JSON. Proof:
  `uv run pytest tests/unit/convert/test_truetype_kicad_c0460.py tests/unit/backends/altium/test_truetype_texts.py -n 0`.

- [x] 1.4 A stroke text keeps the font its record names (S-2253; the round trip of row `-04` wrote
  `FONTNAME` '' on its 15 stroke comments, S-2191): the import keeps the name, bold and italic in the
  text's `altium` bag (`stroke_font`), the conversion to KiCad carries them by KiCad uuid as
  `Fenolite.Altium.StrokeFonts`, and the writer writes them in the stroke text's record. Proof:
  `uv run pytest tests/unit/convert/test_stroke_fonts_c0460.py -n 0`.

## 2. Union members

- [x] 2.1 The import records a via's, region's and component's non-zero union index in its `altium` bag;
  `uv run pytest tests/unit/convert/test_altium_unions.py`.
- [x] 2.2 The writer writes `PcbDocSpec.unions` into via, region and component records; same proof.
- [x] 2.3 The conversion carries `Fenolite.Altium.UnionMembers` by KiCad uuid and gives the members their
  index back; `SmartUnions` is frame-bound; same proof and
  `uv run pytest tests/unit/convert/test_altium_storages.py`.

- [x] 2.4 Track and arc members (the VM finding at 332b79837: row `-07`'s 5 unions lost their 47 members,
  27 tracks and 20 arcs; S-2190). The import reads a track's index at 36 and an arc's at 48, the carrier
  and the writer take tracks, arcs and every graphic, the writer writes a member in the long form, and the
  import to Python renames the copper uuids of a carried property to the build's (flow A lost `-04`'s 22
  vias the same way). Texts too (row `-08`, VM at 332b79837: 41 unions of 2724 members became 4 of 434):
  a free text holds its index at 119 of its first subrecord, a member component's designator and comment
  hold the component's; the import to Python maps board texts and graphics to the build's uuids (row `-01`'s
  region union, lost by flow A at 60687e26d), and the stroke-font
  carrier keys a member text by its marked uuid. Footprint tracks of a union (`-03` 4, `-06` 80) stay out;
  through flow A a member footprint (with its designator and comment) and the stroke fonts of footprint
  fields are still lost: the build gives footprints uuids the import does not map.
  Proof:
  `uv run pytest tests/unit/convert/test_altium_unions.py -n 0`.

## 3. Evidence and docs

- [x] 3.1 Census of union members, smart unions and TrueType texts in the public rows (S-2190); rows in
  `pcb-records.md`, `docs/hypotheses.md`, CHANGELOG; `uv run pytest tests/unit/test_format_facts.py`.

## 4. Kit

- [ ] 4.1 altium-rounds-2 opens the round trips of rows `-01` and `-04`: Altium lists the source's union
  and TrueType texts (S-2191). Row `-04` at 332b79837: unions and TrueType texts identical, stroke
  `FONTNAME` lost (task 1.4); row `-01` open. Row `-07` at 332b79837: 47 union members became 0 (task 2.4).
