## 1. Merge

- [x] 1.1 Authored regression: a pad whose PCB net differs from its sheet net put the pin in two nets
      (`test_net_only_on_the_board_keeps_the_pad_net` encoded it).
- [x] 1.2 Keep sheet membership; report the disagreement with both net names. Proof:
      `uv run pytest tests/unit/backends/altium/adapter -q`.

## 2. Close

- [x] 2.1 Docs, CHANGELOG, explain entry, guide line for the new code, `openspec validate --strict`,
      focused tests, `make check-fast`.
      Done 2026-11-05. `make check-fast` scope: CI 41947475460 on 515ddc6a, `quality` and the five `unit`
      jobs passed; later commits of `cac/c0364-lote16`: focused tests passed and `openspec validate
      --strict` passed. The guide line is on page `altium` (`tests/unit/agent/test_pages.py`, 113 passed).
