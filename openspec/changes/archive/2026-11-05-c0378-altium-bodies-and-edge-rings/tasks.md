## 1. Edge rings

- [x] 1.0 Format fact with evidence: an outline arc vertex runs from its vertex to the next (kit case).
      Done with public evidence instead of a kit case: 248 arcs of the eight public boards (S-1530,
      `H-A-IMP-OUTLINE-ARC`, CORPUS-VERIFIED, `tests/corpus/test_altium_outline_arcs.py`, 8 passed).
- [x] 1.1 Authored outline with a large-radius arc reproduces the ring difference.
      The public cause is a vertex off its circle, not a large radius (radii of 2.7 mm and less): the
      authored arc of 100 mil whose end vertex lies 0.2 mil off the circle reproduces it before the fix
      (the Altium edge keeps a 5 µm gap that KiCad's 10 µm join closes, so the two sides' rings differ;
      `tests/unit/backends/altium/adapter/test_outline_arcs.py`, failing before the fix).
- [x] 1.2 Take outline arc ends from the vertices in `adapter/copper.py:outline`; exact ring equality;
      KiCad 9/10 load proof. `OUTLINE_VERTEX_NM` (10 µm); KiCad 10.0.6 local and 9.0.9 (Docker):
      `tests/kicad/convert/test_a2k_load.py::test_outline_arc_off_its_circle_is_a_closed_edge_in_kicad`.

## 2. Bodies

- [x] 2.1 Kit measurements for projection side and model types; record facts with evidence labels.
      Moved to c0387: no kit file measures a body record, and the public facts (`pcb-bodies.md`,
      CORPUS-VERIFIED) cover only projection equal to the component's side and model types 0 and 1.
- [x] 2.2 Convert the proved cases; keep the others as declared losses. The cases the public corpus
      proves already keep their heights and the others stay declared (`altium.import.body-unknown`).
      Proof: `uv run pytest tests/unit/backends/altium/test_body_volume_import.py -q` (10 passed).
      Converting the unmeasured cases: Moved to c0387.

## 3. Close

- [x] 3.1 Docs, CHANGELOG, `openspec validate --strict`, focused tests, `make check-fast`.
      Done 2026-11-05. `make check-fast` scope: CI 41947475460 on 515ddc6a, `quality` and the five `unit`
      jobs passed; later commits of `cac/c0364-lote16`: focused tests passed and `openspec validate
      --strict` passed. Tasks 2.1 and 2.2 moved to c0387.
