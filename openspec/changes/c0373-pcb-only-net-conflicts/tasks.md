## 1. Merge

- [x] 1.1 Authored regression: a pad whose PCB net differs from its sheet net put the pin in two nets
      (`test_net_only_on_the_board_keeps_the_pad_net` encoded it).
- [x] 1.2 Keep sheet membership; report the disagreement with both net names. Proof:
      `uv run pytest tests/unit/backends/altium/adapter -q`.

## 2. Close

- [ ] 2.1 Docs, CHANGELOG, explain entry, guide line for the new code, `openspec validate --strict`,
      focused tests, `make check-fast`.
