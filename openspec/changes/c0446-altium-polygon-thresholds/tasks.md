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
- [x] 3.3 Altium DRC of the round trip (altium-rounds-2).
  Proof (2026-11-06, Altium 24.5.2, pass a, after Repour): cobra DRC 255 against c0444's 269 (Un-Routed 18
  against 21, Antennae 3 against 14, every other rule equal), 1 of 10 polygons empty (`NETL401_1`) against 3;
  islands 155 mil² (0.1 mm²) and necks 5.906 mil (0.15 mm), the source's values. BMS equal to c0444 (DRC 3618,
  0 of 5 empty); 2 of its 5 islands active and 3 off, as the source sets them. Pass b (island area edited in
  Altium) hangs Altium; not repeated, noted as a kit hazard (c0461).
