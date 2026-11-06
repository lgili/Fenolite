# Tasks: c0432 place on a converted board

## 1. Existing findings

- [x] 1.1 `place.existing` (warning): legality findings of the board before the moves that the layout after
  repeats on parts not moved. Proof: `uv run pytest tests/unit/cli/test_place_c0432.py -q`.

## 2. Locked parts

- [x] 2.1 `place.locked` hint names `--force` and the kept lock of a converted or imported board. Proof:
  the same file.

## 3. Group copper

- [x] 3.1 A group drags the vias in its pads and the track ends on its pads and those vias. Proof: the same
  file, on the authored `routed` sample converted to KiCad, flip included.

## 4. Close

- [x] 4.1 CHANGELOG, explain, docs, codes test; `gen_*` and `model_review` with `--check`; `make check-fast`
  and the place tests through `fenolite-heavy`.
