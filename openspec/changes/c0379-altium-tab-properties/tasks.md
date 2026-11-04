## 1. Regression

- [x] 1.1 A non-KiCad source with a TAB property refused the import (`FormatError`, exit 3): the former
      `source-backend` case of `test_tab_requires_measured_source_and_single_pose`.
- [x] 1.2 Declare `property-tab` and go on; KiCad TAB path unchanged. Proof:
      `uv run pytest tests/unit/importer/test_native_tab_property.py -q`.

## 2. Close

- [ ] 2.1 CHANGELOG, `openspec validate --strict`, focused tests, `make check-fast`.
- [ ] 2.2 Re-run the private board in progress outside the repository and record the outcome there.
