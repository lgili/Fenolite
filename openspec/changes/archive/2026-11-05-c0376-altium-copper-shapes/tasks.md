## 1. Model

- [x] 1.1 Design the entity: none needed. `Graphic.net_id` (change c0277) is the filled copper shape of a
      net, already in the schema and left out of the canonical JSON when `None`.

## 2. Readers and writers

- [x] 2.1 Altium fills/regions set `net_id` (they kept the net in the bag only, so a conversion wrote them
      on no net); the KiCad writer already writes it; read-back verifies. Proof:
      `uv run pytest tests/unit/backends/altium/adapter/test_copper.py tests/unit/api/test_conversion_scope.py -q`.
- [x] 2.2 The copper check already judged these shapes through the bag net (c0277) and now reads `net_id`.
      KiCad DRC: a region on a pad of its net adds no short or clearance violation. Proof:
      `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/convert/test_a2k_load.py -q -k copper_shape`
      (10.0.6 local; 9.0.9 pinned image). KiCad does not report no-net copper on a pad as a short, so the
      DRC run proves no regression rather than the fix; the adapter test proves the fix.
- [x] 2.3 Python import emits them: the Altium import reads the converted KiCad board, whose copper
      graphics now carry `(net …)`, written as graphics of their net (c0277). Checked on a private board
      (equivalent, outside the repository).

## 3. Close

- [x] 3.1 Docs, CHANGELOG, `openspec validate --strict`, focused tests, `make check-fast`.
      Done 2026-11-05. `make check-fast` scope: CI 41947475460 on 515ddc6a, `quality` and the five `unit`
      jobs passed; later commits of `cac/c0364-lote16`: focused tests passed and `openspec validate
      --strict` passed.
