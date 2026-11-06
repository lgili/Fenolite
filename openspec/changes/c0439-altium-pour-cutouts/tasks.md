# Tasks: c0439

## 1. Writers

- [x] 1.1 `rec.region_record(polygon_cutout=True)` writes `KIND=1` without the keep-out flag;
  `V7_LAYERS` names Multi-Layer `MULTILAYER`.
- [x] 1.2 `pcbdoc.free_records` and `pcblib.keepout_records` write a pour-only rule area as polygon cut-outs;
  `uv run pytest tests/unit/backends/altium/test_pour_cutouts.py`.

## 2. Taken in from c0438 (cac-altium-code, commit c0acf241c)

- [x] 2.1 `convert --to altium` gives copper graphics their KiCad net (`fpitems.with_graphic_nets`);
  `uv run pytest tests/unit/convert/test_polygon_cutouts.py`.
- [x] 2.2 Level 5 kind `copper-no-net`, its explain entry, docs and refrozen schemas;
  `uv run pytest tests/unit/checks/equivalence/test_codes.py`, `uv run python tools/gen_schemas.py --check`,
  `uv run python tools/gen_cli_surface.py --check`.

## 3. Evidence and docs

- [x] 3.1 `pcb-records.md` records the census of cut-outs (rows `-01`, `-02`, `-06`, `-08`; S-1980) and the round trip of row `-01` (S-1981);
  `uv run pytest tests/unit/test_format_facts.py`.
- [ ] 3.2 altium-rounds-2 opens the kit `c0438-cutouts` and a rewritten row `-06` in Altium Designer: the cut-outs show as
  polygon cut-outs and DRC finds no new short or keep-out clearance violation (kit request).
