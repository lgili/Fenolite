## 1. Regression

- [x] 1.1 A non-KiCad source with a TAB property refused the import (`FormatError`, exit 3): the former
      `source-backend` case of `test_tab_requires_measured_source_and_single_pose`.
- [x] 1.2 Declare `property-tab` and go on; KiCad TAB path unchanged. Proof:
      `uv run pytest tests/unit/importer/test_native_tab_property.py -q`.

## 2. Close

- [x] 2.1 CHANGELOG, `openspec validate --strict`, focused tests, `make check-fast`.
      Done 2026-11-05. `make check-fast` scope: CI 41947475460 on 515ddc6a, `quality` and the five `unit`
      jobs passed; later commits of `cac/c0364-lote16`: focused tests passed and `openspec validate
      --strict` passed.
- [x] 2.2 Re-run the private board in progress outside the repository and record the outcome there.
  Done 2026-11-04 by root on cac/lote-15 515ddc6a: import, convert and check rerun on the maintainer's private board; outcome recorded in the maintainer's private folder only. Same issue codes and counts as the previous private run; no new loss or refusal.
