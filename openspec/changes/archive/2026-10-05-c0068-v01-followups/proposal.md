## Why

The v0.1 changes left five things for v0.2a, and measuring the first found a sixth:

- The copper check ignores a zone's own clearance and passes fills that KiCad's DRC rejects (c0029, c0031).
- A script cannot say how one pad joins a pour (c0031).
- Script copper has only straight tracks and through vias (c0028).
- A script author cannot ask where a pad is without the Python API (c0028).
- No CI job repeats the macOS `kicad-cli` that most hypotheses were confirmed on (c0025).
- Found on 2026-10-05: the `(offset X Y)` of a pad's drill moves the pad's copper in KiCad. The board frame moves the hole instead, so `check` reports clearance errors that do not exist, 35 on one demo board.

## What Changes

- **Pad shape offset.** `BoardPad` keeps the hole at the pad's position and moves the copper by the offset.
- **Zone clearance in the copper check.** A pair of one fill and one track, arc, via or pad takes the zone's clearance as it takes a class clearance, as KiCad does on both majors. Two fills keep today's rule. A fill that KiCad just made stays clean.
- **Pad zone connection in the DSL.** `Part.zone_connection(number, connection, *, index=None, locked=False)`. On a rebuild, a setting made in KiCad wins unless the request is locked, as for zones and fields.
- **Arcs and via kinds in script copper.** `arc_to(mid, end)` as a path element; `kind=` on `via_step` and `Design.via`.
- **`fenolite pads PATH [REF [NUMBER]]`.** The pads of a board in the board frame.
- **`macos-app` nightly job.** `tests/kicad` on `kicad-cli` of the 10.0.6 macOS disk image, pinned by SHA-256.

Size: 9.75 design-days. Each part can be cut alone, except the first two.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `board-frame`: MODIFIED "Pad holes", "Pad copper entries".
- `copper-check`: MODIFIED "Clearance in force", "Clearance findings", "Supported cases are documented against KiCad's DRC".
- `kicad-oracle`: MODIFIED "Copper verdict parity canaries"; ADDED "Zone clearance parity canaries", "Fresh fills stay clean under the zone clearance", "Arcs and via kinds pass the oracle", "Pad shape offset passes the oracle".
- `design-dsl`: MODIFIED "Copper intents in the DSL"; ADDED "Pad zone connections in the DSL", "Pad zone connections in a build".
- `layout-lens`: ADDED "Pad zone connections across rebuilds".
- `manual-copper`: MODIFIED "Copper module", "Copper uuids and ids", "Tracks from intents", "Single vias", "Script copper is regenerated", "Copper issue codes".
- `cli-contract`: ADDED "Pads command".
- `ci-baseline`: ADDED "macOS application nightly job".

## Non-goals

- No zone clearance between two fills: KiCad's DRC judges none.
- No stitching that avoids zones; stitch vias stay through vias.
- No pad zone connection for `--target altium`.
- Deferred again, with reasons in the design: c0026's rule kinds, export presets, the outline snapping tolerance, per-command result schemas, `inspect` of project and rules files.

## Evidence level required

- Pad shape offset, zone clearance, arcs and via kinds: `KICAD-VERIFIED` by canary rows and probes on both majors (`H-G-FRAME-OFFSET`, `H-K-COPPER-ZONECLR`, `H-G-FRAME-ARC`, `H-K-COPPER-VIAKINDS`).
- Pad zone connection: `H-K-ZONE-CONNECT` of c0031 for the fill, and `H-K-PAD-ZONE-LIB` for the absence of a library mismatch.
- `pads`: the level of the board read with `frame.EVIDENCE`.
- The nightly job: `INFERRED` until its first green run (`H-K-CI-MACOSAPP`).

## Impact

- Changed: `backends/kicad/frame.py`, `copper.py` and `zones.py`; `checks/clearance.py` and `copper.py`; `dsl/part.py` and `intents.py`; `lens/build.py`; `cli/cmd_build.py`.
- New: `cli/cmd_pads.py`, `.github/workflows/nightly.yml`.
- `check` and the copper guard of `build` change their verdict: fewer false errors where pads have an offset drill, and new findings where a fill is closer to other copper than its zone's clearance.
