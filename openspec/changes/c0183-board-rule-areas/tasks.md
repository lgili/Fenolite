## 0. Entry check

- [ ] 0.1 Count the keep-outs, room rules and dimension records of the public boards; record the forms of `Dimensions6` if any board holds one. Proof: `openspec validate c0183-board-rule-areas --strict --no-interactive`.

## 1. Scene

- [ ] 1.1 Draw keep-outs (scenario "An authored keep-out"). Proof: `uv run pytest tests/unit/view/test_board_annotations.py -k keepout -q`.
- [ ] 1.2 Draw rooms and dimensions as the facts of 0.1 allow. Proof: `uv run pytest tests/unit/view/test_board_annotations.py -q`.
- [ ] 1.3 Mark courtyard overlaps (scenario "Two overlapping parts"). Proof: `uv run pytest tests/unit/view/test_board_annotations.py -k overlap -q`.

## 2. Closing

- [ ] 2.1 Browser review of a public board with keep-outs. Proof: the record under this task.
- [ ] 2.2 Docs, `LEGAL-ANNEX.md` row, fast gate. Proof: `make check-fast`.
