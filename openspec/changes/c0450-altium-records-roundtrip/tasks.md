# Tasks: c0450

## 1. Fills

- [x] 1.1 `pcbrecords.fill_record` in the 50-byte form; read back by Fenolite's reader;
  `uv run pytest tests/unit/backends/altium/test_fill_records.py -k record`.
- [x] 1.2 The conversion tags the uuid of a fill, and the writer writes a tagged rectangle as a fill;
  `uv run pytest tests/unit/backends/altium/test_fill_records.py`.

## 2. Storages

- [x] 2.1 The conversion to KiCad writes the carried storages as board properties and counts the
  index-bound ones lost; `uv run pytest tests/unit/convert/test_altium_storages.py -k kicad`.
- [x] 2.2 The conversion to Altium writes the carried storages back;
  `uv run pytest tests/unit/convert/test_altium_storages.py`.

## 3. Flagged keep-out strokes

- [x] 3.1 Census of the bytes after 36 of the long track form and after 47 of the long arc form on the
  public rows (S-2093).
- [x] 3.2 The marker carries the keep-out flag and the restriction byte, and the writer writes a flagged
  stroke back as a flagged track or arc; `uv run pytest tests/unit/backends/altium/test_keepout_lines.py`.

## 4. Evidence and docs

- [x] 4.1 Round trip of public rows `-01`, `-02`, `-04`, `-06` and `-08`: storage diff before and after
  (S-2090). Rows in `pcb-records.md` and `board.md`, and a CHANGELOG line.
  `uv run pytest tests/unit/test_format_facts.py`.
- [ ] 4.2 altium-rounds-2 opens the round trip of row `-01` and of row `-08` in Altium Designer: fills,
  unions, fonts and component classes as in the source (kit request).
- [ ] 4.3 KiCad 9.0.9 keeps the board properties on a save (maintainer's run).
