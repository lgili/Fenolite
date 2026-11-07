# Design: c0446

## Mapping

| Altium key | `ZoneSettings` | note |
|---|---|---|
| `REMOVEDEAD=FALSE` | `island_removal="never"` | as c0085 writes it; wins over the area |
| `REMOVEISLANDSBYAREA=TRUE`, `AREATHRESHOLD=A` | `island_removal="below_area"`, `min_island_area = A·2.54² nm²` | Altium removes every piece below A (I12); KiCad removes isolated islands below it |
| otherwise | `island_removal="always"` | dead copper removed, nothing by area |
| `REMOVENECKS=TRUE`, `NECKWIDTHTHRESHOLD=W` | `min_thickness=W` | both remove copper narrower than the width (I10, KiCad's minimum width) |

The writer is the inverse: `REMOVEISLANDSBYAREA=TRUE` only for `below_area`, `AREATHRESHOLD` its area in
square file units (six decimals, half to even; `250000000000.000000`, Altium's own default, otherwise),
`REMOVENECKS=TRUE` and `NECKWIDTHTHRESHOLD` the minimum width as mil text (four decimals: the unit). KiCad's
default 0.25 mm is `9.8425mil`, which reads back as 250 000 nm. `REMOVENECKS=FALSE` has no KiCad
counterpart and reads as the default width.

The board outline record shares the tail keys and keeps them (`_POLYGON_TAIL`); only pours change.

## Default settings keep the kit's bytes

Writing a default KiCad zone from its settings (`FALSE`, `9.8425mil`) changed the bytes of the kit samples
and made 17 graduated kit runs stale (`gen_altium_graduation --check`: H-A-WRITE-PCBDOC, H-A-KIT-DRC and
others). A zone with the default island mode and minimum width therefore keeps Altium's own thresholds
(2500 mil², 5 mil), the bytes c0035 wrote and the kit verified, and the reader maps Altium's own thresholds
back to the default settings. A default stays a default either way round:

- public row 01 (BMS), whose sources hold 2500 mil² and 5 mil, reads as default zones and writes back the
  same keys;
- public row 06 (cobra), whose sources hold 0.1 mm² and 0.1 or 0.15 mm, carries them through KiCad
  (`island_removal_mode 2`, `island_area_min 0.1`, `min_thickness 0.1`/`0.15`) and writes them back.

A native KiCad zone with the default settings still gets the 2500 mil² area removal in Altium; changing that
needs a new kit run of the graduated samples.

## Result on rows 01 and 06

After the round trip the polygon thresholds equal the source's on both rows, except the three BMS polygons
with `REMOVEDEAD=FALSE` and area removal, which read as `never` and come back without area removal.
`equivalent` level 5 with the computed pour is unchanged: `route-connectivity` on the pour nets (cobra GND,
3V3, 5V, VBUS; BMS GND, VBB, VDD). So the threshold is not what splits those nets in Fenolite's pour; on BMS
the sources already held 2500 mil², so it cannot explain BMS's antennae either. Fenolite's engine cannot pour
the cobra source document itself (a degenerate ring while reading it), so the engine's fidelity to Altium's
own pour on these rows is not measured here. Altium's DRC after Repour All decides (task 3.3).
