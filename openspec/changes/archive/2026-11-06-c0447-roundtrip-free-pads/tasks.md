# Tasks: c0447 free pads through a round trip

## 1. Free pads

- [x] 1.1 `libnames.FREE_PAD_PREFIX` names the link of a free pad in the Altium → KiCad conversion. Proof:
  `uv run pytest tests/unit/convert/test_round_trip_shape.py -n 0 -q -k free_pad`.
- [x] 1.2 The Altium writer writes a converted free pad as a free pad (`lower.converted_free_pad`). Proof:
  `uv run pytest tests/unit/backends/altium/test_lower_free_pads.py -n 0 -q` and the test of 1.1.

## 2. The edge rule

- [x] 2.1 `pcb-copper.md` records the fate of a Board Outline Clearance with an object matrix through a KiCad
  round trip and the DRC of DM6010 (INFERRED; S-2060 and S-2061 in `sources.md`). Proof:
  `openspec validate c0447-roundtrip-free-pads --strict` and
  `uv run pytest tests/unit/test_format_facts.py -n 0 -q`.

## 3. Close

- [x] 3.1 CHANGELOG; ruff, format, pyright src, `gen_*` and `model_review` with `--check`,
  `openspec validate --strict`; each touched or consuming test file alone with `-n 0` (Master's lock rule:
  no `make check-fast`; CI on the lote does the broad run).
