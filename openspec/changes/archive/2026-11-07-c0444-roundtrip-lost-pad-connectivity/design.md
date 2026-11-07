# Design: c0444

## Level 5 and one-sided pads

`pair_nets` pairs nets over the elements both sides hold and now also returns the elements only one side
holds (`one_sided`, the symmetric difference of the numbered pads). `net_routing` keeps a pad of
`one_sided` in a piece when the piece holds copper. On the side that has the pad the piece joins it; on the
other side the same copper joins one pad fewer, so the multisets of pad sets differ. A lone pad that no
copper reaches gives no new level-5 difference: the pad is already `pad-missing` and `pin-missing`.

On public row 06 before c0441 the round trip now gives `route-connectivity` on 8 nets (DN, DP, NetR301_2,
NetR302_2, SCL, SDA, XI and XO); before, level 5 reported only one `route-length`.

## The polygon thresholds (found, not changed here)

On the c0441 base the round trip keeps every via, track end and copper pad of rows 01 and 06, and level 5
with the computed pour still reports `route-connectivity` on the pour nets: GND, 3V3, 5V and VBUS of row 06,
and GND, VBB and VDD of row 01. The written polygons differ from the source's:

| key | source (row 06) | written |
|---|---|---|
| `AREATHRESHOLD` | 15500031000.062008 (0.1 mm²) | 250000000000.000000 (2500 mil², 1.6 mm²) |
| `NECKWIDTHTHRESHOLD` | 3.937mil | 5mil |

`pcb-pour.md` I12: with `REMOVEISLANDSBYAREA=TRUE` a piece below `AREATHRESHOLD` is removed whatever it
connects. The writer (`docboard._POLYGON_TAIL`) writes `TRUE` with 2500 mil² for every zone. A KiCad zone
never removes connected copper by area, so the pour island around a stitching via goes, and the via is left
connected on one layer only: Altium's antennae on vias and its via-to-via un-routed connections. The Altium
reader does not project `REMOVEISLANDSBYAREA`, `AREATHRESHOLD` or `NECKWIDTHTHRESHOLD` into
`ZoneSettings`, so KiCad never holds them. A follow-up change should write `REMOVEISLANDSBYAREA` from
`ZoneSettings.island_removal` (`below_area` with `min_island_area`, otherwise `FALSE`) and have the
Altium reader project the three keys. It changes the bytes of every written polygon, so it needs the full
suite.
