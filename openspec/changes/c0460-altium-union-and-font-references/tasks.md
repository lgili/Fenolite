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

## 2. Union members

- [x] 2.1 The import records a via's, region's and component's non-zero union index in its `altium` bag;
  `uv run pytest tests/unit/convert/test_altium_unions.py`.
- [x] 2.2 The writer writes `PcbDocSpec.unions` into via, region and component records; same proof.
- [x] 2.3 The conversion carries `Fenolite.Altium.UnionMembers` by KiCad uuid and gives the members their
  index back; `SmartUnions` is frame-bound; same proof and
  `uv run pytest tests/unit/convert/test_altium_storages.py`.

## 3. Evidence and docs

- [x] 3.1 Census of union members, smart unions and TrueType texts in the public rows (S-2190); rows in
  `pcb-records.md`, `docs/hypotheses.md`, CHANGELOG; `uv run pytest tests/unit/test_format_facts.py`.

## 4. Kit

- [ ] 4.1 altium-rounds-2 opens the round trips of rows `-01` and `-04`: Altium lists the source's union
  and TrueType texts (S-2191).
