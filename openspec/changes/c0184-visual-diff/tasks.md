## 0. Entry check

- [ ] 0.1 Read `diff`'s matching and the scenes; record the matching keys under this task. Proof: `openspec validate c0184-visual-diff --strict --no-interactive`.

## 1. Compare

- [ ] 1.1 Add `view/compare.py` for boards (scenario "A moved part and a new track"). Proof: `uv run pytest tests/unit/view/test_compare.py -k board -q`.
- [ ] 1.2 Add sheets. Proof: `uv run pytest tests/unit/view/test_compare.py -q`.
- [ ] 1.3 Add `--compare` to `fenolite view` (scenario "Compare counts"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py -q`.

## 2. Page and closing

- [ ] 2.1 Diff layer, OLD/NEW toggle and the Changes panel. Browser review of two commits of a public board. Proof: the record under this task.
- [ ] 2.2 Docs, agent guide, fast gate. Proof: `make check-fast`.
