## 1. Variant names

- [x] 1.1 `library.derive.derive_from_model`: a variant takes the next free `<name>_<n>`, never the name of
  another footprint of the board or of another variant. Proof:
  `uv run pytest tests/unit/library/test_derive.py tests/unit/importer/test_vendor.py -q`.

## 2. Via without a ring

- [x] 2.1 `dsl.intents.record_table` and `backends.kicad.copper._via_sizes`: a drill equal to the diameter is
  accepted, and a larger one is refused with "larger than the diameter". `explain.toml`, `docs/copper.md` and
  `docs/dsl.md` say so. Proof:
  `uv run pytest tests/unit/dsl/test_copper_tables.py tests/unit/backends/kicad/test_copper_tracks.py -q`.

## 3. Public proof

- [x] 3.1 `tests/corpus/test_import_selfcheck_c0426.py`: `import --to python --allow-lossy --dry-run` of
  `altium-third-party-pcbdoc-01` (one pad 1 nm off on 948b6a376) and `altium-third-party-pcbdoc-02` (a via whose
  drill equals its diameter, the code did not build) gives no `import.unequal` and `equivalent` true. Proof:
  `uv run pytest tests/corpus/test_import_selfcheck_c0426.py -q` (2 passed).

## 4. Close

- [ ] 4.1 CHANGELOG; `make check-fast`; the tests of the touched files and the importer tests. Proof: those
  commands.
  Note (2026-11-05): focused tests pass (6344); `make check-fast` gives 23786 passed and 1 failed,
  `tests/unit/backends/altium/test_roundtrip.py::test_scope_documented` (`net_ties`), which fails the same way on
  `origin/cac/lote-24` 948b6a376 without this change. Left open for the coordinator's full run.
