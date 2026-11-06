# Tasks: c0441 board shape and connections through a round trip

## 1. Outline arcs

- [x] 1.1 The Altium writer writes an outline arc as one arc vertex. Proof:
  `uv run pytest tests/unit/convert/test_convert_slots.py tests/unit/convert/test_round_trip_shape.py -q`.

## 2. Connections

- [x] 2.1 A conversion writes a via whose hole equals its diameter (`full_drill`). Proof:
  `uv run pytest tests/unit/convert/test_round_trip_shape.py -q -k vias`.
- [x] 2.2 The KiCad board writer writes the corner ratio of a created pad. Proof: the same test.
- [x] 2.3 A conversion to Altium moves the board by whole units. Proof: the same test and
  `-k whole_units`.

- [x] 2.4 A conversion to Altium gives a copper graphic the net of its KiCad slot. Proof:
  `uv run pytest tests/unit/convert/test_round_trip_shape.py -q -k region`.

## 3. Equivalence

- [x] 3.1 Level 7 compares the board shape in the relative frame. Proof:
  `uv run pytest tests/unit/convert/test_round_trip_shape.py -q -k "level_7 or flattened or rounded"`.

## 4. Close

- [x] 4.1 Docs (`pcb-document.md`, `altium.md`), CHANGELOG; ruff, format, pyright src, `gen_*` and
  `model_review` with `--check`, `openspec validate --strict`; each touched or consuming test file alone with
  `-n 0` (Master's lock rule of 01:05: no `make check-fast` until 05:00; CI on the lote does the broad run).
- [x] 4.2 Altium confirms the written arc vertex and the vias (altium-rounds-2, AD 24.5.2.23, 2026-11-06):
  every arc reads as an arc, foc keeps its 48 full-drill vias, PCB1 its U1/U2/A1 pads, and the netted
  free regions keep their net. Net antennae left on BMS (43), foc (26) and cobra (14), and the outline
  clearance of NG6011 and DM6010 (silk and two extra components), are outside this change.
