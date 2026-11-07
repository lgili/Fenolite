# Tasks: c0464

## 1. Diagnosis

- [x] 1.1 Census of the `Board6` keys, display units, mechanical names and super classes of public rows
  `-01` to `-08` (S-2231). Proof: the scratch scripts' key census.
- [x] 1.2 The writer's `Board6` lines follow Altium's one for one; the mechanical ids come back right and
  their names are the KiCad layer names. Proof: `docboard.board_records` against row `-01`.

## 2. Carrier

- [x] 2.1 `altium_storages` carries `Board6.Settings` (anchored runs of the keys `docboard.OWNED_KEY` does
  not name, and the mechanical names). Proof:
  `uv run pytest tests/unit/convert/test_board6_settings_c0464.py -n 0 -k carries`.

## 3. Writer

- [x] 3.1 `docboard.with_settings` merges the carried fields; `pcbdoc` takes `Board6.Settings` from the kept
  storages. Proof: `uv run pytest tests/unit/convert/test_board6_settings_c0464.py -n 0 -k merge`.
- [x] 3.2 Mechanical names by layer: `lower.named_mechanical`, `PcbDocSpec.named_layers`. Proof:
  `uv run pytest tests/unit/convert/test_board6_settings_c0464.py -n 0 -k mechanical`.

## 4. Flow A

- [x] 4.1 Authored reproductions through flow A (import, build, convert back): the metric document with a
  0.025 mm rule, the document with Altium's default mechanical names, and the black solder mask (S-2232,
  S-2234). Proof:
  `uv run pytest tests/unit/convert/test_board6_settings_c0464.py -n 0 -k flow`.

## 6. Empty mechanical slots

- [x] 6.1 Carry the enabled flags of mechanical layers 1 to 16 with their names; a slot that nothing lies on
  takes the source's flag, and a slot no primitive lies on its name (S-2235, S-2236). Proof:
  `uv run pytest tests/unit/convert/test_board6_settings_c0464.py -n 0 -k empty_slots`.
- [x] 6.2 A drawing on the KiCad row `Altium.DrillDrawing` or `Altium.DrillGuide` goes back to layer 73 or
  55 (`lower.drill_rows`). Proof: `uv run pytest tests/unit/convert/test_board6_settings_c0464.py -n 0 -k drill`.
- [x] 6.3 Rows `-02`, `-04` and `-06` through flow A give every slot's name and flag back, and row `-02`'s
  drill drawing text on layer 73 (S-2236). Proof: the scratch slot census against the cached corpus.
- [x] 6.4 A model body, and a footprint's generated model whose bodies share a layer, goes back on its source
  body's mechanical layer (`models.read_layers`), so row `-05`'s Mechanical 13 and row `-01`'s Mechanical 14
  stay disabled (S-2284). Proof:
  `uv run pytest tests/unit/convert/test_board6_settings_c0464.py -n 0 -k "layer_of_model or body_layer"`.

## 5. Evidence and docs

- [x] 5.1 Row in `pcb-records.md`, H-A-CONV-BOARD6, S-2230 to S-2233, CHANGELOG.
- [ ] 5.2 Kit: Altium opens the flow A round trip of the maintainer's board and of row `-04` with metric
  units, the source's mechanical names and enabled flags, row `-05` with its black mask, and no error; it reports whether the super classes come back
  (S-2233, asked of altium-rounds-2).
