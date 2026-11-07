## 1. Explicit refusal

- [x] 1.1 Detection from the storage header/data length only (no record decoding).
- [x] 1.2 Refused `embedded-board` loss in convert and import; docs and CHANGELOG. Proof:
      `uv run pytest tests/unit/api/test_conversion_scope.py tests/unit/convert -q`.

## 2. Resolution (after c0173 Q7-Q9)

- [x] 2.1 Record facts in `docs/formats/altium/pcb-document.md` with evidence labels. Done 2026-11-04: the
      record's keys and values are the `INFERRED` rows of S-1422 that c0173 task 7.1 measured on the ten
      panels Altium Designer 24.5.2.23 saved; a row added for what the reader takes from them and what no
      saved file shows (where the copies lie).
- [x] 2.2 Read instances and their documents; prove on kit cases. Instances done 2026-11-04:
      `read/arrays.py:board_arrays`, each array a named `embedded-board` item, the loss still refused.
      Proof: `FENOLITE_ALTIUM_Q_SAVED=<saved/board of Part Q phase A> uv run pytest
      tests/unit/backends/altium/read/test_board_arrays.py -q` (15 passed: the ten saved panels read as
      recorded) and `uv run pytest tests/unit/api/test_conversion_scope.py -q` (11 passed). Reading the
      referenced documents and placing their copies: Moved to c0386.
