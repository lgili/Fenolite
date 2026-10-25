## 0. Entry check

- [ ] 0.1 Record the position forms of `check` findings per stage. Proof: `openspec validate c0188-check-overlay --strict --no-interactive`.

## 1. Overlay

- [ ] 1.1 Add `view/check_overlay.py` (scenario "Two findings"). Proof: `uv run pytest tests/unit/view/test_check_overlay.py -q`.
- [ ] 1.2 Add `--check` (scenario "Not a check reply") and the Messages panel. Proof: `uv run pytest tests/unit/cli/test_view_cmd.py tests/unit/view -q`.

## 2. Closing

- [ ] 2.1 Browser review with a KiCad DRC of a public board. Proof: the record under this task.
- [ ] 2.2 Docs, agent guide, fast gate. Proof: `make check-fast`.
