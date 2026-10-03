## Why

The maintainer must route a 4-layer board through Fenolite and open it in Altium Designer 26.5:
critical copper by script, the rest by a router. c0035's PCB document opens there but holds no
copper.

## What Changes

- **Copper.** `<name>.PcbDoc` gains tracks, arcs, vias and zones:
  - tracks and arcs in the 36- and 47-byte forms Altium Designer 26.5 accepts;
  - through vias in the 321-byte form Altium saves;
  - each zone as one polygon pour per layer **without poured copper**; Altium repours.
- **4-layer stack, signal or plane.** Each inner layer is a signal layer (Mid-Layer n, written as two
  public Altium-saved boards hold it: S-0199, S-0200) or an internal plane with one net
  (`PLANE<n>NETNAME` and its stack entry, as S-0176).
  - DSL: `design.board(w, h, copper=4, planes={"In1.Cu": gnd})`.
  - The model does not change: a plane is a build parameter, like the copper count.
- **Two copper sources.**
  - **Script copper.** The build accepts the model that carries c0028's resolved copper. This is
    specified and tested here; c0028 plugs in later.
  - **`--copper-from board.kicad_pcb`.** The build reads a routed KiCad board of the same design
    with Fenolite's reader and copies its copper. It first checks components, footprints, pad nets,
    outline and net names, and refuses with located issues. The board's placements win.
- **Net classes and rules.** Each net class becomes a `Classes6` class. `Rules6` gets Clearance,
  Width and Routing Via Style rules (cuttable).
- **Refusals.** Blind, buried and micro vias, copper outside the stack or on a plane, and a board
  that does not match the design give errors and no file.
- **Oracles.** `kicad-cli pcb import` (10.0.6) reads the copper and the layer types back; a
  round-trip test proves that copper copied with `--copper-from` equals the source board.
- **Sample.** An authored routed 4-layer sample, a plane variant, and Part C of the evidence page.

## Capabilities

### Modified Capabilities (no new capability)

- `altium-pcb-writer`: 9 ADDED (layer map, stack, records, reader, oracle); MODIFIED "PCB document
  file" (c0035's text).
- `altium-build`: 9 ADDED (copper in a build, planes, script copper, copper from a KiCad board,
  round-trip oracle, codes, evidence, sample, documentation); MODIFIED "PCB document output".
- `design-dsl`: ADDED "Planes in a build"; MODIFIED "Board and placements in the DSL" (living text;
  no other active change modifies it).

## Non-goals

- No router, no copper DSL (c0028, c0016, c0023), no Altium reader.
- No poured copper, hatched pour, zone settings (c0031) or zone fill (c0015).
- No split planes, plane primitives or plane rules; no blind, buried or micro vias.
- No differential pairs, tear-drops, keep-outs, board texts or graphics; no other rule kind.
- No stack other than 2 or 4 copper layers.
- The KiCad target does not write planes; it reports them (`build.plane-not-lowered`).

## Evidence level required

- What KiCad's importer reads: `ORACLE-VERIFIED(kicad-cli)` on 10.0.x under `H-A-PCB-CU-KICAD` and
  `H-A-PCB-CU-ROUNDTRIP`; no claim about Altium.
- What Altium must accept: `INFERRED` under `H-A-PCB-CU-TRACK`, `-VIA`, `-STACK`, `-PLANE`,
  `-REPOUR`, `-CLASS`, `-RULES` and `-VIEWER`, until the maintainer reports Part C; then
  `ALTIUM-VERIFIED(author-report; AD 26.5; <date>; no artefact)`.
- Net classes, rules and a plane's net have no oracle. The build stays `INFERRED` and experimental.

## Impact

- Code: `backends/altium/`, `lens/altium.py`, `lens/build.py` (one code), `dsl/`, `cli/cmd_build.py`.
- Data: `tests/data/altium/routed/`; the blink golden document is rebuilt.
- Docs: `docs/formats/altium/pcb-copper.md` (new), `docs/altium.md`, `docs/dsl.md`, the registers.
  Sources S-0195 to S-0200; the boards of S-0199 and S-0200 (MIT) stay outside the repository.
- Order: … → c0037 → c0038; c0028 lands later and hands its copper over.
- Size: 11.0 design-days (a size, not time); 10.25 without the rules group.
