## 1. Scope

- [x] 1.1 Authored regression: an Altium project with one schematic-only part converts without
      `convert.unexplained`; removing that part from the written schematic is still reported.
- [x] 1.2 Leave source components without a source footprint out of level 1 of the board comparison.

## 2. Source duplicates

- [x] 2.1 Authored regression: a component linked to two footprints reports an unexplained `ref-ambiguous`.
- [x] 2.2 `shared-footprint` report kind (changed), its docs row, and the explanation of `ref-ambiguous`.
      Proof: `uv run pytest tests/unit/api/test_conversion_scope.py tests/unit/convert -q`.
- [x] 2.3 The zone outlines with an arc vertex are read from the board document in a project subfolder
      (found while starting c0375). Proof: `uv run pytest tests/unit/api/test_conversion_scope.py -q -k arc_zones`.

## 3. Close

- [ ] 3.1 Docs, CHANGELOG, explain entries, `openspec validate --strict`, focused tests, `make check-fast`.
- [ ] 3.2 Re-run the private batch outside the repository and record the outcome there.
