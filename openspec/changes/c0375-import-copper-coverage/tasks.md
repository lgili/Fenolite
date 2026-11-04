## 1. Copper

- [x] 1.1 Net-less tracks and arcs in copper tables (DSL + emitter), authored regression. Proof: `uv run pytest tests/unit/importer/test_import_copper_coverage.py -q`.
- [x] 1.2 Degenerate arcs as tracks, reported as changed (`import.arc-as-track`, info; an arc whose start
      and end are one point stays `degenerate-arc`). Same proof.

## 2. Zones

- [x] 2.1 Altium arc outlines with `arc_to`: no change needed. The Altium import reads the KiCad board
      of its in-memory conversion, whose zone outlines with arcs are flattened there as a declared change
      (`zone_outlines`), so the emitter writes them without loss. The one `zone-outline` of the triage is
      a source polygon of two equal vertices (incomplete input). Found on the way: with the board in a
      project subfolder those zones were dropped; fixed under c0371 (task 2.3).
- [x] 2.2 Exact zone names that repeat or have surrounding spaces. Proof: `uv run pytest tests/unit/importer/test_import_copper_coverage.py -q`.

## 3. Close

- [ ] 3.1 Docs, CHANGELOG, guide lines, `openspec validate --strict`, focused tests, `make check-fast`.
