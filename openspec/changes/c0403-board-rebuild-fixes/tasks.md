# Tasks: c0403

Each task's proof is a focused test on authored data; the private report and board stay outside the
repository.

## 1. Fixes, one per Fenolite bug

- [x] 1.1 F5: regression test through the shadowed-rule pass for a circular pad of size 0 (the fix is c0364's
  on `dev`). Proof: `uv run pytest tests/unit/checks/test_specificity.py -q`; the test raises the old
  `ValueError` with `padpath.py` of `75f9e995^`. Private rerun of `fenolite check` on the imported project at
  1169f10d: exit 5, not 1.
- [x] 1.2 F2: the docstring of `minimum()` and the page `board-insulation` state the precedence of class
  minimums. Proof: `uv run pytest tests/unit/checks/test_specificity.py -k class_minimum -q` and
  `uv run pytest tests/unit/agent/test_pages.py -q`.
- [x] 1.3 F3 and F4: the page shows the per-domain exception and how to reach a no-connect pad. Proof:
  `uv run pytest tests/unit/checks/test_insulation_rule_scopes.py -q`.
- [x] 1.4 F7: plans counted per working folder, with a bound in all; contract text. Proof:
  `uv run pytest tests/unit/cli/test_plans.py -q` (the new test fails on the old `prune`).
- [x] 1.5 F8: Specctra clearance rules in rule order, a self rule may lower its class, `rule-widened` when a
  value is kept higher. Proof: `uv run pytest tests/unit/backends/specctra/test_dsn_rule_order.py -q` and
  `uv run pytest tests/unit/backends/specctra/test_dsn_rules.py -q`.
- [x] 1.6 F9: `copper.hole-clearance` in the copper check, the build guards and `check`. Proof:
  `uv run pytest tests/unit/checks/test_copper_holes.py -q`,
  `uv run pytest tests/unit/cli/test_build_copper_guard.py -q`,
  `uv run pytest tests/unit/backends/kicad/test_copperrules.py -q`.
- [x] 1.7 F10: `copper.track-width` in the build's copper guards. Proof:
  `uv run pytest tests/unit/checks/test_widths.py -q` and
  `uv run pytest tests/unit/cli/test_build_copper_guard.py -k narrow -q`.
- [x] 1.8 F6: `route.width-below-minimum` stops the write of copper below the governing width. Proof:
  `uv run pytest tests/unit/cli/test_route_cmd.py -q`.

## 2. Not here

- [x] 2.1 F11 and the items of other owners are listed in the proposal, "Not here", each with its owner.

## 3. Close

- [ ] 3.1 `make check-fast` on the integrated batch (coordinator) and CI `ci-complete` on the exact commit;
  CHANGELOG line; `openspec validate c0403-board-rebuild-fixes --strict`.
