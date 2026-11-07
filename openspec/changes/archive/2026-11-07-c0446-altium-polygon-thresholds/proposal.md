# c0446: polygon island and neck thresholds from the zone settings

## Why

c0444 found that the Altium writer gives every polygon `REMOVEISLANDSBYAREA=TRUE`, `AREATHRESHOLD` 2500
mil² (1.6 mm²) and `NECKWIDTHTHRESHOLD=5mil`, whatever the zone holds. By `pcb-pour.md` I12, Altium removes
a pour piece below the threshold whatever it connects. A KiCad zone never removes connected copper by
area. So the small pour islands around stitching vias go, and the vias are left connected on one layer.
After an Altium → KiCad → Altium round trip of public rows 01 and 06, the polygons hold 2500 mil² where
the sources hold 0.1 mm², and Altium's DRC reports Un-Routed and Net Antennae on vias (S-2030). The reader
does not project the keys either, so KiCad never holds the source's values.

## What Changes

- The writer takes `REMOVEISLANDSBYAREA`, `AREATHRESHOLD` and `NECKWIDTHTHRESHOLD` of a polygon pour from
  `Zone.settings`: area removal only for `below_area` (with `min_island_area`), the neck width from
  `min_thickness`. A zone with the default settings keeps the bytes the kit verified (2500 mil², 5 mil), and
  the board outline's polygon keeps its keys.
- The reader projects `REMOVEDEAD`, `REMOVEISLANDSBYAREA`, `AREATHRESHOLD`, `REMOVENECKS` and
  `NECKWIDTHTHRESHOLD` into `Zone.settings`, so a KiCad conversion holds them and the way back writes them.
- The reader maps Altium's own thresholds (2500 mil², 5 mil) to the default settings, so a default stays a
  default either way round. Only zones with other settings write other bytes; the computed pour follows the
  written record.

## Impact

- `backends/altium/docboard.py`, `backends/altium/pcbdoc.py`, `backends/altium/adapter/copper.py`.
- A KiCad zone written to Altium keeps its connected small pieces (KiCad semantics) and has its own minimum
  width as the neck width; KiCad's `below_area` removes isolated islands only, Altium removes any piece
  below the area: the closest mapping, `INFERRED`.
