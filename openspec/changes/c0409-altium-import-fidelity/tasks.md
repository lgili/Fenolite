# Tasks: c0409

Each task's proof is a focused test on authored data. The private project and its report stay outside the
repository. Source ids: S-1680..S-1699.

## 1. High

- [x] 1.1 B8: the KiCad writer writes a created footprint's graphics; the report counts footprint graphics and
  texts, and a lost footprint text is reported and warned. Proof:
  `uv run pytest tests/unit/convert/test_footprint_graphics.py -q` (fails with 0 `fp_*` on the base writer). The converted board and its
  library load in kicad-cli 10.0.6 (`pcb export svg`, `pcb drc`, `fp export svg`).
- [x] 1.2 B4: the importer keeps the source's rule rank and numbers; one-sided rules stay rules. Proof:
  `uv run pytest tests/unit/importer/test_altium_rule_rank.py -q`; on the base emitter the same design gives
  `minimum(clearance=..., netclass="PWR")`, which the test refuses. `tests/unit/importer` passes (533).

## 2. Medium

- [x] 2.1 B5: PolygonConnect rules to zone settings and pad zone connections. Proof:
  `uv run pytest tests/unit/convert/test_polygon_connect.py -q`.
- [x] 2.2 B6: governing zone clearance. Proof: `uv run pytest tests/unit/convert/test_polygon_connect.py -k clearance -q`.
- [x] 2.3 B9: models on the board's footprints and in the import. Proof:
  `uv run pytest tests/unit/importer/test_altium_models.py -q`. Both B5/B6 and B9 tests fail on the base; the
  conversion, import and KiCad load tests pass (698). A built copy of the imported code does not carry the
  model folder: `build` vendors footprints, not models (follow-up).
- [x] 2.4 B7: `select.no_net()`, the model leaf, the Altium scope and the KiCad lowering; the agent-guide line
  and `tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/dsl/test_select_no_net.py tests/unit/importer/test_no_net_rule.py tests/unit/agent/test_pages.py -q`.

## 3. Low

- [x] 3.1 B10: project parameters and special strings. Proof:
  `uv run pytest tests/unit/convert/test_project_parameters.py -q`.
- [x] 3.2 B11: board-area render page. Proof: `uv run pytest tests/unit/backends/kicad/test_plot_page.py -q`.

## 4. Close

- [ ] 4.1 CHANGELOG, format facts with their sources, `openspec validate --all --strict`, ruff, format and
  `pyright src`; the coordinator's batch check-fast and CI.
