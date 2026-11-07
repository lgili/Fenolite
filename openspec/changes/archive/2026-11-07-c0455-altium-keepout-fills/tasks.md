# Tasks: c0455

## 1. Marker

- [x] 1.1 `keepout_lines` parses, checks and gives back a keep-out fill marker;
  `uv run pytest tests/unit/backends/altium/test_keepout_fills.py -k marker`.

## 2. Import and conversion

- [x] 2.1 The import records a keep-out fill of copper in its area's bag, and the conversion to KiCad names
  the area; `uv run pytest tests/unit/backends/altium/test_keepout_fills.py -k kicad`.

## 3. Writer

- [x] 3.1 `fill_record` writes the keep-out flag and the restriction byte, and the writer gives a marked
  area back as a keep-out fill, free or of its component;
  `uv run pytest tests/unit/backends/altium/test_keepout_fills.py`.

## 4. Evidence and docs

- [x] 4.1 Round trip of public row `-08`: keep-out fills before and after (S-2140); rows in
  `pcb-records.md` and `import.md`, and a CHANGELOG line; `uv run pytest tests/unit/test_format_facts.py`.
- [x] 4.2 altium-rounds-2 opens the round trip of row `-08` in Altium Designer: the 11 keep-out fills of
  its components on the bottom layer with their restrictions, as in the source (kit request).
