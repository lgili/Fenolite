## 1. Loss instead of block

- [x] 1.1 Authored regression: a generated circuit too large for its page blocks `convert --allow-lossy`.
- [x] 1.2 Return the refusal as the declared loss; exit 7 without `--allow-lossy`; the lost schematic
      explains schematic-only components. Proof: `uv run pytest tests/unit/api/test_conversion_scope.py -q`.

## 2. Sheets and pages

- [x] 2.1 Keep the source's sheets as KiCad sheets when the circuit carries sheet paths (a hierarchical
      circuit already did; a flat one now keeps its documents). Proof:
      `uv run pytest tests/unit/convert/test_generated_sheets.py -q`.
- [x] 2.2 Paginate a flat generated circuit; prove with KiCad 9/10 ERC that the pages load. Proof:
      `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/convert/test_a2k_schematic.py -q -k source_sheets`
      (KiCad 10.0.6 local; 9.0.9 pinned image).

## 3. Close

- [x] 3.0 Found on 2026-11-04 (CI 41947475460): the generated schematic of `altium-third-party-pcbdoc-08`
      is now written on pages instead of refused; its `schematic` loss leaves the census (`design.md`).
      Proof: `FENOLITE_HEAVY=1 FENOLITE_REQUIRE=corpus uv run pytest -n 2 tests/corpus/test_altium_rule_kinds.py
      tests/corpus/test_altium_pour_census.py tests/corpus/test_convert_altium_census.py
      tests/corpus/test_altium_copper.py 'tests/corpus/test_import_corpus.py::test_demo_board_imports_equivalent[18]'`
      (103 passed, 2026-11-05).
- [x] 3.1 Docs, CHANGELOG, `openspec validate --strict`, focused tests, `make check-fast`.
      Done 2026-11-05. `make check-fast` scope: CI 41947475460 on 515ddc6a, `quality` and the five `unit`
      jobs passed; later commits of `cac/c0364-lote16`: focused tests passed and `openspec validate
      --strict` passed.
