# Tasks: c0451 texts, values and library links through a round trip

## 1. Empty texts

- [x] 1.1 The PCB writer writes the comment record of a placed empty value, and an empty footprint text.
  Proof: `uv run pytest tests/unit/backends/altium/test_lower_empty_texts.py -n 0 -q`.

## 2. Library links

- [x] 2.1 The Altium → KiCad conversion writes `Altium Footprint` and `Altium Symbol`; the KiCad → Altium
  conversion gives them back. Proof: `uv run pytest tests/unit/convert/test_round_trip_texts.py -n 0 -q`.

## 3. Special strings

- [x] 3.1 Unmapped special strings are written as `${NAME}`; `${NAME}` and the project's text variables come
  back as special strings and parameters. Proof:
  `uv run pytest tests/unit/convert/test_project_parameters.py -n 0 -q`.

## 4. Close

- [x] 4.1 The public rows (S-2101): the round trip of rows 01 to 07 keeps the links, values and texts of
  the source. Proof: the probe recorded in S-2101 (all footprint links and Value fields of rows 01 to 07;
  every symbol link but 23 of foc whose names lie outside 7-bit ASCII; a cobra text with a line break stays
  refused, as before).
- [x] 4.2 Docs, CHANGELOG; ruff, format, pyright src, `gen_*` and `model_review` with `--check`,
  `openspec validate --strict`; each touched or consuming test file alone with `-n 0`.
