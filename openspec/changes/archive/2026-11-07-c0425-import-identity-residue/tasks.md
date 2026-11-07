# Tasks: c0425

## 1. Level 2

- [x] 1.1 `assignment_compare.compare` compares an element with several labels through the labels'
  counterparts; `net_text` prints `no net` for an empty part; `tests/unit/checks/test_assignment_compare.py`.
- [x] 1.2 Authored board with a second pad `1` on no net on `J1` compares equal to itself at level 2;
  `tests/unit/importer/test_open_pad_beside_netted.py -k equal`.

## 2. Import

- [x] 2.1 `emit/design.py` counts a pad on no net beside a netted pad of its number as `pad-net-conflict`;
  `tests/unit/importer/test_open_pad_beside_netted.py`; `docs/import.md`.
- [x] 2.2 `derive_from_model` gives a variant a name no footprint of the board holds;
  `tests/unit/library/test_derive.py`, `tests/unit/importer/test_variant_name_collision.py`;
  `docs/import.md`, `docs/cli-contract.md`.

## 3. Conversion report

- [x] 3.1 A lost `schematic` row explains `ref-ambiguous` at a designator the source circuit holds more
  than once; `tests/unit/convert/test_report.py -k twice`; `docs/conversion.md`.

## 4. Close

- [x] 4.1 CHANGELOG, `docs/equivalence.md`; light checks and focused tests.
- [x] 4.2 The next combined sweep confirms the private cases (L1 `ref-ambiguous`, L2 `net`, the
  `build.unknown-pin` case) are gone (coordinator). The sweep of 2026-11-07 at lote-29 `0a88720c1` (88
  cases): L1 `ref-ambiguous` 0, L2 `net` 0, `build.unknown-pin` 0; the cases import and build; no new
  unexplained code.

## 5. Copper on a net with a slash

- [x] 5.1 The private sweep at 332b79837 refused one board that passed at 5ab9d645 (138 L5 `copper-no-net`,
  1 `import.unequal`) and a second (24): copies × regions per copy of free copper regions on the nets of
  embedded board array copies, `B<k>/<net>`. A target-10 graphic's slot names the net `B1{slash}GND`, and
  `with_graphic_nets` looked it up by the model name `B1/GND` only. It and the importer's `graphic_net`
  now take the stored spelling too. Proof:
  `uv run pytest tests/unit/convert/test_slash_net_copper_c0425.py -q -n 0` (on 332b79837 the array case
  gives 6 `convert.unexplained` and the import exits 5).
