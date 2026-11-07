## MODIFIED Requirements

### Requirement: Polygon pour records
`pcbdoc.write_pcbdoc` SHALL write each `model.board.Zone` of `PcbDocSpec.zones` as one `Polygons6` property record per zone layer, with or without poured copper by its pour mode ("Polygon pour modes"; S-0160, S-0172, S-0174, S-0175, S-0176, S-0195, S-0196, S-0833; `H-A-PCB-CU-REPOUR`).

#### Scenario: Detailed contract for polygon pour records
- **WHEN** this behavior is exercised
- **THEN** the following detailed conditions MUST hold:

`pcbdoc.write_pcbdoc` SHALL write each `model.board.Zone` of `PcbDocSpec.zones` as one `Polygons6` property record per zone layer, with or without poured copper by its pour mode ("Polygon pour modes"; S-0160, S-0172, S-0174, S-0175, S-0176, S-0195, S-0196, S-0833; `H-A-PCB-CU-REPOUR`).
- A record MUST hold, in this order: the seven common keys with `LAYER` = the layer text; `PRIMITIVELOCK=TRUE`, `POLYGONTYPE=Polygon`, `POUROVER=TRUE`, `REMOVEDEAD=TRUE` (`FALSE` for a zone whose islands are never removed, change c0085), `GRIDSIZE=20mil`, `TRACKWIDTH=8mil`, `HATCHSTYLE=Solid`, `USEOCTAGONS=FALSE`, `MINPRIMLENGTH=3mil`; per vertex `KIND<k>=0`, `VX<k>`, `VY<k>`, `CX<k>`, `CY<k>`, `SA<k>`, `EA<k>`, `R<k>` as the board outline writes them, the first vertex repeated last; `SHELVED=FALSE`, `RESTORELAYER=UNKNOWN`, `RESTORENET` (empty), `REMOVEISLANDSBYAREA`, `REMOVENECKS=TRUE`, `AREATHRESHOLD`, `ARCRESOLUTION=0.5mil`, `NECKWIDTHTHRESHOLD` (change c0446: a zone whose `settings.island_removal` is `always` and whose `settings.min_thickness` is 0.25 mm, the default settings, keeps `REMOVEISLANDSBYAREA=TRUE`, `AREATHRESHOLD=250000000000.000000` and `NECKWIDTHTHRESHOLD=5mil`, the values the kit verified; any other zone gets `REMOVEISLANDSBYAREA=TRUE` only when `island_removal` is `below_area`, with `AREATHRESHOLD` its `min_island_area` in square file units, 0.0001 mil squared, six decimals rounded half to even, else `FALSE` with `250000000000.000000`, and `NECKWIDTHTHRESHOLD` its `min_thickness` as mil text), `POUROVERSTYLE=1`, `NAME`, `POURINDEX`, `IGNOREVIOLATIONS=FALSE`, `AUTONAME` (only when the name is generated), `OPTIMALVOIDROTATION` (`TRUE` with the pour mode `outline`, `FALSE` with `computed`, change c0215), and `NET` (the net's index; left out without a net).
- `NAME` MUST be the character codes of the name in decimal, joined by commas. The name is `Zone.name`, or `<net name>_L<layer position, two digits from 01>_P<pour index, three digits>` when it is empty (`NONET` stands for a missing net), in upper case, with `AUTONAME=TRUE`.
- `POURINDEX` MUST number the records from 0 in the order of falling `Zone.priority`, then net name, first outline point, zone id and stack position, so a zone of higher priority is poured first. `POURINDEX` MUST equal the record's position in `Polygons6`.
- With the pour mode `outline`, `Regions6` and `ShapeBasedRegions6` MUST hold no region of a polygon (they hold the filled graphics, keep-outs and cut-outs only, and stay empty without them). `Zone.fills` MUST NOT be written in either mode: a computed pour comes from the document ("Poured regions"), never from the model.
- A zone with fewer than three outline points, a zone layer outside the copper layers or on a plane, or a name that fails `text_problem` MUST raise `ValueError` naming the zone's id.

#### Scenario: Ground zone on two layers
- **GIVEN** a zone on `In1.Cu` and `B.Cu` with the net `GND`, four outline points and priority 0, and a second zone on `F.Cu` with priority 2
- **WHEN** `Polygons6` is read after a write with the pour mode `outline`
- **THEN** it holds three records; the `F.Cu` record has `POURINDEX=0`; the two `GND` records have `LAYER=MID1` and `LAYER=BOTTOM`, five vertices, `NET` equal to the index of `GND`, and names that decode to `GND_L02_P001` and `GND_L04_P002`; `Regions6` is empty

#### Scenario: Zone without an outline refused
- **WHEN** a spec holds a zone whose `outline` is empty
- **THEN** `write_pcbdoc` raises `ValueError` naming the zone's id

#### Scenario: Zone fills of the model are not written
- **GIVEN** a zone whose `fills` hold a ring that differs from what the engine pours
- **WHEN** the document is written with the pour mode `computed`
- **THEN** the regions of the polygon are the engine's pieces, and no region holds the model's ring

#### Scenario: Thresholds from the zone settings
- **GIVEN** a zone with the default settings, a zone whose islands are removed below 0.1 mm² with a minimum width of 0.1 mm, and a zone whose islands are never removed
- **WHEN** `uv run pytest tests/unit/backends/altium/test_polygon_thresholds.py -k written` writes them
- **THEN** the first record holds `REMOVEISLANDSBYAREA=TRUE`, `AREATHRESHOLD=250000000000.000000` and `NECKWIDTHTHRESHOLD=5mil`; the third `REMOVEDEAD=FALSE`, `REMOVEISLANDSBYAREA=FALSE` and `NECKWIDTHTHRESHOLD=9.8425mil`; the second holds `REMOVEISLANDSBYAREA=TRUE`, `AREATHRESHOLD=15500031000.062000` (Altium's own save of 0.1 mm² holds `15500031000.062008`, which reads as the same square nanometres) and `NECKWIDTHTHRESHOLD=3.937mil`; the board outline's polygon keeps `REMOVEISLANDSBYAREA=TRUE`, `AREATHRESHOLD=250000000000.000000` and `NECKWIDTHTHRESHOLD=5mil`
