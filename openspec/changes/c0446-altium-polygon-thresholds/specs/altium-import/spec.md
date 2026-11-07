## MODIFIED Requirements

### Requirement: Zones from polygons
`import_board` SHALL map each record of `Polygons6` whose `polygon_type` is `Polygon` and whose layer is a copper layer of the chain to one `Zone`.
- `outline` MUST be the vertices in order, converted, without the repeated last vertex. A record with an arc vertex MUST give `outline == ()`, which the model defines as "kept by the backend", and one `altium.import.zone-arc` info per import with the count.
- `layers` is the one layer; `net_id` the net of the record's net index; `name` the record's name.
- `priority` MUST be `max(pour_index) − pour_index` over the mapped zones, so the zone poured first has the highest priority, the inverse of what c0038 writes. The original goes to `pour_index`.
- `fills` MUST hold one `ZoneFill(layer, polygon)` per region of `PcbDocument.regions_of(index)` on a copper layer, in stream order. Tracks and arcs of a hatched pour are counted as `pour-primitives`, not mapped.
- `polygon` MUST be `keyhole_ring(outline, holes).ring` ("Keyhole ring of a polygon with holes" of `geometry-kernel`), `outline` and each hole being the region's vertices rounded by "Units and frame", without a repeated last vertex and without repeated neighbours. The copper of a fill is therefore the region's outline without its holes: a point inside a hole is outside the polygon under the non-zero and the even-odd rule, and a region without a hole gives its outline unchanged.
- A hole that the ring does not hold is not in the model and MUST be counted as `region-holes`: one with fewer than three distinct points or without area, and one that lies outside its outline. The holes outside their outline MUST also give one `altium.import.zone-hole-outside` warning per import, located at `Regions6/Data`, whose message holds the count of such holes and the count of regions that hold them.
- A polygon of another type (a split plane, a cutout), or on a layer outside the chain, is unmapped.
- `settings` MUST project the record's island and neck keys (change c0446), every other setting staying at its default: `island_removal` is `never` when `REMOVEDEAD` is `FALSE`; otherwise `below_area` when `REMOVEISLANDSBYAREA` is `TRUE` and `AREATHRESHOLD` is a number, with `min_island_area` that number times 2.54² nm² rounded half to even; otherwise `always`. `min_thickness` is `NECKWIDTHTHRESHOLD` when `REMOVENECKS` is `TRUE` and the width is a positive length. A key that is absent or unreadable leaves its setting at the default. Altium's own thresholds, `below_area` with 2500 mil² (1 612 900 000 000 nm²) and a width of 5 mil, MUST give the default settings: they are the pair the writer gives a zone with the default settings, so either way round a default stays a default.

#### Scenario: Unpoured zones of the routed sample
- **GIVEN** the PCB document of `tests/data/altium/routed/`, whose two zones are written without poured copper
- **WHEN** it is imported
- **THEN** the board holds the zones with the model's nets, layers and outlines within 2 nm, each on one layer, with `fills == ()`, and the zone that the model gives the highest priority has the highest priority

#### Scenario: Outline with an arc
- **GIVEN** a polygon whose second vertex has `KIND1=1`
- **WHEN** it is imported
- **THEN** the zone has `outline == ()`, its net and layer are set, and `altium.import.zone-arc` reports one zone

#### Scenario: Pour with a hole and an island
- **GIVEN** a document with one polygon on layer 1 and two regions of it: a square with one square hole, and a smaller square that lies inside that hole
- **WHEN** it is imported
- **THEN** the zone has two fills, the first polygon holds the four points of the outline followed by the anchor, the hole and the anchor again, a point inside the hole and outside the island is `OUTSIDE` of the first polygon, the copper check's touch test finds the two fills apart, the copper check reports no short with a track of another net that lies in the hole, the net of the polygon has two pieces of copper, and no `region-holes` is counted

#### Scenario: Hole outside its outline
- **GIVEN** a polygon with three regions: one with a hole that lies wholly outside its outline, one with such a hole and a hole inside its outline, and one with a hole of three equal points
- **WHEN** it is imported
- **THEN** the first and the third fill are their region's outline, the second holds its inner hole, one `altium.import.zone-hole-outside` warning located at `Regions6/Data` reports 2 holes of 2 regions, and `region-holes` counts 3

#### Scenario: Island and neck settings of a saved polygon
- **GIVEN** the polygons of "Thresholds from the zone settings" as written: Altium's own thresholds; `REMOVEISLANDSBYAREA=TRUE` with 0.1 mm² and `NECKWIDTHTHRESHOLD=3.937mil`; and `REMOVEDEAD=FALSE`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_polygon_thresholds.py -k read` imports them
- **THEN** the first zone has the default settings; the second `island_removal == "below_area"`, `min_island_area == 100_000_000_000` and `min_thickness == 100_000`; the third `never` with a minimum width of 0.25 mm
