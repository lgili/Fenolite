# c0454: copper of an Altium component keeps its net through KiCad

## Why

An Altium component can own copper beside its pads: regions, fills, tracks and arcs on a signal layer,
each with a net. The public row `-01` (BMS) holds four on its top layer, all with nets:
- two regions of the inductor `L3`, one over each pad;
- two fills of `Q2` and `Q6` (S-2130).

The round trip Altium → KiCad → Altium lost all four, so the written board lacked copper that carries
current. Altium Designer showed the two regions missing (S-2011).

The copper was lost in three places:
- The import gave a component's copper its net name in the pair `net` but not in `net_id`, so the
  KiCad writer saw no net.
- The KiCad writer cleared the net of every footprint graphic (`_netless`), so the `fp_poly` had no
  `(net …)`.
- The Altium writer wrote a footprint's copper graphic only for a footprint with net-tie groups (c0431);
  every other one was counted lost under `footprint-copper` ("it would be copper").

## What

- **Import.** `adapter.copper.footprint_items` sets `net_id` on a component's copper graphic with a net,
  as `shapes` does for free copper (c0376).
- **KiCad writer.** A created footprint's `fp_*` on a copper layer writes `(net …)` after `(layer …)`,
  where KiCad 10.0.6 keeps it on a save (S-2131). A graphic on any other layer still holds no net.
- **KiCad read.** `fpitems.with_graphic_nets` also sets `net_id` on a footprint's copper graphics. It reads
  the net from the `(net …)` child of the drawn child each graphic projects (`footprint_graphic_nets`).
- **Altium writer.** `lower._footprint_items` writes a copper graphic of a footprint without net-tie groups,
  whose `net_id` names a net of the written board, as a component item of that net on its signal layer
  (`netted_copper_problem`; `pcbdoc.ComponentGraphic.net`). A netless copper graphic of such a footprint
  stays lost, as before.

## Not in this change

- A Fill is written back as a region, not a Fill (c0450).
- `equivalent` does not compare a footprint's copper graphics. The loss was invisible to it: levels 1 to 5
  gave the same differences before and after this change.
- KiCad's DRC still reports a footprint copper graphic that touches other copper as `shorting_items`, with
  or without a net. KiCad's own importer instead makes such copper an unnumbered pad.

## Impact

- Code:
  - `backends/altium/adapter/copper.py`;
  - `backends/kicad/pcb.py`;
  - `backends/kicad/fpitems.py`;
  - `backends/altium/lower.py`;
  - `backends/altium/pcbdoc.py`.
- Docs:
  - `docs/formats/kicad/board.md`;
  - `docs/formats/altium/pcb-records.md`;
  - `docs/evidence/sources.md` (S-2130, S-2131);
  - `CHANGELOG.md`.
