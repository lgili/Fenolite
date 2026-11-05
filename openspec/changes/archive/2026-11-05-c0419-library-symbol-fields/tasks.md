# Tasks: c0419

## 1. Model and record

- [x] 1.1 `SymbolField` and `SymbolDef.fields`; schemas and the model review inventory regenerated;
  `docs/design-model.md`.
- [x] 1.2 Pins record `[symbol] fields`: parse, refusals, canonical text, `symbol_def`;
  `docs/library-records.md`.

## 2. Writer

- [x] 2.1 Placed and hidden standard fields; unchanged bytes without `fields`.
- [x] 2.2 Lines written with every point.

## 3. Proof

- [x] 3.1 Unit tests; KiCad 10.0.6 oracle (`sym export svg`, `sym upgrade` read back);
  `tools/gen_schemas.py --check`, `tools/gen_cli_surface.py --check`, `tools/gen_agent_guide.py --check`;
  `CHANGELOG.md`.

## Proof (2026-11-05)

- Focused tests through `fenolite-heavy` (`-n 2`), on `origin/cac/lote-22` c54e884b: catalog, library, the
  KiCad backend, every test file that calls `write_symbol_library`, model, schema drift, tools, result and
  file schemas, and the two KiCad 10.0.6 symbol oracles: 6376 passed, 3 skipped. Two failures,
  `test_pcb_write.py::test_created_tokens` and `::test_coverage_tokens`, fail the same way on c54e884b
  without this change.
- `tests/kicad/library/test_symbol_fields_oracle.py` (kicad-cli 10.0.6): `sym export svg` plots the
  library; the file `sym upgrade --force` saves holds each placed property at its `at`, with its justify,
  hidden ones with `(hide yes)` (KiCad 10 moves the flag from `effects` to the property), and the
  three-point polyline with its three points.
- `tools/gen_schemas.py --check`, `--formats --check`, `tools/gen_cli_surface.py --check`,
  `tools/gen_agent_guide.py --check`, `tools/model_review.py --check`: exit 0. The model review inventory
  gains only `SymbolDef.fields` and `SymbolField` (reader locations left as they were).
