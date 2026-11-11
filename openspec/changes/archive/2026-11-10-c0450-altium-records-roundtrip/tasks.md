# Tasks: c0450

## 1. Fills

- [x] 1.1 `pcbrecords.fill_record` in the 50-byte form; read back by Fenolite's reader;
  `uv run pytest tests/unit/backends/altium/test_fill_records.py -k record`.
- [x] 1.2 The conversion tags the uuid of a fill, and the writer writes a tagged rectangle as a fill;
  `uv run pytest tests/unit/backends/altium/test_fill_records.py`.
- [x] 1.3 A tagged copper fill of no net in a footprint without net ties is a component fill (VM at bbe4c452b:
  row `-04`'s J1 lost its 6 Top Layer fills, which the writer refused as footprint copper); a Fenolite round
  trip of `-04` now keeps 6 of 6. Proof: `uv run pytest tests/unit/backends/altium/test_fill_records.py -n 0`.

- [x] 1.4 Preserve the fill marker on a vendored component graphic during Python build placement,
  including moved-part identity mapping. Proof:
  `uv run pytest tests/unit/backends/altium/test_fill_records.py tests/unit/lens/test_moved.py -n 0`.
  Public row `-04` (S-0199), flow A: the return keeps six unnetted component fills on the top copper
  layer and six on the source solder-mask layer, all on the same component. KiCad 10.0.6 keeps all
  twelve marker UUIDs on a native save. Altium 24.5.2.23 opens both copies and enumerates twelve fills
  in each. The task 4.2 comparisons on rows `-01` and `-08` are separate.

## 2. Storages

- [x] 2.1 The conversion to KiCad writes the carried storages as board properties and counts the
  index-bound ones lost; `uv run pytest tests/unit/convert/test_altium_storages.py -k kicad`.
- [x] 2.2 The conversion to Altium writes the carried storages back;
  `uv run pytest tests/unit/convert/test_altium_storages.py`.
- [x] 2.3 The storages travel with `backends.kicad.boardcarrier` (c0434): one `with_carried` call with the
  rule records, read back with `carried`; `uv run pytest tests/unit/convert/test_altium_storages.py
  tests/unit/convert/test_rule_carrier_c0434.py`.

## 3. Flagged keep-out strokes

- [x] 3.1 Census of the bytes after 36 of the long track form and after 47 of the long arc form on the
  public rows (S-2093).
- [x] 3.2 The marker carries the keep-out flag and the restriction byte, and the writer writes a flagged
  stroke back as a flagged track or arc; `uv run pytest tests/unit/backends/altium/test_keepout_lines.py`.

## 4. Evidence and docs

- [x] 4.1 Round trip of public rows `-01`, `-02`, `-04`, `-06` and `-08`: storage diff before and after
  (S-2090). Rows in `pcb-records.md` and `board.md`, and a CHANGELOG line.
  `uv run pytest tests/unit/test_format_facts.py`.
- [x] 4.2 altium-rounds-2 opens the round trip of row `-01` and of row `-08` in Altium Designer: fills,
  unions, fonts and component classes as in the source (kit request).
  Deferred to v0.8 (coordinator, 2026-11-07): not run before the cut of 0.7.0; the code ships.
  Altium 24.5.2.23 opened both direct returns and enumerated 2 and 43 fills, respectively, as in the
  sources. TrueType counts and union member indices matched. Two near-straight members of row `-08`
  changed from arc to track and kept their union indices, as recorded in c0460 task 2.6. Native
  save-as retained all 27 and 21 ordinary component classes, respectively, with the same members
  (S-2292). The inputs' hashes were unchanged. The native object TSV SHA-256 was
  `a07fda29f89a07cca0417e835a0833e6199140792a16a6d55b1c7c10e4664d5e`.
- [x] 4.3 KiCad 9.0.9 keeps the board properties on a save (maintainer's run).
  Deferred to v0.8 (coordinator, 2026-11-07): not run before the cut of 0.7.0; the code ships.
  Done 2026-11-07 at the coordinator's word (S-2280): 9.0's `kicad-cli` has no `pcb upgrade`, so the board code of
  the pinned 9.0.9 image saved it (`pcbnew.LoadBoard`, `pcbnew.SaveBoard`). The KiCad 9 leg of row `-01`,
  converted at `d721893cd`, keeps its eleven `Fenolite.Altium.*` properties byte for byte, after `setup` and
  sorted by name. `H-K-FENOLITE-PROPS` is `KICAD-VERIFIED (9.0.x, 10.0.x)`.
- [x] 4.4 Mechanical layers above 16 keep their long id: a track, an arc or a fill with the layer byte of
  Mechanical 16 and the long id of Mechanical 17 to 32 comes back from KiCad with that byte and long id, and
  the layer's `LAYERV7_<i>` name and flag come back (S-2282);
  `uv run pytest tests/unit/convert/test_long_mechanical_c0450.py -n 0`.
- [x] 4.6 Lines and arcs of width 0 on a mechanical layer are written with width 0 (row `-01`: 68 tracks and
  1 arc of components on Mechanical 1, S-2286); copper and every other layer keep the refusal;
  `uv run pytest tests/unit/convert/test_zero_width_mechanical_c0450.py -n 0`.
- [x] 4.5 Texts on Mechanical 17 to 32 keep their long id: a text with the byte 72 and the long id of
  Mechanical 17 to 32 at 226 comes back from KiCad in the source's form with that id
  (`Fenolite.Altium.TextTails`, S-2285); every other text keeps the 137-byte form;
  `uv run pytest tests/unit/convert/test_long_mechanical_c0450.py -n 0`.
