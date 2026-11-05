# Tasks: c0404

## 1. Block capture

- [x] 1.1 `current_model` maps the net id of copper graphics; a graphic without a net keeps none. Proof:
  `uv run pytest tests/unit/cli/test_blocks_capture.py -q` (the new test fails without the fix).

## 2. Model review

- [x] 2.1 `--check` compares the reviewed shape and notes moved readers; the stored inventory is written
  again. Proof: `uv run python tools/model_review.py --check` (exit 0) and
  `uv run pytest tests/unit/test_model_review_tool.py -q`.
- [x] 2.2 A test runs the check against the stored inventory. Proof: `test_stored_inventory_is_current`
  in the same file.

## 3. Close

- [ ] 3.1 `make check-fast` through the heavy lock; CHANGELOG line; `openspec validate c0404 --strict`.
