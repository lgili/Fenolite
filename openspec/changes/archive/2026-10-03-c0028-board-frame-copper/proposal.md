## Why

The dogfood buck board, built through the public API only, drew 29 power-track segments from a hand-made pad table: pads are footprint-local, and the only helper is `pcb.pad_angle_to_board`. A placement change silently invalidated every coordinate, and a hand-written extent check got the 270° case wrong. `embed.footprint_extent` works in the definition's frame only. The copper check (c0029), placement (c0022) and field placement (c0030) need this geometry too.

## What Changes

- `backends/base.py`: plain-data records `PadCopper`, `BoardPad`, `PlacedExtent` and the protocol `BoardFrame` (`board_pads`, `placed_extents`), satisfied by `KicadBackend`, so `checks` and `placement` need no backend import.
- `backends/kicad/frame.py` (new):
  - `board_pads` and `find_pads(design, "U1", 2)`: board-frame position, rotation, layers, net, hole and copper entries of every pad, all pads sharing a number included.
  - Copper entries are integer core points with a width (disc, capsule or rounded polygon), read with the opaque `roundrect_rratio` and custom primitives; supersets are flagged `exact=False`. `copper_polygon` gives an outer polygon.
  - `placed_extent`: front and back courtyard rings with rotation and side applied, from the footprint's own node, with a pad-hull fallback.
- `backends/kicad/copper.py` (new): `resolve_copper` turns intents into tracks and vias:
  - pad to pad or pad to point, with waypoints and layer-changing via steps;
  - single vias, and stitching along a polyline or on a grid in a region, clear of other copper;
  - nets inferred from the pads and checked; widths and via sizes from the net class.

  Uuids are RFC 9562 version 8 with a Fenolite marker, hashed from the caller's key and locator, so rebuilds keep ids; `merge_copper` regenerates script copper and drops stale items and duplicates.
- `fenolite.dsl`: `Part.pad`, `via_step`, `Design.track`, `Design.via`, `Design.stitch` and `copper(design)` record intents as data, resolved by the build after placement and c0019's precedence, so copper follows footprints moved in KiCad; `merge_layout` uses `merge_copper`.
- Oracle on `kicad-cli` 9.0.9 and 10.0.6, probes first: the uuids load and survive a re-save; pad positions match IPC-D-356 at 0°, 90°, 180°, 270° and 30° on both sides; clearance and `courtyards_overlap` canaries at ±20 µm; no unconnected item on routed nets, also after a footprint move.
- Registers: S-0110, S-0111; `H-G-FRAME-UUID`, `-SHAPE`, `-CRTYD`, `-ROUTE`; `docs/formats/kicad/frame.md`, `docs/copper.md`.

Budget: 21.5 working days, 18.5 after the cut order in the design.

## Capabilities

### New Capabilities
- `board-frame`: pads, copper entries, holes, placed extents, polygons.
- `manual-copper`: copper uuids, intent resolution, stitching, regeneration.

### Modified Capabilities
- `backend-protocol`: ADDED "Board-frame protocol".
- `design-dsl` (c0011): ADDED "Copper intents in the DSL", "Copper intents in a build".
- `layout-lens` (c0019): ADDED "Script copper in a merge".
- `kicad-oracle`: ADDED "Board-frame queries agree with kicad-cli", "Script copper passes the oracle".
- `design-model`: MODIFIED "Identifier derivation" (c0011's text plus a fifth case).

## Non-goals

- Placement legality (c0022), the copper check and guard (c0029), field placement (c0030), routing (c0016, c0023), zone fill (c0015), zone settings (c0031).
- Arcs, blind, buried and micro vias, and zones from the copper API; avoiding zones and the board edge; a CLI pad query.
- A thick-shape geometry type (c0029's), a `package-layering` change, a schema change.

## Evidence level required

- Pad positions and rotations: `KICAD-VERIFIED (9.0.x, 10.0.x)`, reusing `H-G-ROT-DIR`, `H-G-BOTTOM-PLACE` and `H-G-PAD-ANGLE-ABS`.
- Copper entries and extents: `KICAD-VERIFIED` on the bench (`H-G-FRAME-SHAPE`, `H-G-FRAME-CRTYD`); `INFERRED` elsewhere.
- Script copper: `H-G-FRAME-UUID`, `H-G-FRAME-ROUTE` on both majors; module evidence stays `INFERRED`.
- Resolution, merging and the DSL: mechanical (hermetic tests).

## Impact

- Extended `backends/base.py`, `backends/kicad/backend.py`, `dsl`, `lens/build.py`, `lens/preserve.py`, `cli/cmd_build.py`.
- No runtime dependency, FEN code, schema or layering change.
- Depends on c0019 and c0020 (through them c0011, c0017, c0009, c0005); after c0021 by order only.
