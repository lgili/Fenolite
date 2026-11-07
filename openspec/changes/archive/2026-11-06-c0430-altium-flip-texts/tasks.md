## 1. Evidence

- [x] 1.1 `docs/evidence/sources.md`: S-1890 (the J9 run in Altium Designer 24.5), S-1891 (census of the long
  layer id of texts and pads in the eight public documents), S-1892 (Altium's J9 save against Fenolite's flip).
  `pcb-records.md` "Long layer ids of texts and pads", a `pcb-document.md` row and the status of
  `H-A-EDIT-FLIP`. Proof: `uv run pytest tests/unit/test_legal_docs.py tests/unit/test_format_facts.py -q`.

## 2. Edit session

- [x] 2.1 `edit.records`: `LONG_LAYER` rows for the text (232, 226) and the pad (170, 114), and `SHORT_FORM`
  rows for the forms Fenolite writes (137, 114). The docstrings of `relayer` and `remap_layer` are updated.
  Proof: `uv run pytest tests/unit/backends/altium/edit/test_flip_texts.py tests/unit/backends/altium/edit/test_ops.py -q`.

## 3. Writers

- [x] 3.1 A test that the Altium write of a bottom part puts its designator and comment on Bottom Overlay,
  mirrored, and a top part's on Top Overlay. The KiCad side is pinned by `test_embed_fields.py::test_bottom_side`.
  Proof: `uv run pytest tests/unit/backends/altium/edit/test_flip_texts.py -k written -q`.

## 4. Kit

- [x] 4.1 Write `flip.PcbDoc` (case J9's session), `c0430-top-to-bottom.PcbDoc` (`D1` and `R1`) and
  `c0430-bottom-to-top.PcbDoc` (`D1` of Altium's J9 save) from the phase A saves, outside the repository, for
  the VM agent's check. Proof: the files read back with both texts of each flipped part on the overlay of
  its side, by layer byte and long id.

## 5. Mechanical pairs and the DSL path

- [x] 5.1 `ops.mechanical_pairs`, `ops.flip_layers`, `ops.layer_of` and `ops.relayer_long`: the flip swaps
  only declared mechanical pairs, by long layer id. Proof:
  `uv run pytest tests/unit/backends/altium/edit/test_flip_texts.py -k mechanical -q`.
- [x] 5.2 A test that `fenolite build --target altium` of the routed blink writes `D1` (`side="bottom"`) with
  its designator and comment on Bottom Overlay, mirrored. Source S-1893 and the rows in `pcb-records.md` and
  `pcb-document.md`. Proof: `uv run pytest tests/unit/cli/test_build_altium_bottom_texts.py -q`.
