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

- [x] 1.5 Preserve zero-height TrueType ordinary footprint texts when converting to Altium, as in the
  two omitted records of public row `-08` (S-0187). Proof:
  `uv run pytest tests/unit/convert/test_truetype_kicad_c0460.py tests/unit/backends/altium/test_pcb_text.py -n 0`.

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

- [x] 2.5 Empty texts and line breaks (row `-08` at bbe4c452b: 2 671 of 2 724 members came back, its
  51 empty member texts refused; its 13 texts with CR LF left out). The writer writes an empty text and a
  line feed as CR LF; the ledgers of CM5_MINIMA_3, complex_hierarchy and seven other public boards lose
  their empty-text and line-break rows (texts whose justification has no key move to that row). Proof:
  `uv run pytest tests/unit/backends/altium/test_pcb_text.py -n 0` and
  `uv run pytest tests/corpus/test_convert_census.py -k "explained or not_written"`.

- [x] 2.6 A straight member arc (row `-08`: one arc of each of the unions 0x4E and 0x59, sweep under
  0.2 degree, comes back from KiCad with collinear points and is written as a track, change c0435) keeps
  its union on that track. Proof:
  `uv run pytest tests/unit/convert/test_altium_unions.py -n 0 -k straight`.

## 3. Evidence and docs

- [x] 3.1 Census of union members, smart unions and TrueType texts in the public rows (S-2190); rows in
  `pcb-records.md`, `docs/hypotheses.md`, CHANGELOG; `uv run pytest tests/unit/test_format_facts.py`.

## 4. Kit

- [x] 4.1 altium-rounds-2 opens the round trips of rows `-01` and `-04`: Altium lists the source's union
  and TrueType texts (S-2191). Row `-04` at 332b79837: unions and TrueType texts identical, stroke
  `FONTNAME` lost (task 1.4); row `-01` open. Row `-07` at 332b79837: 47 union members became 0 (task 2.4).
  Row `-08` at bbe4c452b: TrueType texts 857 became 1081 and texts 1742 became 1917. No text changes font
  type: the source holds 241 texts on long mechanical ids (239 TrueType on Mechanical 20, 2 on Mechanical
  21) that Altium does not count, and the writer puts them on Mechanical 16, where it does (c0450, long
  mechanical ids). The written document holds 1081 TrueType records against the source's 1096: 13 texts with
  CR LF (task 2.5) and 2 footprint texts. Closes with c0450, not here.
  Deferred to v0.8 (coordinator, 2026-11-07): not run before the cut of 0.7.0; the code ships.

  Altium 24.5.2.23 follow-up, 2026-11-10: both direct round trips opened. Row `-01` kept one
  TrueType text and one region member of union 1. Row `-04` kept 18 TrueType texts and 22 via members
  with the same union indices. Row `-08` kept 1,742 native text objects, of which 859 were TrueType
  including two of size zero. It kept 312 text union members and 2,412 other members by union index;
  one arc each in unions 78 and 89 came back as a track, as task 2.6 describes. The strict reader
  counted 1,098 TrueType records in each file of row `-08`. The font type, name and flag census and
  the UnionNames and EmbeddedFonts6 storage bytes matched for all three rows. The script ran on
  copies, with SHA-256 checks before and after. Native TSV SHA-256:
  `a07fda29f89a07cca0417e835a0833e6199140792a16a6d55b1c7c10e4664d5e`.
