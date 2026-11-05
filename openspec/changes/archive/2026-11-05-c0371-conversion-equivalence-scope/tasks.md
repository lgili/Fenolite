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

- [x] 3.1 Docs, CHANGELOG, explain entries, `openspec validate --strict`, focused tests, `make check-fast`.
      Done 2026-11-05. `make check-fast` scope: CI 41947475460 on 515ddc6a, `quality` and the five `unit`
      jobs passed; later commits of `cac/c0364-lote16`: focused tests passed and `openspec validate
      --strict` passed. No new issue code needs an explain entry: the report kinds `shared-footprint` and
      `embedded-board` are documented in `docs/conversion.md`.
- [x] 3.2 Re-run the private batch outside the repository and record the outcome there.
  Done 2026-11-04 by root on cac/lote-15 515ddc6a: import, convert and check rerun on the maintainer's private board; outcome recorded in the maintainer's private folder only. Same issue codes and counts as the previous private run; no new loss or refusal.
