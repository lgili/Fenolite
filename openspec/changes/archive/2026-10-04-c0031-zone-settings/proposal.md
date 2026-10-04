## Why

The dogfood buck board poured GND on both layers through the public API, but could not ask for a 0.3 mm pour clearance, a solid connection on the exposed pad or thermal reliefs elsewhere. `model.board.Zone` holds only outline, name, layers, net, priority and fills; c0009 keeps every zone setting opaque, and c0017 writes created zones without settings. Proposal-time runs found one more defect: KiCad 9.0.9 and 10.0.6 plot a target-9 created zone's fill 0.125 mm larger per side, because it lacks `(filled_areas_thickness no)`.

## What Changes

- `model.board`: value objects `ZoneSettings` (clearance, minimum thickness, connection `solid`/`thermal`/`none`/`thru_hole_only`, thermal gap and spoke width, island removal and minimum area, smoothing, fill mode) and `ZoneHatch`; fields `Zone.settings`, `Zone.filled`, `Zone.locked` and `Pad.zone_connection`. Defaults are KiCad's new-zone values. `board.json` and `library.json` are regenerated.
- Reader: `connect_pads`, `min_thickness`, `fill` and `locked` become modelled children, in each major's form; a child the emitter cannot reproduce stays opaque and projected. Pad `zone_connect` 0–3 is modelled for board and library pads.
- Writer: created zones get KiCad's new-zone form per target, with `(filled_areas_thickness no)` for target 9. A read zone gets a missing child only when its value changed.
- DSL: `Design.zone(net, layers=…, clearance=…, connection=…, …)`, ids from the zone name.
- Lens (c0019): script zones are matched by uuid. The board wins unless the script locks the zone; new zones are added; removed script zones go. The fill digest covers the settings.
- Oracle, probes first: on 10.0.6, `--refill-zones` fills measured with the exact kernel (spokes, pad overrides, clearance against class and rule, gap, spoke width, islands, minimum thickness, hatch); on 9.0.9, loading of every form and the target-9 plot.
- Hypotheses `H-K-ZONE-*`; source S-0125, the Gerber format that the plot probe reads.

Budget: 8.0 working days; cut order in the design. Order: after c0030, before c0015; cuttable to v0.2a at the cost the design states.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-model`: ADDED "Zone settings in the board model"; MODIFIED "Identifier derivation" (c0028's text plus a `zone` row).
- `kicad-file-backend`: ADDED "Zone settings are read", "Zone settings are written", "Pad zone connection"; MODIFIED "Zones, fills and rule areas".
- `design-dsl` (c0011): ADDED "Zones in the DSL", "Zones in a build".
- `layout-lens` (c0019): ADDED "Zones declared in the script"; MODIFIED "Zone fills and the staleness digest" (c0019's text).
- `kicad-oracle`: ADDED "Zone settings pass the oracle".

## Non-goals

- Computing fills and lifting them into the model (c0015). Teardrops.
- Rule areas beyond today's model; footprint-level `zone_connect`; per-pad thermal gap, width and angle.
- The copper check (c0029).
- The zone's own clearance in the copper check: a v0.2a follow-up to c0029.
- New rule kinds such as `zone_connection` (a v0.2a rule-kinds change, c0026 Open Question 3).
- Per-pad requests, hatching and smoothing in the DSL (model API only); zone defaults in `.kicad_pro`.

## Evidence level required

- Model, schema, DSL and lens: mechanical.
- Reading and writing the forms: `CORPUS-VERIFIED`; the rules reproduce all 71 native demo zones and all 355 upgraded third-party zones (`H-K-ZONE-FORM`).
- Meaning of each setting and of pad overrides: `KICAD-VERIFIED (10.0.x)` by refill (`H-K-ZONE-CONNECT`, `H-K-ZONE-GEOM`). On 9.0 only loading is `KICAD-VERIFIED (9.0.x)`, and the meaning stays `INFERRED`: 9.0 has no `--refill-zones` (S-0037; `H-K-ZONE-LOAD9`).
- Defaults: `KICAD-VERIFIED (10.0.x)` for absent children (`H-K-ZONE-DEFAULTS`); the GUI half is `INFERRED` from its saved project defaults (S-0020).
- Target-9 fill plot: `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-K-ZONE-FAT9`).

## Impact

- New `backends/kicad/zones.py`; extended `pcb.py`, `_fpmap.py`, `model/board.py`, `dsl`, `lens/preserve.py`.
- Two schemas regenerated; target-9 fills no longer inflated.
- Depends on c0011 and c0019, archived first.
