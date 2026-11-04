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

- [ ] 2.1 Kit measurements for projection side and model types; record facts with evidence labels.
- [ ] 2.2 Convert the proved cases; keep the others as declared losses.

## 3. Close

- [ ] 3.1 Docs, CHANGELOG, `openspec validate --strict`, focused tests, `make check-fast`.
