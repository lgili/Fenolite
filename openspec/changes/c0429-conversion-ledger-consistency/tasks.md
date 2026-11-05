# Tasks: c0429 conversion ledger consistency

## 1. Convert

- [x] 1.1 `report_issues(report)` in `fenolite.convert`: one `convert.lossy` per lost row, one
  `convert.changed` per changed row, one `convert.kept` per kept row; `convert_project` uses it after the
  refusal; `WARNED_LOSSES` removed; `codes.py`, `cmd_convert`, `explain.toml`, `docs/conversion.md` and
  `docs/cli-contract.md` updated. Proof: the convert files of 3.1.
- [x] 1.2 Invariant test over every kind of `KINDS` (lost, changed, kept, and a row with none), and the
  refusal of a `refuse` kind against the warning of a `report` kind (`rule`, `body`, `model`,
  `schematic`). Proof: `uv run pytest tests/unit/convert/test_c0429_ledger.py -q`.

## 2. Import

- [x] 2.1 `import --to python` of an Altium source gives `result.report` (the conversion's report; `null`
  for KiCad); `ImportReply.report` and `ImportResult.report` optional, `kept` optional in the v1 convert
  row; schemas regenerated, `frozen-v0.json` refrozen. Proof:
  `uv run python tools/gen_schemas.py --check`.
- [x] 2.2 End-to-end test on an authored Altium project: the import's report rows equal convert's, every lost
  row has a `convert.lossy` issue in both, and an import that refuses gives the same `FEN-7001` and issues
  as convert, and the kept rules of c0424 agree in both. Proof:
  `uv run pytest tests/unit/importer/test_c0429_import_report.py -q`.

## 3. Close

- [x] 3.1 CHANGELOG; no existing test pinned the old issue lists. Proof (focused, one process; no full suite
  while the lote-24 run holds the heavy lock): the convert files `test_to_altium`, `test_to_kicad`,
  `test_body_models`, `test_altium_rule_fates`, `test_footprint_graphics`, `test_footprint_content`,
  `test_curve_error`, `test_convert_slots`; the CLI files `test_convert_cmd`, `test_evidence_contract`,
  `test_result_schemas`, `test_explain_cmd`, `test_import`, `test_cli_surface`; `importer/test_altium_input`,
  `importer/test_altium_models`, `api/test_conversion_scope`, `api/test_conversion_api`,
  `agent/test_pages`, `test_schema_drift`, `test_import_graph` and the two new files.
- [x] 3.2 Light checks: ruff, ruff format --check, pyright src; `gen_schemas`, `gen_cli_surface`,
  `gen_agent_guide` and `tools/model_review.py` with `--check`; openspec validate --strict.
