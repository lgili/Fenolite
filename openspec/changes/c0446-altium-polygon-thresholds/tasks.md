# Tasks: c0446

## 1. Spec

- [x] 1.1 Deltas for altium-pcb-writer ("Polygon pour records") and altium-import ("Zones from polygons").
  Proof: `openspec validate c0446-altium-polygon-thresholds --strict`.

## 2. Writer and reader

- [x] 2.1 `docboard.polygon_fields(..., islands=, neck=)` and `pcbdoc` passes the zone's settings.
  Proof: `tests/unit/backends/altium/test_polygon_thresholds.py -k written`.
- [x] 2.2 `adapter/copper.py` projects the keys into `Zone.settings`. Proof: `-k read`.
- [x] 2.3 Pins: none change. A default zone keeps the kit's bytes (design.md), so the graduated kit
  samples, `test_docboard.py` and `gen_altium_graduation --check` hold. Proof: the consuming files run alone
  (list in the commit message).

## 3. Records and proof

- [x] 3.1 `pcb-copper.md`, `docs/altium.md` where it names the keys, CHANGELOG.
- [x] 3.2 Level 5 on the round trip of public rows 01 and 06 with the computed pour: thresholds now equal the
  source's; the pour-net differences remain (design.md, "Result").
- [ ] 3.3 Altium DRC of the round trip (altium-rounds-2).
