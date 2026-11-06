# Tasks: c0459

## 1. Code

- [x] 1.1 `BoardRegions` leaves `CARRIED` and is counted lost as frame-bound;
  `uv run pytest tests/unit/convert/test_altium_storages.py`.
- [x] 1.2 `CustomMaskShapes` leaves `CARRIED` and is counted lost with its own reason; the census of the
  converted losses counts one more `altium-storage` loss per row;
  `uv run pytest tests/unit/convert/test_altium_storages.py`.

## 2. Evidence and docs

- [x] 2.1 altium-rounds-2 opens the A/B round trips of rows `-04` and `-08` (A with the carried storage, B
  without): B pours and holds no Board Outline Clearance collision inside the board, A does not (S-2182;
  row `-08`: B pours 33 of 33, A none).
- [x] 2.2 Census of `BoardRegions` in the public rows (S-2181); rows in `pcb-records.md` and
  `docs/hypotheses.md`, c0450's storage list, CHANGELOG; `uv run pytest tests/unit/test_format_facts.py`.
