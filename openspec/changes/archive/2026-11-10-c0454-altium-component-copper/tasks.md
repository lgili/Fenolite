# Tasks: c0454

## 1. Code

- [x] 1.1 The import sets `net_id` on a component's copper graphics;
  `uv run pytest tests/unit/backends/altium/test_component_copper.py -k import`.
- [x] 1.2 The KiCad writer writes `(net …)` on footprint copper, and `with_graphic_nets` reads it back;
  `uv run pytest tests/unit/backends/altium/test_component_copper.py -k kicad`.
- [x] 1.3 The Altium writer writes a footprint's netted copper with its net;
  `uv run pytest tests/unit/backends/altium/test_component_copper.py`.

## 2. Evidence and docs

- [x] 2.1 Round trip of public row `-01` (S-2130). KiCad 10.0.6 save and DRC (S-2131). Rows in
  `board.md` and `pcb-records.md`, and a CHANGELOG line. `uv run pytest tests/unit/test_format_facts.py`.
- [x] 2.2 altium-rounds-2 opens the round trip of row `-01` in Altium Designer: the top layer holds the
  copper of `L3`, `Q2` and `Q6` with the source's nets, and DRC finds no short on it (kit request).
  Done 2026-11-06 (S-2132): 4 regions with the source's owners and nets, 0 Short-Circuit, 0 Clearance, no
  connectivity message names that copper.
- [x] 2.3 KiCad 9.0.9 keeps `(net …)` on a footprint `fp_poly` on a save (maintainer's run).
  Deferred to v0.8 (coordinator, 2026-11-07): not run before the cut of 0.7.0; the code ships.
  Done 2026-11-07 at the coordinator's word (S-2281): the board code of the pinned 9.0.9 image saved the KiCad 9
  leg of row `-01`, converted at `d721893cd` (`pcbnew.SaveBoard`; 9.0's `kicad-cli` has no `pcb upgrade`). The
  two `fp_poly` of `L3` and the `fp_rect` of `Q2` and `Q6` on `F.Cu` keep their uuid and `(net N)` after their
  `layer`, each N naming the same net.
