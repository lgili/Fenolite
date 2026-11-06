# Tasks: c0444

## 1. Diagnosis

- [x] 1.1 Round-trip public rows 01 and 06; compare vias (net, span, size) and track ends after the
  translation, pads, copper regions and polygons. Proof: the scratch scripts' report (0 via and 0 track-end
  differences on lote-26 with c0441).

## 2. Level 5

- [x] 2.1 `NetPairing.one_sided` and `net_routing(..., one_sided)`: copper that reaches a pad the other side
  lacks is `route-connectivity`. Proof: `uv run pytest tests/unit/convert/test_roundrect_roundtrip.py -q`
  (fails without the change) and the files of `tests/unit/checks/equivalence/` each alone.

## 3. Tests and records

- [x] 3.1 Authored `tests/data/kicad/convert/roundrect_roundtrip.kicad_pcb` with its manifest entry; three
  tests (ratio kept, no pad lost and level 5 equal, lost pad seen). Proof: `tests/corpus/test_manifest.py`.
- [x] 3.2 `docs/equivalence.md` and CHANGELOG.
- [ ] 3.3 Altium's DRC on the c0441 base round trip of rows 01 and 06 (asked of altium-rounds-2; the
  polygon thresholds of design.md are expected to leave antennae on vias).
