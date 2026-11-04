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

- [ ] 3.1 Docs, CHANGELOG, `openspec validate --strict`, focused tests, `make check-fast`.
