## Why

The maintainer must route a complete 4-layer board through Fenolite and open it in Altium Designer
26.5: power and critical copper by script, the other signals by a router plugin. The PCB document of
c0035 opens there but holds no copper: only the outline, a 2-layer stack, components, pads, nets
and designators.

## What Changes

- **Copper.** `<name>.PcbDoc` gains the model's `Board.tracks`, `arcs`, `vias` and `zones`:
  - tracks and arcs with their net, in the 36- and 47-byte forms Altium Designer 26.5 accepts;
  - through vias in the 321-byte form Altium saves;
  - each zone as one polygon pour per layer (outline, net, layer, pour order) **without poured
    copper**. Altium repours. Altium saves such polygons itself and documents the unpoured state
    (S-0176, S-0195).
- **4-layer stack.** `design.board(w, h, copper=4)` exists; the Altium build now receives the count.
  `In1.Cu` and `In2.Cu` become the signal layers Mid-Layer 1 and 2. A power plane is a zone on an
  inner layer.
- **Net classes and rules.** Each model net class becomes a `Classes6` net class. `Rules6` gets
  Clearance, Width and Routing Via Style rules (cuttable).
- **Refusals.** A blind, buried or micro via, copper outside the stack, a stack that is not 2 or 4
  standard layers, or a zone without an outline gives an error and no file.
- **Route of the copper.** This change only writes what the model holds. Script copper comes from
  c0028's intents; router results from c0016 and c0023. c0038 can be implemented before c0028: its
  tests and sample put copper into the model directly.
- **Oracle.** `kicad-cli pcb import --format altium` (10.0.6) reads the tracks, arcs, vias and zones;
  Fenolite's own reader compares the import with the model. A probe of 2026-10-03 matched to the
  nanometre on four layers.
- **Sample.** An authored routed 4-layer sample and Part C of `docs/evidence/altium-pcb.md`.

## Capabilities

### Modified Capabilities (no new capability)

- `altium-pcb-writer`: ADDED "Copper layer map", "Four-layer stack", "Routed track and arc records",
  "Via records", "Polygon pour records", "Net class records", "Design rule records", "Copper records
  read back", "Copper oracle"; MODIFIED "PCB document file" (c0035's text).
- `altium-build`: ADDED "Copper in an Altium build", "Copper issue codes", "Copper evidence", "Routed
  sample and author report", "Copper is documented"; MODIFIED "PCB document output" (c0035's text).

## Non-goals

- No copper source: no DSL call, no router, no `.kicad_pcb` read into the Altium build.
- No poured copper (`Regions6`), hatched pour, zone settings (c0031) or zone fill (c0015).
- No internal or split planes, no blind, buried or micro vias, no second drill pair.
- No differential pairs, tear-drops, keep-outs, board texts or graphics; no other rule kind.
- No stack other than 2 or 4 copper layers. No Altium reader. No change to the KiCad target.

## Evidence level required

- What KiCad's importer reads (tracks, arcs, vias, zone outlines, four copper layers):
  `ORACLE-VERIFIED(kicad-cli)` on 10.0.x under `H-A-PCB-CU-KICAD`; no claim about Altium.
- What Altium must accept: `INFERRED` under `H-A-PCB-CU-TRACK`, `-VIA`, `-STACK`, `-REPOUR`, `-CLASS`,
  `-RULES` and `-VIEWER`, until the maintainer reports Part C. A confirmed row becomes
  `ALTIUM-VERIFIED(author-report; AD 26.5; <date>; no artefact)`.
- Net classes and rules have no oracle: `pcb import` writes no project file.
- The Altium build stays `INFERRED` and experimental.

## Impact

- Code: `backends/altium/{pcbrecords,pcbdoc,docboard,libboard}.py`, `lens/altium.py`,
  `cli/cmd_build.py`.
- Data: `tests/data/altium/routed/`; the blink golden document is rebuilt (its net class is written).
- Docs: `docs/formats/altium/pcb-copper.md` (new), `docs/altium.md`, the evidence page, the
  registers. Sources S-0195 to S-0198.
- Archive order: … → c0035 → c0036 → c0037 → c0038.
- Size: 7.75 design-days (a size, not time); 7.0 without the rules group.
