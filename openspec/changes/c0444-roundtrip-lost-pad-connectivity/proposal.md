# c0444: lost pads and the Altium round trip's connectivity

## Why

After an Altium → KiCad → Altium round trip, Altium's DRC reports Un-Routed and Net Antennae violations on
public rows 01 (BMS: 41 un-routed, 23 of them via to via, 54 antennae, all on vias) and 06 (cobra: 5
un-routed, 28 antennae, 27 on top tracks) where the sources have none (S-2030, altium-rounds-2, Altium 24.5).
Measured on the round trip of both rows:

- The vias keep their position, net, span, diameter and drill, and the tracks keep their ends, within 2 nm
  after the board's translation.
- Rounded-rectangle pads lost their corner ratio in the KiCad board (the writer left `roundrect_rratio` out
  of a created pad), so KiCad → Altium refused them: 71 pads of cobra, the two pads of BMS's `L3` (14 vias
  of net `5V` sit in its pad 2). Change c0441 already writes the ratio; on its base no pad is lost.
- `equivalent` did not see the lost pads at level 5: it compares only the pads both sides hold, so a track
  that ends on a pad the other side lacks joined the same pad set on both sides.
- The remaining cause is in the polygons the Altium writer gives every zone (not fixed here, see
  design.md).

## What Changes

- Level 5 of `equivalent` counts a pad that only one side holds, on that side, in a piece that holds copper:
  copper that reaches a lost pad is `equiv.route-connectivity` on its net. A pad no copper reaches stays a
  level-2 and level-3 difference only.
- An authored round-trip board and tests: corner ratios survive, no pad is lost, level 5 sees a lost pad.

## Impact

- `src/fenolite/checks/equivalence/routing.py` (`NetPairing.one_sided`, `net_routing`, `level_routing`).
- A conversion whose writer loses a pad that copper reaches now has a level-5 difference too; the `pad`
  loss row explains it (`Explains("pad", LEVEL5, "net")`).
